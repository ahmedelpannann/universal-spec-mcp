# Universal Spec MCP — Full Work Backlog

**Project:** `universal-spec-mcp`
**Author:** ahmed elpannann
**Evaluated:** 2026-05-25
**Codebase state:** v1 foundation — 48/48 tests passing, no enhancements implemented

---

## How to read this document

Work is split into two parts:

- **Part 1 — Bug fixes and code issues** — things broken or wrong in the current code. Do these first; they affect correctness.
- **Part 2 — Enhancements** — new capabilities that make the workflow production-grade.

Each item has a priority, effort estimate, exact file(s) to change, and a precise description of the fix or implementation.

### Priority key

| Symbol | Meaning |
|---|---|
| 🔴 | Must fix — correctness or contract broken |
| 🟡 | Should fix — material gap or bad pattern |
| 🔵 | Nice to fix — polish or future-proofing |

### Effort key

| Symbol | Meaning |
|---|---|
| S | Small — under 1 hour |
| M | Medium — 1–4 hours |
| L | Large — half day or more |

---

## Part 1 — Bug fixes and code issues

### BUG-001 — EARS regex rejects valid requirements

**Priority:** 🔴 | **Effort:** S | **File:** `src/universal_spec_mcp/server.py` line ~43

**What is broken**

The EARS validation regex requires at least one character *after* `SHALL`:

```python
ears_pattern = r'(?:WHEN\s+.+?\s+)?(?:WHILE\s+.+?\s+)?THE\s+.+?\s+SHALL\s+.+'
```

`SHALL\s+.+` means: one or more whitespace after SHALL, then one or more characters. Any requirement ending with `SHALL` and nothing after it fails. This breaks stub requirements during drafting and any minimal form like `THE system SHALL authenticate`.

**Confirmed by running:**
```
Match=False: "THE system SHALL"
Match=False: "WHEN user logs in THE system SHALL"
Match=True:  "THE system SHALL authenticate"
```

**Fix**

Change line ~43 in `server.py`:

```python
# Before
ears_pattern = r'(?:WHEN\s+.+?\s+)?(?:WHILE\s+.+?\s+)?THE\s+.+?\s+SHALL\s+.+'

# After
ears_pattern = r'(?:WHEN\s+.+?\s+)?(?:WHILE\s+.+?\s+)?THE\s+.+?\s+SHALL(?:\s+.+)?'
```

**Tests to add in `tests/test_server.py`** (`TestRequirementModel`):

```python
def test_ears_minimal_valid(self):
    """Minimal valid EARS form — SHALL with no response text."""
    req = Requirement(id="REQ-001", text="THE system SHALL authenticate")
    assert req.text == "THE system SHALL authenticate"

def test_ears_with_trigger_no_response(self):
    """EARS with WHEN trigger and no response text."""
    req = Requirement(id="REQ-001", text="WHEN user logs in THE system SHALL verify credentials")
    assert req.text is not None
```

---

### BUG-002 — Circular task dependencies not detected

**Priority:** 🔴 | **Effort:** S | **File:** `src/universal_spec_mcp/server.py` line ~110

**What is broken**

`validate_task_dependencies` checks that dependency IDs reference existing tasks but does not detect cycles. This passes silently:

```python
TasksDoc(feature_name="test", tasks=[
    {"id": "TASK-001", "title": "A", "description": "A", "depends_on": ["TASK-002"]},
    {"id": "TASK-002", "title": "B", "description": "B", "depends_on": ["TASK-001"]},
])
```

Amelia selecting a task will never find one with all dependencies complete, causing an infinite loop.

**Fix**

Add a cycle detector using Kahn's algorithm inside `validate_task_dependencies`, after the existing checks:

```python
@field_validator('tasks')
@classmethod
def validate_task_dependencies(cls, tasks: list[Task]) -> list[Task]:
    task_ids = {task.id for task in tasks}

    # Existing checks
    if len(task_ids) != len(tasks):
        raise ValueError("Duplicate task IDs found")
    for task in tasks:
        for dep_id in task.depends_on:
            if dep_id not in task_ids:
                raise ValueError(f"Task {task.id} depends on non-existent task {dep_id}")

    # NEW: Cycle detection via Kahn's algorithm
    in_degree = {task.id: 0 for task in tasks}
    for task in tasks:
        for dep_id in task.depends_on:
            in_degree[task.id] += 1

    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    visited = 0
    while queue:
        current = queue.pop(0)
        visited += 1
        for task in tasks:
            if current in task.depends_on:
                in_degree[task.id] -= 1
                if in_degree[task.id] == 0:
                    queue.append(task.id)

    if visited != len(tasks):
        raise ValueError(
            "Circular dependency detected in tasks. "
            "Tasks must form a directed acyclic graph."
        )

    return tasks
```

**Tests to add in `tests/test_server.py`** (`TestTasksDoc`):

