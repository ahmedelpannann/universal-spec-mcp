# Universal Spec MCP — Enhancement Roadmap

**Project:** `universal-spec-mcp`
**Author:** ahmed elpannann
**Date:** 2026-05-25
**Status:** Proposed

---

## Overview

The `universal-spec-mcp` server correctly implements the BMad four-phase workflow and provides a solid foundation of 14 MCP tools, EARS validation, task dependency management, persistent SQLite memory, and a privacy filter. The enhancements below address gaps between what the project *promises* and what it *mechanically enforces*, and add high-value capabilities that make the workflow production-grade.

Enhancements are grouped into three priority tiers:

| Priority | Count | Description |
|---|---|---|
| 🔴 Critical gap | 2 | Core promises not mechanically enforced |
| 🟡 High value | 3 | Closes material workflow gaps |
| 🔵 Strategic | 4 | Expands scope and integration |

---

## 🔴 Critical Gaps

### ENH-001 — Phase gate enforcement at server level

**Problem**
Nothing currently prevents the AI from calling `write_design` before `write_requirements` is complete, or `write_tasks` before a design exists. The project's core promise — "no code before specs" — is stated in documentation but not mechanically enforced at the tool layer.

**Proposed changes**

Add two new MCP tools:

```python
@mcp.tool()
def get_spec_phase(feature_name: str) -> str:
    """
    Returns the current phase of a feature spec.
    Phases: uninitialized → requirements → design → tasks → implementation → complete
    """

@mcp.tool()
def lock_phase(feature_name: str, phase: str) -> str:
    """
    Locks a phase as complete, enabling the next phase to begin.
    Requires that the phase's spec file exists and is non-empty.
    """
```

Modify all existing write tools to check the current phase before executing:

- `write_requirements` — requires phase: `uninitialized` or `requirements`
- `write_design` — requires phase: `requirements` (locked)
- `write_tasks` — requires phase: `design` (locked)
- `update_task_status` — requires phase: `tasks` or `implementation`

Add a `phase_state.json` file inside each `.specs/<feature-name>/` directory to persist the phase state.

**Acceptance criteria**
- Calling `write_design` on a feature with no locked requirements returns an error message explaining the phase violation.
- `get_spec_phase` returns the correct current phase after each state transition.
- Phases can only advance forward, never skip.

---

### ENH-002 — `approve_phase` tool — explicit user sign-off gate

**Problem**
Phase transitions are currently implicit — an agent decides to proceed when it judges the current phase is "done enough." There is no record of user approval and no hard stop. This undermines the auditability goal and breaks the "Think Before Code" contract.

**Proposed changes**

Add one new MCP tool:

```python
@mcp.tool()
def approve_phase(
    feature_name: str,
    phase: Literal["requirements", "design", "tasks"],
    approved_by: str = "user",
    notes: str = ""
) -> str:
    """
    Records explicit user approval of a completed phase and unlocks the next phase.
    Without this call, the next phase's write tools are blocked.
    
    Writes an approval record to .specs/<feature-name>/approvals.md.
    """
```

The approval record written to `approvals.md` must include:

```markdown
## requirements — approved

- **Approved by:** user
- **Timestamp:** 2026-05-25T14:32:00Z
- **Notes:** Requirements reviewed and confirmed with stakeholder.
```

Modify `lock_phase` (ENH-001) so it is called *by* `approve_phase` internally — the user-facing entry point is `approve_phase`, not `lock_phase` directly.

**Acceptance criteria**
- Without `approve_phase("auth", "requirements")` being called, `write_design("auth", ...)` returns a blocking error.
- `approvals.md` is written correctly on every approval.
- `get_spec_phase` reflects the approved state.

---

## 🟡 High Value

### ENH-003 — Substantive `run_hook` implementation

**Problem**
The `run_hook(hook_type, feature_name, task_id)` tool exists but returns a stub message. It does not validate pre-conditions, inject context, or capture post-task learnings. Amelia calls it out of convention with no real effect.

