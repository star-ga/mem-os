# Mem OS Formal Specification v1.0

This document defines the grammars, invariants, state machine, and atomicity guarantees that govern Mem OS behavior. All implementations MUST conform to this specification.

---

## 1. Block Grammar (EBNF)

All structured data in Mem OS is stored as **blocks** — markdown sections with a typed ID header and key-value body.

```ebnf
Block         ::= Header NewLine Body
Header        ::= "[" BlockID "]"
BlockID       ::= Prefix "-" DatePart "-" Counter
                 | Prefix "-" Counter

Prefix        ::= "D" | "T" | "PRJ" | "PER" | "TOOL" | "INC"
                 | "C" | "DREF" | "SIG" | "P" | "I" | "B" | "S"
DatePart      ::= Digit{8}                          (* YYYYMMDD *)
Counter       ::= Digit{3}                          (* 001-999 *)

Body          ::= { Field NewLine }
Field         ::= Key ":" Space Value
Key           ::= Letter { Letter | Digit | "_" }
Value         ::= { AnyChar }                       (* until NewLine *)

(* Typed ID examples *)
(* D-20260213-001   = Decision                     *)
(* T-20260213-001   = Task                         *)
(* PRJ-001          = Project                      *)
(* PER-001          = Person                       *)
(* TOOL-001         = Tool                         *)
(* INC-001          = Incident                     *)
(* C-20260213-001   = Contradiction                *)
(* DREF-20260213-001 = Drift Reference             *)
(* SIG-20260213-001 = Signal (auto-captured)       *)
(* P-20260213-001   = Proposal                     *)
(* I-20260213-001   = Impact Record                *)
(* B-2026-W07       = Briefing                     *)
(* S-2026-02-14     = Snapshot                     *)
```

### Required Fields by Type

| Type | Required Fields |
|---|---|
| Decision (D-) | Date, Status, Statement |
| Task (T-) | Date, Status, Title |
| Project (PRJ-) | Name, Status |
| Person (PER-) | Name |
| Tool (TOOL-) | Name |
| Incident (INC-) | Date, Status, Summary |
| Contradiction (C-) | Date, DecisionA, DecisionB, Description |
| Drift (DREF-) | Date, Type, Source |
| Signal (SIG-) | Date, Type, Source, Status, Excerpt |
| Proposal (P-) | Date, Type, Status, Target |

### Status Values

```ebnf
DecisionStatus ::= "active" | "superseded" | "archived" | "draft"
TaskStatus     ::= "todo" | "doing" | "done" | "blocked" | "canceled"
SignalStatus   ::= "pending" | "accepted" | "rejected"
ProposalStatus ::= "pending" | "approved" | "applied" | "rejected" | "deferred"
```

---

## 2. ConstraintSignature Grammar

ConstraintSignatures encode the semantic intent of decisions as structured metadata, enabling automated contradiction detection.

```ebnf
ConstraintSignature ::= "ConstraintSignature:" NewLine
                        { SigField NewLine }

SigField      ::= Indent SigKey ":" Space SigValue
Indent        ::= Space Space                       (* 2 spaces *)

(* Required fields *)
SigKey        ::= "axis.key"                        (* unique constraint axis *)
                | "relation"                        (* constraint type *)
                | "object"                          (* target value *)
                | "enforcement"                     (* hard | soft | advisory *)
                | "domain"                          (* functional domain *)

(* Optional fields *)
                | "subject"                         (* what is constrained *)
                | "predicate"                       (* action verb *)
                | "scope"                           (* module | project | org *)
                | "modality"                        (* must | should | may *)
                | "priority"                        (* 1-10, 10 = highest *)
                | "lifecycle.created_by"            (* origin reference *)
                | "lifecycle.created_at"            (* ISO date *)
                | "lifecycle.expires"               (* ISO date or "never" *)
                | "lifecycle.review_by"             (* ISO date *)

(* Enumerated values *)
Relation      ::= "must_be" | "must_not_be" | "should_be" | "should_not_be"
                | "prefers" | "requires" | "excludes" | "replaces"
Enforcement   ::= "hard" | "soft" | "advisory"
Scope         ::= "module" | "project" | "workspace" | "org"
Modality      ::= "must" | "should" | "may"
```

### Contradiction Detection Rule

