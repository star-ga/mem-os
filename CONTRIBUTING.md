# Contributing to Mem OS

Thanks for your interest in contributing to Mem OS.

## How to Contribute

1. **Open an issue first** — Describe what you want to change and why. This avoids duplicate work and ensures alignment.

2. **Fork the repo** — Create a fork and work on a feature branch.

3. **Keep it simple** — Mem OS has zero external dependencies. Any contribution must maintain this constraint for the core. Vector backends are the exception (they go in optional modules).

4. **Test your changes** — Run the full validation suite on a fresh workspace:

```bash
# Create a test workspace
python3 scripts/init_workspace.py /tmp/test-ws

# Run integrity scan
python3 scripts/intel_scan.py /tmp/test-ws

# Run structural validation
bash scripts/validate.sh /tmp/test-ws
```

5. **Submit a PR** — Reference the issue number in your PR description.

## What We're Looking For

- Bug fixes with reproduction steps
- New integrity checks for `validate.sh`
- New detection patterns for `capture.py`
- Vector backend implementations (`recall_vector.py`)
- Documentation improvements
- Performance improvements (especially for large workspaces)

## What We Won't Merge

- External dependency additions to core scripts
- Changes that break backward compatibility with existing workspaces
- Auto-write to source of truth (decisions/tasks) without going through the proposal pipeline
- Features that require a daemon or background process

## Code Style

- Python: Follow existing patterns in the codebase. No type stubs or annotations unless they add clarity.
- Bash: Use `set -euo pipefail`. Quote variables. Use `shellcheck` if available.
- Markdown: Use `## [ID]` block format. Keep templates minimal.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