**Proposed changes**

**`pre_task` hook** — before starting a task, the hook should:
1. Verify all tasks listed in `depends_on` for the given `task_id` have status `completed`. If not, return a blocking error listing the incomplete dependencies.
2. Call `list_directives()` internally and inject the result into the response so Amelia has current project rules in context.
3. Call `get_memories_by_feature(feature_name)` and surface any memory entries tagged with the task's title keywords.
4. Return a structured pre-flight report.

**`post_task` hook** — after completing a task, the hook should:
1. Auto-call `add_memory` with a summary of what was implemented, tagged to the feature and task ID.
2. Check if the task description mentions a significant decision (keywords: "chose", "decided", "rejected", "instead of") and prompt the agent to consider creating an ADR.
3. Recalculate and return the updated feature progress (completed / total tasks).

**Updated signature:**

```python
@mcp.tool()
def run_hook(
    hook_type: Literal["pre_task", "post_task"],
    feature_name: str,
    task_id: str,
    implementation_summary: str = ""  # required for post_task
) -> str:
    ...
```

**Acceptance criteria**
- `pre_task` on a task with incomplete dependencies returns an error, not a success.
- `post_task` creates a memory entry searchable via `search_memory`.
- Both hooks inject directives into their response.

---

### ENH-004 — Spec versioning with diff support

**Problem**
Calling `write_requirements` on an existing spec silently overwrites it with no history, no changelog, and no way to see what changed. If an agent revises requirements mid-project, the original intent is permanently lost.

**Proposed changes**

Modify `write_spec_file` to create a versioned backup before overwriting:

```
.specs/<feature-name>/
├── requirements.md          ← current version
├── requirements.v1.md       ← first version (auto-created on first overwrite)
├── requirements.v2.md       ← second version, etc.
└── requirements.changelog.md ← append-only log of changes
```

The changelog entry format:

```markdown
## v2 — 2026-05-25T15:10:00Z

- Added REQ-005 (rate limiting requirement)
- Modified REQ-002: changed priority from "should" to "must"
- Reason: stakeholder review feedback
```

Add two new MCP tools:

```python
@mcp.tool()
def spec_history(feature_name: str, spec_type: Literal["requirements", "design", "tasks"]) -> str:
    """Lists all saved versions of a spec file with timestamps."""

@mcp.tool()
def diff_spec(
    feature_name: str,
    spec_type: Literal["requirements", "design", "tasks"],
    version_a: str = "current",
    version_b: str = "v1"
) -> str:
    """Returns a line-diff between two versions of a spec file."""
```

**Acceptance criteria**
- On a second call to `write_requirements`, a `.v1.md` backup is created automatically.
- `spec_history` lists all available versions with their timestamps.
- `diff_spec("auth", "requirements", "current", "v1")` returns a readable diff.

---

### ENH-005 — Requirements traceability matrix

**Problem**
There is no mechanism to verify that every requirement (REQ-xxx) has a corresponding design component and at least one implementation task. A spec can be "complete" with requirements that are never designed or built.

**Proposed changes**

Add one new MCP tool:

```python
@mcp.tool()
def check_coverage(feature_name: str) -> str:
    """
    Runs a traceability check across all three spec files:
    1. Extracts all REQ-xxx IDs from requirements.md
    2. Checks each REQ-xxx is referenced in design.md
    3. Checks each REQ-xxx is referenced in at least one task in tasks.md
    4. Checks each TASK-xxx references at least one REQ-xxx
    
    Returns a coverage report with pass/warn/fail status per requirement.
    """
```

Example output:

```
Coverage Report — auth
───────────────────────────────────────────
REQ-001  ✓ In design  ✓ In tasks (TASK-001, TASK-002)
REQ-002  ✓ In design  ✗ No task references this requirement
REQ-003  ✗ Not found in design.md
TASK-005  ✗ No requirement linkage found

Summary: 1/3 requirements fully covered · 2 gaps found
```