Two signatures **contradict** if and only if:

```
sig_a.axis.key == sig_b.axis.key
AND sig_a.object != sig_b.object
AND sig_a.enforcement == "hard"
AND sig_b.enforcement == "hard"
AND both parent decisions have Status == "active"
```

---

## 3. Proposal Grammar

Proposals are staged mutations that require explicit approval before touching source of truth.

```ebnf
Proposal      ::= Header NewLine ProposalBody
ProposalBody  ::= ProposalType NewLine
                  ProposalTarget NewLine
                  ProposalAction NewLine
                  ProposalReason NewLine
                  ProposalStatus NewLine
                  { ProposalField NewLine }

ProposalType  ::= "Type:" Space ("new_decision" | "new_task" | "supersede"
                  | "status_change" | "merge" | "archive")
ProposalTarget ::= "Target:" Space BlockID
ProposalAction ::= "Action:" Space ActionDesc
ProposalReason ::= "Reason:" Space ReasonDesc
ProposalStatus ::= "Status:" Space ("pending" | "approved" | "applied"
                  | "rejected" | "deferred")
```

### Proposal Invariants

1. **Budget**: No scan run may generate more than `proposal_budget.per_run` proposals
2. **Daily cap**: No day may accumulate more than `proposal_budget.per_day` proposals
3. **Backlog**: Total pending proposals must not exceed `proposal_budget.backlog_limit`
4. **No duplicate**: A proposal targeting the same BlockID with the same Action must not exist in pending state
5. **Defer cooldown**: A deferred proposal may not be re-proposed for `defer_cooldown_days` days

---

## 4. Mode State Machine

```
                    ┌─────────────┐
                    │ detect_only │ ← initial state
                    └──────┬──────┘
                           │ observation_week_clean == true
                           │ explicit user action
                           ▼
                    ┌─────────────┐
                    │   propose   │
                    └──────┬──────┘
                           │ propose_weeks_clean >= 2
                           │ explicit user action
                           ▼
                    ┌─────────────┐
                    │   enforce   │
                    └─────────────┘

Transitions:
  detect_only → propose:   requires flip_gate_week1_clean == true
  propose     → enforce:   requires explicit opt-in in mem-os.json
  enforce     → propose:   any time (downgrade always safe)
  propose     → detect_only: any time (downgrade always safe)
  enforce     → detect_only: any time (downgrade always safe)

No upward transition happens automatically. All upgrades require explicit action.
```

### Mode Capabilities

| Capability | detect_only | propose | enforce |
|---|:---:|:---:|:---:|
| Run integrity scan | Yes | Yes | Yes |
| Detect contradictions | Yes | Yes | Yes |
| Detect drift | Yes | Yes | Yes |
| Generate proposals | No | Yes | Yes |
| Apply proposals (manual) | No | Yes | Yes |
| Auto-apply low-risk | No | No | Yes |
| Supersede decisions | No | No | Yes |

---

## 5. Apply Engine Atomicity Guarantees

The apply engine provides ACID-like guarantees for memory mutations.

### Transaction Protocol

```
1. PRE-CHECK
   - Validate proposal format
   - Verify target block exists
   - Check mode allows operation
   - Check budget not exceeded

2. SNAPSHOT
   - Save current state of all affected files
   - Record snapshot ID in apply receipt

3. EXECUTE
   - Perform mutation(s) on target file(s)
   - One mutation per proposal (no batching)

4. POST-CHECK
   - Run validate.sh on affected files
   - Verify no new contradictions introduced
   - Verify no structural invariant broken

5. COMMIT or ROLLBACK
   - If post-check passes: mark proposal "applied", log receipt
   - If post-check fails: restore all files from snapshot, mark proposal "failed"
```

### Atomicity Rules

1. **All-or-nothing**: Either all mutations in a proposal succeed, or none do
2. **Snapshot before mutate**: No file is modified until a snapshot is taken
3. **Post-validate**: Every apply is followed by structural validation
4. **Rollback on failure**: If validation fails, all files revert to pre-apply state
5. **Receipt required**: Every apply produces a receipt in `intelligence/AUDIT.md`
6. **No cascade**: One proposal per apply. No proposal may trigger another proposal

### Apply Receipt Format