```python
def test_circular_dependency_rejected(self):
    """Test that circular task dependencies are rejected."""
    with pytest.raises(ValueError, match="Circular dependency"):
        TasksDoc(
            feature_name="user-auth",
            tasks=[
                {"id": "TASK-001", "title": "A", "description": "A", "depends_on": ["TASK-002"]},
                {"id": "TASK-002", "title": "B", "description": "B", "depends_on": ["TASK-001"]},
            ]
        )

def test_three_way_circular_dependency_rejected(self):
    """Test that three-way circular dependencies are also caught."""
    with pytest.raises(ValueError, match="Circular dependency"):
        TasksDoc(
            feature_name="user-auth",
            tasks=[
                {"id": "TASK-001", "title": "A", "description": "A", "depends_on": ["TASK-003"]},
                {"id": "TASK-002", "title": "B", "description": "B", "depends_on": ["TASK-001"]},
                {"id": "TASK-003", "title": "C", "description": "C", "depends_on": ["TASK-002"]},
            ]
        )
```

---

### BUG-003 — update_task_status has no file lock — race condition

**Priority:** 🔴 | **Effort:** S | **File:** `src/universal_spec_mcp/server.py` line ~310

**What is broken**

`update_task_status` reads `tasks.md`, modifies it in memory, and writes it back with no lock. In a multi-agent scenario two concurrent calls will silently drop one update. The `DirectiveStore` and `MemoryStore` both use `threading.Lock` correctly — the same pattern is missing here.

**Fix**

Add a module-level lock and use it in `update_task_status`:

```python
# Add near top of server.py, after store initializations
import threading
_file_lock = threading.Lock()
```

Then wrap the read-modify-write in `update_task_status`:

```python
with _file_lock:
    content = read_spec_file(feature_name, "tasks")
    # ... regex update ...
    file_path.write_text(privacy_filter.filter(new_content), encoding='utf-8')
```

---

### ISSUE-001 — ExtraArgStripMiddleware is dead code

**Priority:** 🟡 | **Effort:** S | **File:** `src/universal_spec_mcp/server.py` line ~130

**What is wrong**

`ExtraArgStripMiddleware` is defined but never registered with FastMCP. The comment says the actual workaround is `ConfigDict(extra='ignore')` on the Pydantic models — which is correct. The class creates confusion for anyone reading the code.

**Fix — option A (preferred):** Delete the entire class and its comment block.

**Fix — option B:** Replace with an explanatory comment:

```python
# Extra argument handling: we rely on ConfigDict(extra='ignore') on all Pydantic
# models rather than middleware, because FastMCP validates args before any
# middleware can strip them. No middleware registration needed.
```

---

### ISSUE-002 — SPECS_DIR is hardcoded — not configurable

**Priority:** 🟡 | **Effort:** S | **File:** `src/universal_spec_mcp/server.py` line ~25

**What is wrong**

```python
SPECS_DIR = Path(".specs")
```

This is resolved relative to the process working directory at import time. Two projects on the same machine will collide if the server is run from the same directory. There is no way to override it without monkey-patching.

**Fix**

```python
import os

SPECS_DIR = Path(os.environ.get("UNIVERSAL_SPEC_DIR", ".specs"))
```

Update the `pyproject.toml` description and README to document this env var.

**Tests to add in `tests/test_server.py`:**

```python
def test_specs_dir_env_override(self, tmp_path, monkeypatch):
    """Test that UNIVERSAL_SPEC_DIR env var overrides the default."""
    custom_dir = tmp_path / "custom-specs"
    monkeypatch.setenv("UNIVERSAL_SPEC_DIR", str(custom_dir))
    # Re-import would pick up the new value; test the pattern with monkeypatch
    import universal_spec_mcp.server as srv
    monkeypatch.setattr(srv, 'SPECS_DIR', custom_dir)
    result = srv.initialize_spec("test-feature", "desc")
    assert custom_dir.exists()
```

---

### ISSUE-003 — Directive injection appended to every tool response

**Priority:** 🟡 | **Effort:** M | **File:** `src/universal_spec_mcp/server.py` — `inject_directives()` and all callers

**What is wrong**

Every tool response ends with the full directives block appended. With 20 directives (~1,000 chars each call) across a 30-call workflow, this adds ~30,000 characters of repeated context — a significant context window cost with no benefit after the first call.

**Fix**

Change `inject_directives` to accept a `category` filter, and only append if the calling tool is in a relevant phase:

```python
def inject_directives(response: str, category: str | None = None) -> str:
    """Inject project directives, optionally filtered by category."""
    directives_text = directive_store.format_for_context(category=category)
    if directives_text:
        return f"{response}\n\n{directives_text}"
    return response
```

Update `DirectiveStore.format_for_context()` to accept an optional `category` parameter.

Then update each tool call to pass the relevant category:

```python
# write_requirements — inject architecture + testing directives
return inject_directives(response, category="requirements")

# write_design — inject architecture directives only
return inject_directives(response, category="architecture")

# write_tasks — inject testing + general directives
return inject_directives(response, category="testing")
```

---

### ISSUE-004 — update_task_status uses fragile regex on markdown

**Priority:** 🟡 | **Effort:** M | **File:** `src/universal_spec_mcp/server.py` line ~315

**What is wrong**

The current implementation:

```python
pattern = rf"(### {re.escape(task_id)}:.*?\n\*\*Status:\*\*\s+)\w+"
new_content = re.sub(pattern, rf"\1{status}", content)
```