This tool should be called by John (bmad-pm) at the end of Phase 3 as a mandatory pre-condition for `approve_phase("feature", "tasks")`.

**Update `.bob/rules/spec-workflow.md`** to add `check_coverage` as a required step at the end of Phase 3.

**Acceptance criteria**
- `check_coverage` correctly identifies requirements with no design reference.
- `check_coverage` correctly identifies requirements with no task.
- `check_coverage` correctly identifies tasks with no requirement linkage.
- A feature with 100% coverage returns a clear all-pass summary.

---

## 🔵 Strategic Additions

### ENH-006 — Task estimation rollup and burndown summary

**Problem**
Tasks have an `estimated_hours` field but there is no summary tool. Amelia must read through the entire `tasks.md` to understand progress, and there is no way for a TPM (or an orchestrating agent) to get a quick status view.

**Proposed changes**

Add one new MCP tool:

```python
@mcp.tool()
def get_feature_summary(feature_name: str) -> str:
    """
    Returns a progress summary for a feature:
    - Total estimated hours
    - Hours completed (sum of estimated_hours for completed tasks)
    - Hours remaining
    - % complete by task count and by hours
    - List of blocked tasks with their blocker task IDs
    - Current phase and approval status
    """
```

Example output:

```
Feature Summary — risk-assessment
───────────────────────────────────
Phase:      implementation (tasks approved 2026-05-24)
Progress:   5 / 12 tasks complete (42%)
Hours:      18.5h done / 26.0h remaining (44.5h total)
Blocked:    TASK-007 blocked by TASK-006 (in_progress)
Next up:    TASK-008 — Implement scoring matrix
```

**Acceptance criteria**
- Summary reflects real-time task status, not a cached snapshot.
- Blocked tasks and their blockers are correctly identified.
- Hours calculation correctly sums only `completed` tasks for "done."

---

### ENH-007 — Cross-feature dependency tracking

**Problem**
Tasks can only depend on other tasks within the same feature. In multi-epic programs (e.g. IAOS where risk-sensing depends on risk-assessment being complete), there is no way to express or enforce inter-feature dependencies.

**Proposed changes**

Add two new MCP tools:

```python
@mcp.tool()
def add_feature_dependency(feature_name: str, depends_on_feature: str, notes: str = "") -> str:
    """
    Records that feature_name cannot begin implementation until depends_on_feature
    reaches the 'complete' phase. Stored in .specs/.system/feature_graph.json.
    """

@mcp.tool()
def get_feature_graph() -> str:
    """
    Returns the full inter-feature dependency graph showing:
    - All features and their current phases
    - Dependency edges between features
    - Which features are blocked by incomplete dependencies
    - Critical path estimate based on estimated_hours
    """
```

Modify `approve_phase(feature, "requirements")` to check that all `depends_on_feature` entries have reached the `complete` phase before allowing the current feature to proceed to implementation.

**Acceptance criteria**
- `add_feature_dependency("risk-sensing", "risk-assessment")` persists to `feature_graph.json`.
- `get_feature_graph` returns a human-readable dependency map.
- Attempting to start implementation on a feature with an incomplete dependency returns a blocking error.

---

### ENH-008 — Spec health check tool

**Problem**
There is no single command that validates the entire state of a feature (or all features) — phase gates, EARS compliance, task dependency validity, coverage, and directive adherence. This makes it impossible to use the MCP server as a CI gate.

**Proposed changes**

Add one new MCP tool:

```python
@mcp.tool()
def health_check(feature_name: str = None) -> str:
    """
    Runs all validations for one feature (or all features if feature_name is None):
    1. EARS compliance on all requirements
    2. Task dependency graph validity (no circular deps, no missing refs)
    3. Requirements coverage (ENH-005)
    4. Phase gate status (which phases are approved)
    5. Cross-feature dependency status (ENH-007)
    6. Privacy filter check (no redacted tokens still present)
    
    Returns a green / amber / red summary per feature.
    """
```

