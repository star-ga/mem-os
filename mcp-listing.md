# Mem-OS — MCP Community Listing

Append-only, auditable memory with contradiction detection, drift analysis, namespaces, proposals, and BM25 recall. Zero dependencies, git-diffable Markdown blocks. Built for OpenClaw/Claude coding agents.

## Features

### Resources (8)

- `mem-os://decisions` — Active decisions
- `mem-os://tasks` — All tasks
- `mem-os://entities/{type}` — Entities (projects, people, tools, incidents)
- `mem-os://signals` — Auto-captured signals pending review
- `mem-os://contradictions` — Detected contradictions
- `mem-os://health` — Workspace health summary
- `mem-os://recall/{query}` — BM25 recall search results
- `mem-os://ledger` — Shared fact ledger (multi-agent)

### Tools (6)

- `recall` — Search memory with BM25 (stemming, query expansion, graph boost)
- `propose_update` — Propose a decision or task (writes to SIGNALS.md only, never source of truth)
- `approve_apply` — Apply a staged proposal (dry-run by default)
- `rollback_proposal` — Rollback an applied proposal by receipt timestamp
- `scan` — Run integrity scan (contradictions, drift, dead decisions)
- `list_contradictions` — List contradictions with auto-resolution analysis

### Safety Guarantees

- `propose_update` never writes to DECISIONS.md or TASKS.md — all proposals go to SIGNALS.md
- `approve_apply` defaults to `dry_run=True` — agents must explicitly opt in to apply
- All resources are read-only — no MCP client can mutate source of truth
- Snapshot before every apply for rollback support

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

## Benchmarks

- **LongMemEval (ICLR 2025)**: R@10=88.1%, MRR=0.784 (470 questions)
- **LoCoMo (Snap Research)**: R@10=66.9%, MRR=0.453 (1986 questions)
- Pure BM25 + Porter stemming, zero dependencies

## Tags

`persistent-memory` `governance` `append-only` `contradiction-safe` `audit-trail` `zero-dependencies` `local-first`

## Links

- Repository: https://github.com/star-ga/mem-os
- License: MIT
- Author: STARGA Inc