This is fragile. If the markdown template ever changes, if a task title spans multiple lines, or if future fields are added between the heading and the status line, this silently fails (returns same content, then hits the "not found" branch).

**Fix**

Maintain a `tasks.json` alongside `tasks.md` as the source of truth for machine updates:

```python
def write_tasks_json(feature_name: str, doc: TasksDoc) -> None:
    """Write tasks to a machine-readable JSON file."""
    feature_dir = get_feature_dir(feature_name)
    json_path = feature_dir / "tasks.json"
    data = [task.model_dump() for task in doc.tasks]
    json_path.write_text(json.dumps(data, indent=2), encoding='utf-8')

def read_tasks_json(feature_name: str) -> list[dict]:
    """Read tasks from the JSON source of truth."""
    feature_dir = get_feature_dir(feature_name)
    json_path = feature_dir / "tasks.json"
    if not json_path.exists():
        raise FileNotFoundError(f"tasks.json not found for {feature_name}")
    return json.loads(json_path.read_text(encoding='utf-8'))
```

Update `write_tasks` to write both `.md` and `.json`. Update `update_task_status` to modify `tasks.json`, then regenerate `tasks.md` from it. Update `read_spec("tasks")` to still serve the markdown.

---

### ISSUE-005 — list_specs hides initialized-but-empty features

**Priority:** 🔵 | **Effort:** S | **File:** `src/universal_spec_mcp/server.py` line ~360

**What is wrong**

A feature that has been `initialize_spec`-ed but has no spec files yet (only a `README.md`) does not appear in `list_specs()` output. The agent cannot tell whether the feature was never created or simply has no specs written yet.

**Fix**

```python
# Current
if specs:
    features.append(f"- {item.name}: {', '.join(specs)}")

# Fixed — show all features, even with no specs
if specs:
    features.append(f"- {item.name}: {', '.join(specs)}")
else:
    features.append(f"- {item.name}: (initialized, no specs yet)")
```

---

### ISSUE-006 — search_specs has no pagination

**Priority:** 🔵 | **Effort:** S | **File:** `src/universal_spec_mcp/server.py` line ~385

**What is wrong**

`search_specs` hard-caps at 10 results. In a large project with many features, results beyond 10 are silently discarded. There is no way to retrieve them.

**Fix**

Add `limit` and `offset` parameters:

```python
@mcp.tool()
def search_specs(query: str, limit: int = 10, offset: int = 0) -> str:
    """
    Search across all specification documents.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return (default 10)
        offset: Number of results to skip for pagination (default 0)
    """
    # ... existing search logic ...
    paginated = results[offset:offset + limit]
    total = len(results)
    
    response = f"## Search Results for '{query}'\n"
    response += f"Showing {offset + 1}–{offset + len(paginated)} of {total}\n\n"
    response += "\n".join(paginated)
    if total > offset + limit:
        response += f"\n\nUse offset={offset + limit} to see more results."
    return inject_directives(response)
```

---

### ISSUE-007 — import json inside methods in memory_store.py

**Priority:** 🔵 | **Effort:** S | **File:** `src/universal_spec_mcp/memory_store.py`

**What is wrong**

`import json` appears inside four method bodies. Python caches imports so there is no performance penalty, but it is non-idiomatic and makes the dependency non-obvious.

**Fix**

Remove the four inline `import json` statements. Add `import json` at the top of the file alongside the other imports.

---

## Part 2 — Enhancements

### ENH-001 — Phase gate enforcement at server level

**Priority:** 🔴 | **Effort:** M | **Files:** `server.py`, `.specs/<feature>/phase_state.json`

**What to build**

Nothing currently stops the AI from calling `write_design` before `write_requirements` is complete. The core promise of the project — "no code before specs" — is documented but not enforced.

**New tools to add:**

```python
@mcp.tool()
def get_spec_phase(feature_name: str) -> str:
    """
    Returns the current workflow phase of a feature.
    
    Phases: uninitialized → requirements → design → tasks → implementation → complete
    
    Args:
        feature_name: Name of the feature
    Returns:
        Current phase name and what is allowed next
    """

@mcp.tool()
def lock_phase(feature_name: str, phase: str) -> str:
    """
    Marks a phase as complete, enabling the next phase to begin.
    Called internally by approve_phase (ENH-002).
    
    Args:
        feature_name: Name of the feature
        phase: Phase to lock (requirements, design, tasks, implementation)
    Returns:
        Confirmation and next allowed action
    """
```

**Phase state file** — write `.specs/<feature-name>/phase_state.json`:

```json
{
  "current_phase": "requirements",
  "locked_phases": ["requirements"],
  "last_updated": "2026-05-25T14:32:00Z"
}
```

**Gate logic to add to existing write tools:**

