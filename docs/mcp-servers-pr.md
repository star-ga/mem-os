# PR: Add Mem-OS to Community Servers

## Entry to add (alphabetical, after "Maybe Don't AI Policy Engine"):

```markdown
- **[Mem-OS](https://github.com/star-ga/mem-os)** - Append-only, auditable memory with contradiction detection, drift analysis, multi-agent namespaces, and BM25 recall. Proposal-based governance (propose_update writes to SIGNALS.md only, never source of truth). Zero dependencies, git-diffable Markdown blocks. 478 tests, benchmarked on LoCoMo and LongMemEval.
```

## PR Title

Add Mem-OS: governance-safe, contradiction-proof memory for coding agents

## PR Body

```
## Summary

Adds [Mem-OS](https://github.com/star-ga/mem-os) to the community servers list.

Mem-OS is a persistent, auditable memory layer for AI coding agents (Claude Desktop, OpenClaw, Cursor, Windsurf). Key differentiators from existing memory servers:

- **Proposal-based governance**: `propose_update` writes to SIGNALS.md only — never mutates source of truth. All changes require explicit `/apply`.
- **Integrity engine**: Contradiction detection (ConstraintSignatures), drift analysis, dead decision detection, coverage scoring.
- **Zero dependencies**: Pure Python stdlib. No vector DB, no cloud, no daemon.
- **Git-diffable**: All data is structured Markdown blocks with typed IDs.
- **Benchmarked**: LoCoMo R@10=66.9% (1986 questions), LongMemEval R@10=88.1% (470 questions).

### MCP Surface

**8 Resources**: decisions, tasks, entities/{type}, signals, contradictions, health, recall/{query}, ledger
**6 Tools**: recall, propose_update, approve_apply, rollback_proposal, scan, list_contradictions

### Safety

- `approve_apply` defaults to `dry_run=True`
- All resources are read-only
- Snapshot before every apply for rollback
- Token auth for HTTP transport

### Install

```bash
pip install "fastmcp>=2.0"
git clone https://github.com/star-ga/mem-os.git
```

MIT License. 478 tests.
```

## Checklist

- [x] Entry is alphabetically sorted
- [x] Description is concise (1-2 sentences in list)
- [x] Repository link is correct
- [x] Repository is public
- [x] Server has README with setup instructions
- [x] Server has .mcp.json manifest
- [x] Server has server.json for registry
