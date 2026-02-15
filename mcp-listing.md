# mem-os

Persistent, auditable, contradiction-safe memory for AI coding agents. Local-first with zero core dependencies.

## Features

### Resources (8)

- `mem-os://decisions` -- Active decisions
- `mem-os://tasks` -- All tasks
- `mem-os://entities/{type}` -- Entities (projects, people, tools, incidents)
- `mem-os://signals` -- Auto-captured signals pending review
- `mem-os://contradictions` -- Detected contradictions
- `mem-os://health` -- Workspace health summary
- `mem-os://recall/{query}` -- BM25 recall search results
- `mem-os://ledger` -- Shared fact ledger (multi-agent)

### Tools (6)

- `recall` -- Search memory with BM25 (stemming, query expansion, graph boost)
- `propose_update` -- Propose a decision or task (writes to SIGNALS.md only, never source of truth)
- `approve_apply` -- Apply a staged proposal (dry-run by default)
- `rollback_proposal` -- Rollback an applied proposal by receipt timestamp
- `scan` -- Run integrity scan (contradictions, drift, dead decisions)
- `list_contradictions` -- List contradictions with auto-resolution analysis

## Install

```bash
pip install "mem-os[mcp]"
```

Or from source:

```bash
git clone https://github.com/star-ga/mem-os.git
pip install "fastmcp>=2.0"
```

## Claude Desktop Configuration

```json
{
  "mcpServers": {
    "mem-os": {
      "command": "python3",
      "args": ["/path/to/mem-os/mcp_server.py"],
      "env": {"MEM_OS_WORKSPACE": "/path/to/workspace"}
    }
  }
}
```

## Links

- Repository: https://github.com/star-ga/mem-os
- License: MIT