```python
# At the top of write_design():
phase = _get_phase(feature_name)
if "requirements" not in phase.get("locked_phases", []):
    return inject_directives(
        f"✗ Cannot write design for '{feature_name}': "
        f"requirements phase is not yet locked. "
        f"Complete and approve requirements first (use approve_phase)."
    )

# At the top of write_tasks():
if "design" not in phase.get("locked_phases", []):
    return inject_directives(
        f"✗ Cannot write tasks for '{feature_name}': "
        f"design phase is not yet locked."
    )

# At the top of update_task_status():
if "tasks" not in phase.get("locked_phases", []):
    return inject_directives(
        f"✗ Cannot update task status for '{feature_name}': "
        f"tasks phase is not yet approved."
    )
```

**Tests to add:**

```python
def test_phase_gate_blocks_write_design_before_requirements(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, write_design
    initialize_spec("test", "desc")
    result = write_design("test", "arch", [
        {"id": "ADR-001", "title": "T", "context": "C", "decision": "D", "consequences": "Q"}
    ])
    assert "✗" in result
    assert "requirements" in result.lower()

def test_phase_gate_allows_write_design_after_approval(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, write_requirements, approve_phase, write_design
    initialize_spec("test", "desc")
    write_requirements("test", "desc", [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}])
    approve_phase("test", "requirements")
    result = write_design("test", "arch", [
        {"id": "ADR-001", "title": "T", "context": "C", "decision": "D", "consequences": "Q"}
    ])
    assert "✓" in result
```

---

### ENH-002 — approve_phase tool — explicit user sign-off gate

**Priority:** 🔴 | **Effort:** S | **Files:** `server.py`, `.specs/<feature>/approvals.md`

**Depends on:** ENH-001

**What to build**

Phase transitions are currently implicit — agents proceed when they decide they are done. There is no record of user approval and no hard stop.

**New tool to add:**

```python
@mcp.tool()
def approve_phase(
    feature_name: str,
    phase: Literal["requirements", "design", "tasks"],
    approved_by: str = "user",
    notes: str = ""
) -> str:
    """
    Records explicit approval of a completed phase and unlocks the next phase.
    
    Without calling this, the next phase's write tools are blocked.
    Writes an approval record to .specs/<feature-name>/approvals.md.
    
    Args:
        feature_name: Name of the feature
        phase: Phase being approved (requirements, design, or tasks)
        approved_by: Who is approving (default: 'user')
        notes: Optional notes about the approval
    Returns:
        Confirmation and next allowed action
    """
```

**Approval record written to `approvals.md`:**

```markdown
## requirements — approved

- **Approved by:** user
- **Timestamp:** 2026-05-25T14:32:00Z
- **Notes:** Requirements reviewed and confirmed with stakeholder.
```

`approve_phase` calls `lock_phase` (ENH-001) internally. The user-facing entry point is `approve_phase`, not `lock_phase` directly.

**Tests to add:**

```python
def test_approve_phase_creates_approval_record(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, write_requirements, approve_phase
    initialize_spec("test", "desc")
    write_requirements("test", "desc", [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}])
    result = approve_phase("test", "requirements", "ahmed", "looks good")
    assert "✓" in result
    approval_file = temp_specs_dir / "test" / "approvals.md"
    assert approval_file.exists()
    content = approval_file.read_text()
    assert "requirements" in content
    assert "ahmed" in content

def test_approve_phase_blocks_wrong_phase_order(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, approve_phase
    initialize_spec("test", "desc")
    result = approve_phase("test", "design")  # Can't approve design before requirements
    assert "✗" in result
```

---

### ENH-003 — Substantive run_hook implementation

**Priority:** 🟡 | **Effort:** M | **File:** `server.py`

**What to build**

`run_hook` currently returns a timestamp stub. It must do real work.

**Updated tool signature:**

```python
@mcp.tool()
def run_hook(
    hook_type: Literal["pre_task", "post_task"],
    feature_name: str,
    task_id: str,
    implementation_summary: str = ""
) -> str:
    """
    Run a lifecycle hook for task execution.
    
    pre_task: Verifies dependencies are complete, injects directives and
              relevant memories. Blocks if dependencies are incomplete.
    post_task: Stores a memory of what was done, calculates progress,
               flags if an ADR-worthy decision was made.
    
    Args:
        hook_type: pre_task or post_task
        feature_name: Name of the feature
        task_id: ID of the task
        implementation_summary: What was done (required for post_task)
    """
```

**pre_task logic:**

1. Read `tasks.json` (from ISSUE-004 fix) or parse `tasks.md`.
2. Find the task by `task_id`. If not found, return error.
3. Check each `depends_on` task ID — if any has status other than `completed`, return a blocking error listing the incomplete tasks by name.
4. Call `list_directives()` and include the result in the response.
5. Call `get_memories_by_feature(feature_name)` and surface any entries whose content overlaps with the task title keywords.
6. Return a structured pre-flight report: dependency check ✓, directives appended, relevant memories surfaced.

**post_task logic:**

1. Call `add_memory(feature_name, implementation_summary, memory_type="progress", metadata={"task_id": task_id})`.
2. Scan `implementation_summary` for decision keywords (`chose`, `decided`, `rejected`, `instead of`). If found, add a line: "Consider documenting this as an ADR in write_design."
3. Read task progress (how many completed / total) and include in response.

**Tests to add:**

