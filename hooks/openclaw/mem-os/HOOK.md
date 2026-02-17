---
name: mem-os
description: "Memory OS health check on bootstrap + auto-capture on /new"
homepage: https://github.com/star-ga/mem-os
metadata:
  { "openclaw": { "emoji": "🧠", "events": ["agent:bootstrap", "command:new"], "requires": { "bins": ["python3"] } } }
---
# Mem OS

Memory + Immune System for OpenClaw agents. Injects health context on agent bootstrap and auto-captures session signals on `/new`.

## Events

- **agent:bootstrap**: Reads `intel-state.json` and pushes health summary into bootstrap context
- **command:new**: Runs `capture.py` to extract decision/task signals from the session

## Configuration

In `~/.openclaw/openclaw.json`:

```json
{
  "hooks": {
    "internal": {
      "entries": {
        "mem-os": {
          "enabled": true,
          "env": {
            "MEM_OS_WORKSPACE": "/path/to/your/workspace"
          }
        }
      }
    }
  }
}
```

## Install

```bash
# Copy hook to managed hooks directory
cp -r /path/to/mem-os/hooks/openclaw/mem-os ~/.openclaw/hooks/mem-os

# Enable
openclaw hooks enable mem-os
```