Example output:

```
Health Check — all features
───────────────────────────────────────────
risk-assessment   🟢 Healthy   (phase: complete, coverage: 100%)
risk-sensing      🟡 Warning   (phase: design, REQ-004 has no task)
user-auth         🔴 Error     (phase: requirements, EARS violation in REQ-002)

Overall: 1 healthy · 1 warning · 1 error
```

This tool is the intended integration point for a CI/CD pre-merge check.

**Acceptance criteria**
- `health_check()` (no argument) checks all features and returns a summary.
- `health_check("risk-sensing")` returns only that feature's report.
- Each check category reports independently — a failing coverage check does not suppress an EARS violation report.

---

### ENH-009 — Semantic spec search via memory integration

**Problem**
`search_specs(query)` performs a basic file-content scan. It does not leverage the SQLite FTS5 memory store, so Winston searching for past decisions about "rate limiting" will miss memory entries tagged "rate limiting" that are stored from other feature sessions.

**Proposed changes**

Modify `search_specs` to accept an optional flag:

```python
@mcp.tool()
def search_specs(query: str, include_memories: bool = True) -> str:
    """
    Searches across:
    1. All spec files in .specs/ (requirements, design, tasks) — existing behaviour
    2. The memory store (SQLite FTS5) — new when include_memories=True
    
    Returns combined results grouped by source, ranked by relevance.
    """
```

Result format:

```
Search results for "rate limiting"
───────────────────────────────────
From spec files (2 matches):
  risk-assessment/design.md — "rate limiting middleware applied at gateway layer"
  user-auth/requirements.md — "REQ-007: THE system SHALL enforce rate limiting..."

From memory store (1 match):
  [MEM-014] risk-assessment · architecture — "Decided to use token bucket algorithm 
   for rate limiting. Rejected leaky bucket due to burst allowance requirements."
```

**Acceptance criteria**
- `search_specs("rate limiting")` returns both file matches and memory matches.
- `search_specs("rate limiting", include_memories=False)` returns only file matches (backward compatible).
- Results are grouped and clearly labelled by source type.

---

## Implementation order (recommended)

| Order | Enhancement | Effort | Dependency |
|---|---|---|---|
| 1 | ENH-001 Phase gate enforcement | Medium | None |
| 2 | ENH-002 approve_phase tool | Small | ENH-001 |
| 3 | ENH-003 Substantive run_hook | Medium | None |
| 4 | ENH-005 Traceability matrix | Medium | None |
| 5 | ENH-004 Spec versioning | Medium | None |
| 6 | ENH-006 Estimation rollup | Small | None |
| 7 | ENH-008 Health check tool | Medium | ENH-001, ENH-005 |
| 8 | ENH-007 Cross-feature deps | Medium | ENH-001 |
| 9 | ENH-009 Semantic search | Small | None |

---

## Files to modify

| File | Enhancements |
|---|---|
| `src/universal_spec_mcp/server.py` | ENH-001, ENH-002, ENH-003, ENH-004, ENH-005, ENH-006, ENH-007, ENH-008, ENH-009 |
| `src/universal_spec_mcp/directive_store.py` | ENH-003 (inject directives in pre_task) |
| `src/universal_spec_mcp/memory_store.py` | ENH-003, ENH-009 |
| `.bob/rules/spec-workflow.md` | ENH-002, ENH-005 (add approve_phase and check_coverage steps) |
| `.bob/skills/bmad-pm.md` | ENH-005 (John must run check_coverage before approving tasks) |
| `.bob/skills/bmad-dev.md` | ENH-003 (Amelia must call run_hook pre/post each task) |
| `tests/test_server.py` | All enhancements |

---

*Enhancement roadmap v1.0 — Universal Spec MCP Server*