```python
def test_pre_task_hook_blocks_on_incomplete_dependency(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, write_tasks, run_hook
    initialize_spec("test", "desc")
    write_tasks("test", [
        {"id": "TASK-001", "title": "First", "description": "D"},
        {"id": "TASK-002", "title": "Second", "description": "D", "depends_on": ["TASK-001"]},
    ])
    result = run_hook("pre_task", "test", "TASK-002")
    assert "TASK-001" in result
    assert "✗" in result or "blocked" in result.lower() or "incomplete" in result.lower()

def test_post_task_hook_creates_memory(self, temp_specs_dir, temp_memory_store):
    from universal_spec_mcp.server import initialize_spec, write_tasks, run_hook
    initialize_spec("test", "desc")
    write_tasks("test", [{"id": "TASK-001", "title": "First", "description": "D"}])
    run_hook("post_task", "test", "TASK-001", "Implemented the login endpoint using JWT")
    memories = temp_memory_store.get_memories_by_feature("test")
    assert any("TASK-001" in m["content"] for m in memories)
```

---

### ENH-004 — Spec versioning with diff support

**Priority:** 🟡 | **Effort:** M | **Files:** `server.py`

**What to build**

Calling `write_requirements` on an existing spec silently overwrites it with no history. Every overwrite should create a versioned backup.

**Modify `write_spec_file`** to create a backup before overwriting:

```python
def write_spec_file(feature_name, spec_type, content):
    feature_dir = get_feature_dir(feature_name)
    feature_dir.mkdir(parents=True, exist_ok=True)
    file_path = feature_dir / f"{spec_type}.md"

    if file_path.exists():
        # Find next version number
        existing_versions = list(feature_dir.glob(f"{spec_type}.v*.md"))
        next_version = len(existing_versions) + 1
        backup_path = feature_dir / f"{spec_type}.v{next_version}.md"
        file_path.rename(backup_path)

        # Append to changelog
        changelog = feature_dir / f"{spec_type}.changelog.md"
        entry = (
            f"\n## v{next_version + 1} — {datetime.utcnow().isoformat()}Z\n\n"
            f"Previous version saved as {backup_path.name}\n"
        )
        with open(changelog, 'a', encoding='utf-8') as f:
            f.write(entry)

    filtered_content = privacy_filter.filter(content)
    file_path.write_text(filtered_content, encoding='utf-8')
```

**New tools to add:**

```python
@mcp.tool()
def spec_history(
    feature_name: str,
    spec_type: Literal["requirements", "design", "tasks"]
) -> str:
    """
    Lists all saved versions of a spec file with timestamps.
    
    Args:
        feature_name: Name of the feature
        spec_type: Type of spec (requirements, design, or tasks)
    Returns:
        List of versions with file sizes and modification times
    """

@mcp.tool()
def diff_spec(
    feature_name: str,
    spec_type: Literal["requirements", "design", "tasks"],
    version_a: str = "current",
    version_b: str = "v1"
) -> str:
    """
    Returns a line-diff between two versions of a spec file.
    
    Args:
        feature_name: Name of the feature
        spec_type: Type of spec
        version_a: First version (default: current)
        version_b: Second version (default: v1)
    Returns:
        Unified diff of the two versions
    """
```

**Tests to add:**

```python
def test_write_requirements_creates_backup_on_overwrite(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, write_requirements
    initialize_spec("test", "desc")
    write_requirements("test", "desc", [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}])
    write_requirements("test", "desc", [{"id": "REQ-001", "text": "THE system SHALL authenticate", "priority": "must"}])
    assert (temp_specs_dir / "test" / "requirements.v1.md").exists()

def test_spec_history_lists_versions(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, write_requirements, spec_history
    initialize_spec("test", "desc")
    write_requirements("test", "desc", [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}])
    write_requirements("test", "desc", [{"id": "REQ-001", "text": "THE system SHALL auth", "priority": "must"}])
    result = spec_history("test", "requirements")
    assert "v1" in result
```

---

### ENH-005 — Requirements traceability matrix

**Priority:** 🟡 | **Effort:** M | **File:** `server.py`

**What to build**

There is no way to verify that every requirement has a corresponding design component and at least one implementation task. Specs can be "complete" with requirements that are never designed or built.

**New tool to add:**

```python
@mcp.tool()
def check_coverage(feature_name: str) -> str:
    """
    Runs a requirements traceability check across all three spec files.
    
    Checks:
    1. Each REQ-xxx in requirements.md appears in design.md
    2. Each REQ-xxx in requirements.md appears in at least one task in tasks.md
    3. Each TASK-xxx in tasks.md references at least one REQ-xxx
    
    Args:
        feature_name: Name of the feature
    Returns:
        Coverage report with pass/warn/fail per requirement
    """
```

**Implementation logic:**