```ebnf
Receipt       ::= Header NewLine ReceiptBody
ReceiptBody   ::= "Date:" Space ISOTimestamp NewLine
                  "Proposal:" Space BlockID NewLine
                  "Action:" Space ActionDesc NewLine
                  "Result:" Space ("applied" | "rolled_back" | "rejected") NewLine
                  "Snapshot:" Space SnapshotID NewLine
                  [ "DIFF:" NewLine DiffBlock ]
```

---

## 6. Invariant Lock Rules

These invariants MUST hold at all times. Any operation that would violate them MUST be rejected.

### Structural Invariants

| # | Invariant | Enforcement |
|---|---|---|
| S1 | Every BlockID is unique across all files | validate.sh |
| S2 | Every Decision must have Date, Status, Statement | validate.sh |
| S3 | Every Task must have Date, Status, Title | validate.sh |
| S4 | Every active Decision with priority >= 7 must have ConstraintSignature | validate.sh |
| S5 | Every ConstraintSignature must have axis.key, relation, object, enforcement, domain | validate.sh |
| S6 | Superseded decisions must have SupersededBy referencing a valid BlockID | validate.sh |
| S7 | Tasks with AlignsWith must reference existing decision BlockIDs | validate.sh |
| S8 | Daily logs are append-only — existing content must not be modified | protocol |
| S9 | Status values must be from the defined enum for each type | validate.sh |

### Semantic Invariants

| # | Invariant | Enforcement |
|---|---|---|
| M1 | No two active decisions may share the same axis.key with conflicting hard constraints | intel_scan.py |
| M2 | Decisions are never edited — they are superseded with a new decision | protocol |
| M3 | Every memory claim must have a source (no source = no claim) | protocol |
| M4 | Auto-capture writes to SIGNALS only, never to DECISIONS or TASKS | capture.py |
| M5 | Mode transitions upward require explicit user action | state machine |
| M6 | Proposals respect budget limits (per_run, per_day, backlog_limit) | intel_scan.py |

### Operational Invariants

| # | Invariant | Enforcement |
|---|---|---|
| O1 | Apply engine takes snapshot before any mutation | apply_engine.py |
| O2 | Apply engine rolls back on post-check failure | apply_engine.py |
| O3 | Every applied proposal produces an audit receipt | apply_engine.py |
| O4 | No cascade: proposals cannot trigger other proposals | apply_engine.py |
| O5 | init_workspace.py never overwrites existing files | init_workspace.py |
| O6 | validate.sh is idempotent and side-effect-free | validate.sh |

---

## 7. File Authority Map

Which scripts are authorized to write to which files:

| File/Directory | intel_scan.py | apply_engine.py | capture.py | init_workspace.py | validate.sh |
|---|:---:|:---:|:---:|:---:|:---:|
| decisions/ | Read | **Write** | Read | **Create** | Read |
| tasks/ | Read | **Write** | Read | **Create** | Read |
| entities/ | Read | **Write** | Read | **Create** | Read |
| memory/*.md | Read | Read | Read | Read | Read |
| memory/intel-state.json | **Write** | **Write** | Read | **Create** | Read |
| intelligence/CONTRADICTIONS.md | **Write** | Read | Read | **Create** | Read |
| intelligence/DRIFT.md | **Write** | Read | Read | **Create** | Read |
| intelligence/SIGNALS.md | Read | **Write** | **Write** | **Create** | Read |
| intelligence/IMPACT.md | **Write** | Read | Read | **Create** | Read |
| intelligence/AUDIT.md | Read | **Write** | Read | **Create** | Read |
| intelligence/SCAN_LOG.md | **Write** | Read | Read | **Create** | Read |
| intelligence/proposed/ | **Write** | **Write** | Read | **Create** | Read |
| intelligence/state/snapshots/ | **Write** | **Write** | Read | **Create** | Read |
| mem-os.json | Read | Read | Read | **Create** | Read |

**Key rule**: `capture.py` may only write to `intelligence/SIGNALS.md`. It has no write access to any other file.

---

## 8. Versioning

This specification follows semantic versioning:
- **Major**: Breaking changes to grammar or invariants
- **Minor**: New optional fields or capabilities
- **Patch**: Clarifications or corrections

Current version: **1.0.0**

---

*Copyright 2026 STARGA Inc. MIT License.*
