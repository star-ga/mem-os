# /recall — Memory Search

Lexical search across all structured memory files. Default backend: TF-IDF with field boosts and recency weighting. Optional: vector/embedding backend (configure in mem-os.json). Returns ranked results with block ID, type, score, excerpt, and file path.

## When to Use
- Before making decisions (check if a similar decision already exists)
- When asked about past events, decisions, or tasks
- To find related context for a current problem
- To check what's known about a person, project, or tool

## How to Run

### Basic Search
```bash
python3 scripts/recall.py --query "authentication" --workspace "${MEM_OS_WORKSPACE:-.}"
```

### JSON Output (for programmatic use)
```bash
python3 scripts/recall.py --query "auth" --workspace "${MEM_OS_WORKSPACE:-.}" --json --limit 5
```

### Active Items Only
```bash
python3 scripts/recall.py --query "deadline" --workspace "${MEM_OS_WORKSPACE:-.}" --active-only
```

## What It Searches
- `decisions/DECISIONS.md` — All decisions
- `tasks/TASKS.md` — All tasks
- `entities/projects.md` — Projects
- `entities/people.md` — People
- `entities/tools.md` — Tools
- `entities/incidents.md` — Incidents
- `intelligence/CONTRADICTIONS.md` — Known contradictions
- `intelligence/DRIFT.md` — Drift detections
- `intelligence/SIGNALS.md` — Captured signals

## Scoring
Results are ranked by TF-IDF relevance with boosts for:
- **Recency** — Recent items score higher
- **Active status** — Active items get 1.2x boost
- **Priority** — P0/P1 items get 1.1x boost