```python
import re as _re

def _extract_ids(content: str, prefix: str) -> set[str]:
    return set(_re.findall(rf'{prefix}-\d+', content))

def check_coverage_impl(feature_name: str) -> str:
    try:
        req_content = read_spec_file(feature_name, "requirements")
        design_content = read_spec_file(feature_name, "design")
        tasks_content = read_spec_file(feature_name, "tasks")
    except FileNotFoundError as e:
        return f"✗ Cannot run coverage check: {e}"

    req_ids = _extract_ids(req_content, "REQ")
    task_ids = _extract_ids(tasks_content, "TASK")

    lines = [f"## Coverage Report — {feature_name}\n"]
    gaps = 0

    for req_id in sorted(req_ids):
        in_design = req_id in design_content
        in_tasks = req_id in tasks_content
        status = "✓" if (in_design and in_tasks) else "✗"
        if not (in_design and in_tasks):
            gaps += 1
        design_mark = "✓ In design" if in_design else "✗ Not in design"
        tasks_mark = "✓ In tasks" if in_tasks else "✗ No task references"
        lines.append(f"{status} {req_id}  {design_mark}  {tasks_mark}")

    for task_id in sorted(task_ids):
        has_req = any(req_id in tasks_content for req_id in req_ids
                      if req_id in read_spec_file(feature_name, "tasks"))
        # Simplified: check if any REQ-xxx appears near this task's section
        task_section = _re.search(
            rf'### {task_id}:.*?(?=### TASK-|\Z)', tasks_content, _re.DOTALL
        )
        if task_section:
            section_text = task_section.group()
            has_req_ref = bool(_re.search(r'REQ-\d+', section_text))
            if not has_req_ref:
                gaps += 1
                lines.append(f"✗ {task_id}  No requirement linkage found")

    covered = len(req_ids) - gaps
    lines.append(f"\nSummary: {covered}/{len(req_ids)} requirements fully covered · {gaps} gap(s) found")
    return inject_directives("\n".join(lines))
```

**Update `.bob/skills/bmad-pm.md`** — add `check_coverage` as a required step before handing off to Amelia.

**Update `.bob/rules/spec-workflow.md`** — add `check_coverage` as mandatory at end of Phase 3.

**Tests to add:**

```python
def test_check_coverage_detects_requirement_not_in_design(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, write_requirements, write_design, write_tasks, check_coverage
    initialize_spec("test", "desc")
    write_requirements("test", "desc", [
        {"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"},
        {"id": "REQ-002", "text": "THE system SHALL scale", "priority": "must"},
    ])
    write_design("test", "arch with REQ-001 only", [
        {"id": "ADR-001", "title": "T", "context": "REQ-001", "decision": "D", "consequences": "Q"}
    ])
    write_tasks("test", [{"id": "TASK-001", "title": "X", "description": "Covers REQ-001 REQ-002"}])
    result = check_coverage("test")
    assert "REQ-002" in result
    assert "Not in design" in result
```

---

### ENH-006 — Task estimation rollup and burndown summary

**Priority:** 🔵 | **Effort:** S | **File:** `server.py`

**What to build**

Tasks have `estimated_hours` but there is no summary tool. A TPM needs a quick status view without reading through all of `tasks.md`.

**New tool to add:**

```python
@mcp.tool()
def get_feature_summary(feature_name: str) -> str:
    """
    Returns a progress summary for a feature.
    
    Includes: total estimated hours, hours completed, hours remaining,
    % complete by task count and by hours, blocked tasks with blockers,
    current phase and approval status.
    
    Args:
        feature_name: Name of the feature
    Returns:
        Formatted progress summary
    """
```

**Example output:**

```
Feature Summary — risk-assessment
───────────────────────────────────
Phase:      implementation (tasks approved 2026-05-24)
Progress:   5 / 12 tasks complete (42%)
Hours:      18.5h done / 26.0h remaining (44.5h total)
Blocked:    TASK-007 blocked by TASK-006 (in_progress)
Next up:    TASK-008 — Implement scoring matrix
```

**Implementation approach:** Read `tasks.json` (from ISSUE-004), aggregate statuses and hours. Find blocked tasks by checking whose `depends_on` tasks are not all `completed`. Find next available task (no incomplete deps, status `pending`).

**Tests to add:**

```python
def test_get_feature_summary_correct_progress(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, write_tasks, update_task_status, get_feature_summary
    initialize_spec("test", "desc")
    write_tasks("test", [
        {"id": "TASK-001", "title": "A", "description": "D", "estimated_hours": 2.0},
        {"id": "TASK-002", "title": "B", "description": "D", "estimated_hours": 3.0},
    ])
    update_task_status("test", "TASK-001", "completed")
    result = get_feature_summary("test")
    assert "1 / 2" in result
    assert "2.0h done" in result
```

---

### ENH-007 — Cross-feature dependency tracking

**Priority:** 🔵 | **Effort:** M | **Files:** `server.py`, `.specs/.system/feature_graph.json`

**What to build**

Tasks can only depend on other tasks within the same feature. In multi-epic programs (e.g. IAOS risk-sensing depending on risk-assessment being complete), there is no way to express or enforce inter-feature dependencies.

**New tools to add:**

```python
@mcp.tool()
def add_feature_dependency(
    feature_name: str,
    depends_on_feature: str,
    notes: str = ""
) -> str:
    """
    Records that feature_name cannot begin implementation until
    depends_on_feature reaches the 'complete' phase.
    
    Stored in .specs/.system/feature_graph.json.
    
    Args:
        feature_name: The feature that has a dependency
        depends_on_feature: The feature that must be complete first
        notes: Optional explanation
    """

@mcp.tool()
def get_feature_graph() -> str:
    """
    Returns the full inter-feature dependency graph.
    
    Shows: all features and their current phases, dependency edges,
    which features are blocked by incomplete dependencies,
    and critical path estimate based on estimated_hours.
    """
```

