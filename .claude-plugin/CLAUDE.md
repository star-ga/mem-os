# Mem OS for OpenClaw — Memory + Immune System

## Available Commands
- `/scan` — Run contradiction detection, drift analysis, impact graph, snapshot, briefing
- `/validate` — Run structural integrity validation (74+ structural checks, 478 unit tests)
- `/apply <ProposalId>` — Apply a staged proposal with atomic rollback
- `/recall <query>` — Search all memory files (BM25F + graph + optional vector)
- `/status` — Health dashboard (contradictions, drift, coverage)
- `/init` — Scaffold a new mem-os workspace

## Memory Protocol
- Write decisions to `decisions/DECISIONS.md` (never edit old decisions — supersede them)
- Write tasks to `tasks/TASKS.md`
- Write entities to `entities/*.md` (projects, people, tools, incidents)
- Raw events to `memory/YYYY-MM-DD.md` (append-only daily logs)
- Every claim needs a source — no source = no memory claim

## Modes
- `detect_only` — scan and report, never modify (default)
- `propose` — scan and generate proposals for human review
- `enforce` — auto-apply low-risk proposals (requires explicit opt-in)

## Config
Settings in `mem-os.json` at workspace root. Created by `/init`.
