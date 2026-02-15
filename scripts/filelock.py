#!/usr/bin/env python3
"""mem-os file locking — cross-platform advisory locks. Zero external deps.

Provides cooperative file locking for concurrent agent/session writes.
Uses fcntl on Unix, msvcrt on Windows. Falls back to lockfile-based locking
if neither is available.

Usage:
    from filelock import FileLock

    with FileLock("path/to/file.md"):
        # exclusive access to the file
        ...

    # Or manual:
    lock = FileLock("path/to/file.md", timeout=5.0)
    lock.acquire()
    try:
        ...
    finally:
        lock.release()
"""

from __future__ import annotations

import os
import sys
import time
from types import TracebackType


class LockTimeout(Exception):
    """Raised when lock acquisition times out."""
    pass


class FileLock:
    """Cross-platform advisory file lock.

    Creates a .lock file next to the target. Uses OS-level locking
    where available, falls back to atomic create for portability.

    Parameters:
        path: Path to the file to lock.
        timeout: Max seconds to wait for lock (0 = non-blocking, -1 = infinite).
        poll_interval: Seconds between retry attempts.
    """

    def __init__(self, path: str, timeout: float = 10.0, poll_interval: float = 0.05) -> None:
        self.path = os.path.abspath(path)
        self.lock_path = self.path + ".lock"
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._lock_fd = None

    def acquire(self) -> None:
        """Acquire the lock. Raises LockTimeout if timeout exceeded."""
        start = time.monotonic()
        while True:
            try:
                # O_CREAT | O_EXCL: atomic create-if-not-exists
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                # Write PID for debugging stale locks
                os.write(fd, f"{os.getpid()}\n".encode())
                self._lock_fd = fd

                # Apply OS-level lock if available
                self._os_lock(fd)
                return
            except FileExistsError:
                # Check for stale lock (process died without cleanup)
                if self._is_stale():
                    self._break_stale()
                    continue

                if self.timeout == 0:
                    raise LockTimeout(f"Could not acquire lock: {self.lock_path}")
                elapsed = time.monotonic() - start
                if self.timeout > 0 and elapsed >= self.timeout:
                    raise LockTimeout(
                        f"Lock timeout ({self.timeout}s) for: {self.lock_path}"
                    )
                time.sleep(self.poll_interval)

    def release(self) -> None:
        """Release the lock."""
        if self._lock_fd is not None:
            try:
                self._os_unlock(self._lock_fd)
                os.close(self._lock_fd)
            except OSError:
                pass
            self._lock_fd = None
        try:
            os.unlink(self.lock_path)
        except OSError:
            pass

    def _is_stale(self) -> bool:
        """Check if existing lock file is from a dead process."""
        try:
            with open(self.lock_path, "r") as f:
                pid_str = f.read().strip()
            if not pid_str:
                return True
            pid = int(pid_str)
            # Check if process exists
            if sys.platform == "win32":
                return not self._pid_exists_win(pid)
            else:
                try:
                    os.kill(pid, 0)
                    return False  # Process exists
                except ProcessLookupError:
                    return True  # Process dead
                except PermissionError:
                    return False  # Process exists but different user
        except (OSError, ValueError):
            # Can't read lock file — treat as stale after age check
            try:
                age = time.time() - os.path.getmtime(self.lock_path)
                return age > 300  # 5 min stale threshold
            except OSError:
                return True

    def _break_stale(self) -> None:
        """Remove a stale lock file."""
        try:
            os.unlink(self.lock_path)
        except OSError:
            pass

    @staticmethod
    def _pid_exists_win(pid: int) -> bool:
        """Check if a PID exists on Windows."""
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False

    def _os_lock(self, fd: int) -> None:
        """Apply OS-level exclusive lock if available."""
        try:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            try:
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except ImportError:
                pass  # No OS locking available — rely on O_EXCL

    def _os_unlock(self, fd: int) -> None:
        """Release OS-level lock."""
        try:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
        except ImportError:
            try:
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except ImportError:
                pass

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> bool:
        self.release()
        return False

    def __repr__(self) -> str:
        return f"FileLock({self.path!r})"