**Modify `approve_phase`** (ENH-002): when approving the `tasks` phase (unlocking implementation), check `feature_graph.json` to confirm all `depends_on_feature` entries are in `complete` phase. If not, return a blocking error.

**Storage format** for `.specs/.system/feature_graph.json`:

```json
[
  {
    "feature": "risk-sensing",
    "depends_on": "risk-assessment",
    "notes": "Sensing model requires assessment schema to be finalized",
    "created_at": "2026-05-25T14:00:00Z"
  }
]
```

**Tests to add:**

```python
def test_add_feature_dependency_persists(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, add_feature_dependency
    initialize_spec("feature-a", "A")
    initialize_spec("feature-b", "B")
    result = add_feature_dependency("feature-b", "feature-a", "B needs A")
    assert "✓" in result
    graph_file = temp_specs_dir / ".system" / "feature_graph.json"
    assert graph_file.exists()
    data = json.loads(graph_file.read_text())
    assert data[0]["feature"] == "feature-b"
    assert data[0]["depends_on"] == "feature-a"
```

---

### ENH-008 — Spec health check tool

**Priority:** 🔵 | **Effort:** M | **File:** `server.py`

**What to build**

There is no single command that validates the full state of a feature. This is the intended integration point for a CI/CD pre-merge gate.

**New tool to add:**

```python
@mcp.tool()
def health_check(feature_name: str = None) -> str:
    """
    Runs all validations for one feature or all features.
    
    Checks:
    1. EARS compliance on all requirements
    2. Task dependency graph validity (including cycle detection)
    3. Requirements coverage (each req has design ref and task)
    4. Phase gate status (which phases are approved)
    5. Cross-feature dependency status
    6. Privacy filter check (no un-redacted patterns remain)
    
    Args:
        feature_name: Specific feature to check, or None for all features
    Returns:
        Green / amber / red summary per feature
    """
```

**Example output:**

```
Health Check — all features
───────────────────────────────────────────
risk-assessment   🟢 Healthy   (phase: complete, coverage: 100%)
risk-sensing      🟡 Warning   (phase: design, REQ-004 has no task)
user-auth         🔴 Error     (phase: requirements, EARS violation in REQ-002)

Overall: 1 healthy · 1 warning · 1 error
```

**Implementation:** Compose results from existing tools: re-run EARS validation on saved content using `Requirement.validate_ears_notation`, call the `check_coverage` logic (ENH-005), read `phase_state.json` (ENH-001), check `feature_graph.json` (ENH-007), and re-run the privacy filter on all spec file contents to check if any redaction markers remain in a partially filtered file.

**Tests to add:**

```python
def test_health_check_returns_error_for_invalid_ears(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, health_check
    # Manually write a requirements file with invalid EARS to simulate a corrupted state
    initialize_spec("test", "desc")
    (temp_specs_dir / "test" / "requirements.md").write_text(
        "# Requirements: test\n\n### REQ-001 (must)\nUsers can log in\n"
    )
    result = health_check("test")
    assert "🔴" in result or "Error" in result

def test_health_check_all_features_no_crash(self, temp_specs_dir):
    from universal_spec_mcp.server import health_check
    result = health_check()
    assert isinstance(result, str)
```

---

### ENH-009 — Semantic spec search via memory integration

**Priority:** 🔵 | **Effort:** S | **File:** `server.py`

**What to build**

`search_specs` currently scans spec files only. Winston searching for past decisions about "rate limiting" will miss memory entries tagged "rate limiting" stored from other feature sessions. The two data stores (spec files and SQLite memory) are never queried together.

**Modify `search_specs` to accept an optional flag:**

```python
@mcp.tool()
def search_specs(
    query: str,
    limit: int = 10,
    offset: int = 0,
    include_memories: bool = True
) -> str:
    """
    Search across spec files and optionally the memory store.
    
    Args:
        query: Search query string
        limit: Maximum number of file results to return
        offset: Offset for pagination
        include_memories: Also search the SQLite memory store (default True)
    Returns:
        Combined results grouped by source, labelled clearly
    """
```

**Implementation:**

```python
# Run existing file search
file_results = _search_spec_files(query, limit, offset)

response_parts = []
if file_results:
    response_parts.append("### From spec files\n" + "\n".join(file_results))

if include_memories:
    memory_results = memory_store.search_memory(query, limit=5)
    if memory_results:
        mem_lines = [f"### From memory store\n"]
        for m in memory_results:
            mem_lines.append(
                f"- **[MEM-{m['id']}]** {m['feature_name']} · {m['memory_type']} — {m['content'][:120]}"
            )
        response_parts.append("\n".join(mem_lines))

if not response_parts:
    return inject_directives(f"No results found for '{query}'")

return inject_directives(
    f"## Search Results for '{query}'\n\n" + "\n\n".join(response_parts)
)
```

**Tests to add:**

```python
def test_search_specs_includes_memories_by_default(self, temp_specs_dir, temp_memory_store):
    import universal_spec_mcp.server as srv
    from unittest.mock import patch
    # Add a memory and search for it
    temp_memory_store.add_memory("user-auth", "Decided to use rate limiting with token bucket", "decision")
    with patch.object(srv, 'memory_store', temp_memory_store):
        result = srv.search_specs("rate limiting")
    assert "rate limiting" in result.lower()

def test_search_specs_exclude_memories_flag(self, temp_specs_dir, temp_memory_store):
    import universal_spec_mcp.server as srv
    from unittest.mock import patch
    temp_memory_store.add_memory("user-auth", "rate limiting decision", "decision")
    with patch.object(srv, 'memory_store', temp_memory_store):
        result = srv.search_specs("rate limiting", include_memories=False)
    assert "memory store" not in result.lower()
```

---

## Summary table

### Part 1 — Bugs and issues

| ID | Title | Priority | Effort | File(s) |
|---|---|---|---|---|
| BUG-001 | EARS regex rejects valid requirements | 🔴 | S | `server.py` |
| BUG-002 | Circular task dependencies not detected | 🔴 | S | `server.py` |
| BUG-003 | update_task_status has no file lock | 🔴 | S | `server.py` |
| ISSUE-001 | ExtraArgStripMiddleware is dead code | 🟡 | S | `server.py` |
| ISSUE-002 | SPECS_DIR is hardcoded | 🟡 | S | `server.py` |
| ISSUE-003 | Directive injection bloats every response | 🟡 | M | `server.py` |
| ISSUE-004 | update_task_status uses fragile regex | 🟡 | M | `server.py` |
| ISSUE-005 | list_specs hides empty features | 🔵 | S | `server.py` |
| ISSUE-006 | search_specs has no pagination | 🔵 | S | `server.py` |
| ISSUE-007 | import json inside methods | 🔵 | S | `memory_store.py` |

### Part 2 — Enhancements

| ID | Title | Priority | Effort | Depends on |
|---|---|---|---|---|
| ENH-001 | Phase gate enforcement | 🔴 | M | — |
| ENH-002 | approve_phase sign-off tool | 🔴 | S | ENH-001 |
| ENH-003 | Substantive run_hook | 🟡 | M | ISSUE-004 |
| ENH-004 | Spec versioning + diff | 🟡 | M | — |
| ENH-005 | Traceability matrix | 🟡 | M | — |
| ENH-006 | Estimation rollup | 🔵 | S | ISSUE-004 |
| ENH-007 | Cross-feature dependency graph | 🔵 | M | ENH-001 |
| ENH-008 | Health check tool | 🔵 | M | ENH-001, ENH-005 |
| ENH-009 | Semantic search via memory | 🔵 | S | ISSUE-006 |

---

## Recommended implementation order

```
Wave 1 — Correctness (all 🔴 items)
  BUG-001  Fix EARS regex
  BUG-002  Add circular dependency detection
  BUG-003  Add file lock to update_task_status
  ISSUE-001 Remove dead middleware
  ISSUE-002 SPECS_DIR env var
  ENH-001  Phase gate enforcement
  ENH-002  approve_phase tool

Wave 2 — Structural quality
  ISSUE-004 Fix fragile regex → tasks.json source of truth
  ISSUE-003 Directive injection filtering
  ENH-003  Substantive run_hook (depends on ISSUE-004)
  ENH-004  Spec versioning + diff
  ENH-005  Traceability matrix

Wave 3 — Polish and strategic
  ISSUE-005 list_specs shows empty features
  ISSUE-006 search_specs pagination
  ISSUE-007 Move import json to top level
  ENH-006  Estimation rollup
  ENH-009  Semantic search
  ENH-007  Cross-feature dependency graph (depends on ENH-001)
  ENH-008  Health check tool (depends on ENH-001, ENH-005)
```

---

## Files to touch — consolidated view

| File | Items |
|---|---|
| `src/universal_spec_mcp/server.py` | BUG-001, BUG-002, BUG-003, ISSUE-001, ISSUE-002, ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-006, ENH-001, ENH-002, ENH-003, ENH-004, ENH-005, ENH-006, ENH-007, ENH-008, ENH-009 |
| `src/universal_spec_mcp/memory_store.py` | ISSUE-007 |
| `src/universal_spec_mcp/directive_store.py` | ISSUE-003 (add category param to format_for_context) |
| `tests/test_server.py` | All items — new test classes and methods per item |
| `tests/test_privacy.py` | No changes needed |
| `.bob/rules/spec-workflow.md` | ENH-002, ENH-005 |
| `.bob/skills/bmad-pm.md` | ENH-005 (add check_coverage step) |
| `.bob/skills/bmad-dev.md` | ENH-003 (document substantive pre/post hooks) |
| `README.md` | ISSUE-002 (document env var), ENH-001, ENH-002 (document new tools) |
| `pyproject.toml` | No changes needed |

---

*Full work backlog v1.0 — Universal Spec MCP Server*
*Generated from code evaluation against universal-spec-mcp v2 (2026-05-25)*
