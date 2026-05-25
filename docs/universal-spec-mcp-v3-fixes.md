# Universal Spec MCP v3 — Fixes & Suggestions

**Evaluated:** 2026-05-25
**Codebase state:** v3 — 65/65 tests passing, 25 MCP tools, all backlog items addressed
**This document:** 5 bugs to fix + 7 suggestions to improve

---

## Summary

| Category | Count | Files affected |
|---|---|---|
| 🔴 Bugs (runtime errors or wrong output) | 5 | `server.py`, `memory_store.py` |
| 🔵 Suggestions (quality and completeness) | 7 | `server.py`, `memory_store.py`, `tests/test_server.py` |

Fixes are ordered by severity. All have exact line numbers, the broken code, and the corrected replacement.

---

## Part 1 — Bugs

---

### FIX-001 — `run_hook` crashes with KeyError when any directive exists

**Priority:** 🔴 Must fix
**File:** `src/universal_spec_mcp/server.py`
**Line:** 1021

**What is broken**

The pre-task hook reads directives and formats them using the wrong dictionary key:

```python
# BROKEN — key is 'directive', which does not exist
directives_text = "\n".join(f"- {d['directive']}" for d in directives[:5]) if directives else "None"
```

`DirectiveStore.list_directives()` returns objects with keys `['id', 'text', 'category']`. The key `'directive'` does not exist. When any directive has been added to the project, every call to `run_hook("pre_task", ...)` raises a `KeyError` that is silently swallowed by the outer `except Exception` block — the hook returns a generic error instead of the pre-flight report.

This was not caught by tests because no test calls `run_hook` with directives present in the store.

**Fix**

```python
# FIXED — correct key is 'text'
directives_text = "\n".join(f"- {d['text']}" for d in directives[:5]) if directives else "None"
```

**Test to add** (`TestWave2Features`):

```python
def test_pre_task_hook_shows_directives(self, temp_specs_dir, temp_directive_store, monkeypatch):
    """Test that run_hook pre_task correctly renders directives."""
    import universal_spec_mcp.server as srv
    monkeypatch.setattr(srv, 'directive_store', temp_directive_store)
    temp_directive_store.add_directive("Always write tests", "testing")
    
    # Set up phase state and tasks
    srv.initialize_spec("test", "desc")
    phase = {"current_phase": "implementation", "locked_phases": ["requirements", "design", "tasks"], "last_updated": ""}
    srv._save_phase("test", phase)
    from universal_spec_mcp.server import TasksDoc, write_tasks_json
    doc = TasksDoc(feature_name="test", tasks=[
        {"id": "TASK-001", "title": "Implement login", "description": "D"}
    ])
    write_tasks_json("test", doc)
    
    result = srv.run_hook("pre_task", "test", "TASK-001")
    assert "Always write tests" in result
    assert "✗" not in result  # should not return an error
```

---

### FIX-002 — `approve_phase`: unreachable bare `return` statement

**Priority:** 🔴 Must fix
**File:** `src/universal_spec_mcp/server.py`
**Line:** 1318

**What is broken**

After the final `except Exception` block of `approve_phase`, there is a stray line:

```python
    return inject_directives(response)
```

At this point `response` is not in scope (the function always exits via the try/except before reaching this line). If Python's control flow ever reached it — e.g. if a future refactor moves the except block — it would raise `NameError: name 'response' is not defined`. It is a copy-paste artifact from the refactoring that merged the approval logic.

**Fix**

Delete line 1318 entirely. The function's last valid `return` is inside the try block at line ~1314.

```python
# DELETE this line (line 1318):
    return inject_directives(response)
```

---

### FIX-003 — Two dead code blocks appended after `health_check` at EOF

**Priority:** 🔴 Must fix
**File:** `src/universal_spec_mcp/server.py`
**Lines:** 1936–1963 (approximately — everything between `health_check`'s final `except` and the `# Main Entry Point` section)

**What is broken**

After `health_check`'s legitimate `except Exception` block closes, the file continues with two orphaned code fragments that are unreachable:

1. A stray `return inject_directives(response)` and `except Exception` handler (fragment of `get_feature_graph`)
2. A full copy of `get_feature_summary`'s response-building block including its own `except Exception` handler

These are copy-paste artifacts from merging three functions during refactoring. They inflate the file by ~30 lines and will mislead anyone reading or modifying the code.

**Fix**

Delete everything between the end of `health_check`'s except block and the `# Main Entry Point` comment. Specifically, delete the following block in its entirety:

```python
# DELETE — lines ~1936 to ~1963, the two orphaned fragments:

        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error retrieving feature graph: {str(e)}")

        
        # Build response
        response = f"Feature Summary — {feature_name}\n"
        response += "─" * (len(response) - 1) + "\n"
        response += f"Phase:      {current_phase}{approval_info}\n"
        response += f"Progress:   {completed_tasks} / {total_tasks} tasks complete ({task_progress_pct:.0f}%)\n"
        
        if total_hours > 0:
            response += f"Hours:      {completed_hours:.1f}h done / {remaining_hours:.1f}h remaining ({total_hours:.1f}h total)\n"
        
        if in_progress_tasks > 0:
            response += f"Active:     {in_progress_tasks} task(s) in progress\n"
        
        if blocked_tasks:
            response += f"Blocked:    {blocked_tasks[0]}\n"
            ...
        
    except Exception as e:
        return inject_directives(f"✗ Error generating feature summary: {str(e)}")
```

After deletion, the file should go directly from `health_check`'s except block to the `# Main Entry Point` section.

---

### FIX-004 — `run_hook` post_task reports stale progress — always N-1

**Priority:** 🔴 Must fix
**File:** `src/universal_spec_mcp/server.py`
**Lines:** ~1065–1080

**What is broken**

The post-task hook reads `tasks.json` to calculate and display progress:

```python
tasks_data = read_tasks_json(feature_name)
total_tasks = len(tasks_data)
completed_tasks = sum(1 for t in tasks_data if t.get("status") == "completed")
progress_pct = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
```

But `update_task_status` is called **after** the hook in Amelia's workflow:

```
run_hook("post_task", ...)    ← reads JSON here: task still "pending"
update_task_status(..., "completed")  ← writes JSON here
```

The hook always reads the pre-completion state. **Confirmed by test**: after implementing TASK-001, the hook reports `0/2 tasks completed (0.0%)` even though the task is done.

**Fix — Option A (recommended):** Remove the progress block from the post-task hook entirely. `get_feature_summary` already does this correctly and Amelia can call it explicitly when she wants a status view.

```python
# REMOVE these lines from the post_task branch (~line 1065-1080):
tasks_data = read_tasks_json(feature_name)
total_tasks = len(tasks_data)
completed_tasks = sum(1 for t in tasks_data if t.get("status") == "completed")
progress_pct = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

# And remove from the response string:
f"📊 Progress: {completed_tasks}/{total_tasks} tasks completed ({progress_pct:.1f}%)\n"
```

Replace with a reminder to call `get_feature_summary`:

```python
response += f"\n\n📊 Use get_feature_summary('{feature_name}') for current progress."
```

**Fix — Option B (if you want to keep the progress display):** Accept the current task ID as being complete in the count:

```python
# Count the current task as completed regardless of JSON state
completed_tasks = sum(
    1 for t in tasks_data
    if t.get("status") == "completed" or t.get("id") == task_id
)
```

**Test to add:**

```python
def test_post_task_hook_stores_memory(self, temp_specs_dir, temp_memory_store, monkeypatch):
    """Test that post_task hook stores a memory entry."""
    import universal_spec_mcp.server as srv
    monkeypatch.setattr(srv, 'memory_store', temp_memory_store)
    srv.initialize_spec("test", "desc")
    phase = {"current_phase": "implementation", "locked_phases": ["requirements", "design", "tasks"], "last_updated": ""}
    srv._save_phase("test", phase)
    from universal_spec_mcp.server import TasksDoc, write_tasks_json
    doc = TasksDoc(feature_name="test", tasks=[
        {"id": "TASK-001", "title": "First", "description": "D"}
    ])
    write_tasks_json("test", doc)
    
    result = srv.run_hook("post_task", "test", "TASK-001", "Implemented login using JWT")
    assert "✓" in result
    memories = temp_memory_store.get_memories_by_feature("test")
    assert any("TASK-001" in m["content"] for m in memories)
```

---

### FIX-005 — `get_feature_summary`: approval timestamp always blank

**Priority:** 🔴 Must fix
**File:** `src/universal_spec_mcp/server.py`
**Lines:** 1540–1542

**What is broken**

The summary attempts to show when the current phase was approved:

```python
if current_phase in phase_state.get("approvals", {}):
    approval_ts = phase_state["approvals"][current_phase].get("timestamp", "")
    if approval_ts:
        approval_info = f" ({current_phase} approved {approval_ts[:10]})"
```

`phase_state.json` has no `"approvals"` key. Approvals are written to `approvals.md` by `approve_phase`, not to the phase state JSON. `approval_info` is therefore always an empty string and the phase line never shows an approval date.

**Fix — Option A (recommended):** Write the approval timestamp into `phase_state.json` inside `approve_phase`:

In `approve_phase`, after calling `lock_phase`, add:

```python
# Write approval metadata into phase_state.json
phase_state = _get_phase(feature_name)
if "approvals" not in phase_state:
    phase_state["approvals"] = {}
phase_state["approvals"][phase] = {
    "approved_by": approved_by,
    "timestamp": timestamp,
    "notes": notes
}
_save_phase(feature_name, phase_state)
```

**Fix — Option B:** Parse the timestamp from `approvals.md`:

```python
approvals_file = feature_dir / "approvals.md"
if approvals_file.exists():
    content = approvals_file.read_text(encoding="utf-8")
    # Find the most recent timestamp for current_phase
    pattern = rf"## {re.escape(current_phase)} — approved.*?Timestamp:\*\* ([^\n]+)"
    matches = re.findall(pattern, content, re.DOTALL)
    if matches:
        approval_info = f" (approved {matches[-1][:10]})"
```

**Test to add:**

```python
def test_feature_summary_shows_approval_timestamp(self, temp_specs_dir):
    from universal_spec_mcp.server import (
        initialize_spec, write_requirements, approve_phase,
        write_tasks_json, get_feature_summary, TasksDoc
    )
    import universal_spec_mcp.server as srv
    initialize_spec("test", "desc")
    write_requirements("test", "desc", [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}])
    approve_phase("test", "requirements", "ahmed")
    
    # Check that phase_state has the approval recorded
    phase = srv._get_phase("test")
    assert "approvals" in phase
    assert "requirements" in phase["approvals"]
```

---

## Part 2 — Suggestions

---

### SUG-001 — `memory_store.py`: inline `import json` not fixed

**File:** `src/universal_spec_mcp/memory_store.py`
**Line:** 3 (top of file) — but also repeated inside 4 method bodies

**Context**

ISSUE-007 was marked done because `import json` was moved to the top of `server.py`. But `memory_store.py` still has `import json` repeated inside `add_memory`, `search_memory`, `get_memories_by_feature`, and `list_all_memories`.

**Fix**

`memory_store.py` already has `import json` at line 3. Remove the four inline `import json` statements inside the method bodies. One-line delete per method.

```python
# DELETE from inside add_memory(), search_memory(), get_memories_by_feature(), list_all_memories():
import json  # ← remove these four occurrences
```

---

### SUG-002 — `diff_spec`: cannot compare current file to a backup

**File:** `src/universal_spec_mcp/server.py`
**Line:** 1373

**Context**

Current signature:

```python
def diff_spec(feature_name: str, spec_type: str, version1: int, version2: int) -> str:
```

Both parameters are integers, so only backup versions can be compared to each other. The most useful case — "what changed since the first version?" or "what did I just change?" — requires comparing a backup to the live current file, which is impossible with this API.

**Suggested change**

Change both version parameters to `int | str` and treat the string `"current"` as a reference to the live file:

```python
def diff_spec(
    feature_name: str,
    spec_type: str,
    version_a: int | str = "current",
    version_b: int | str = 1
) -> str:
    """
    Show differences between two versions of a spec.
    
    Use version_a="current" to compare the live file to a backup.
    Use integer values to compare two backup versions.
    
    Examples:
        diff_spec("auth", "requirements", "current", 1)   # live vs first backup
        diff_spec("auth", "requirements", 2, 1)           # v2 vs v1
    """
    def resolve_version(v) -> Path:
        if str(v) == "current":
            path = feature_dir / f"{spec_type}.md"
        else:
            path = feature_dir / f"{spec_type}.v{v}.md"
        if not path.exists():
            raise FileNotFoundError(f"Version '{v}' not found: {path}")
        return path
    
    # ... rest of implementation unchanged
```

**Test to add:**

```python
def test_diff_spec_current_vs_backup(self, temp_specs_dir):
    from universal_spec_mcp.server import initialize_spec, write_requirements, diff_spec
    initialize_spec("test", "desc")
    write_requirements("test", "desc", [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}])
    write_requirements("test", "desc", [{"id": "REQ-001", "text": "THE system SHALL authenticate", "priority": "must"}])
    result = diff_spec("test", "requirements", "current", 1)
    assert "diff" in result.lower() or "---" in result or "+++" in result
```

---

### SUG-003 — `health_check`: coverage counter double-penalises requirements with two gaps

**File:** `src/universal_spec_mcp/server.py`
**Line:** 1905

**Context**

The coverage percentage inside `health_check` is calculated as:

```python
covered = len(req_ids) - len([w for w in warnings if "has no task" in w or "not referenced" in w])
```

A single requirement that is **both** not in the design AND has no task generates two warnings and gets subtracted from `covered` twice. A feature with 3 requirements where one has both gaps reports `1/3` covered instead of the correct `2/3`.

**Fix**

Count unique REQ-xxx IDs that appear in any warning, not the number of warning lines:

```python
# Count unique requirement IDs that have any gap
gapped_req_ids = set()
for w in warnings:
    match = re.search(r'REQ-\d+', w)
    if match:
        gapped_req_ids.add(match.group())

covered = len(req_ids) - len(gapped_req_ids)
coverage_pct = (covered / len(req_ids) * 100) if req_ids else 0
```

**Test to add:**

```python
def test_health_check_coverage_no_double_penalty(self, temp_specs_dir):
    """A requirement missing from both design and tasks should count as 1 gap, not 2."""
    from universal_spec_mcp.server import initialize_spec, health_check
    initialize_spec("test", "desc")
    (temp_specs_dir / "test" / "requirements.md").write_text(
        "# Requirements: test\n\n### REQ-001 (must)\nTHE system SHALL work\n\n"
        "### REQ-002 (must)\nTHE system SHALL scale\n\n"
        "### REQ-003 (must)\nTHE system SHALL log\n"
    )
    # Design and tasks only reference REQ-001 and REQ-002; REQ-003 has no design OR task
    (temp_specs_dir / "test" / "design.md").write_text("REQ-001 REQ-002")
    (temp_specs_dir / "test" / "tasks.md").write_text("REQ-001 REQ-002")
    result = health_check("test")
    # Should show 2/3 covered, not 1/3
    assert "2/3" in result or "66%" in result
```

---

### SUG-004 — `tasks.json` is not versioned alongside `tasks.md`

**File:** `src/universal_spec_mcp/server.py`
**Function:** `write_tasks_json` (~line 321)

**Context**

When `write_tasks` is called twice, `tasks.md` gets a `tasks.v1.md` backup via `write_spec_file`. But `tasks.json` — the machine-readable source of truth used by `update_task_status`, `run_hook`, and `get_feature_summary` — is simply overwritten with no backup:

```python
def write_tasks_json(feature_name: str, doc: TasksDoc) -> None:
    json_path = feature_dir / "tasks.json"
    data = [task.model_dump() for task in doc.tasks]
    json_path.write_text(json.dumps(data, indent=2), encoding='utf-8')  # no backup
```

If you need to roll back tasks, the markdown history exists (`tasks.v1.md`) but the JSON is gone.

**Fix**

Mirror the same versioning logic in `write_tasks_json`:

```python
def write_tasks_json(feature_name: str, doc: TasksDoc) -> None:
    """Write tasks to machine-readable JSON, with versioned backup."""
    feature_dir = get_feature_dir(feature_name)
    json_path = feature_dir / "tasks.json"
    
    # Backup existing file before overwriting
    if json_path.exists():
        existing_backups = list(feature_dir.glob("tasks.v*.json"))
        next_version = len(existing_backups) + 1
        backup_path = feature_dir / f"tasks.v{next_version}.json"
        json_path.rename(backup_path)
    
    data = [task.model_dump() for task in doc.tasks]
    json_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
```

---

### SUG-005 — `run_hook` pre_task silently truncates directives at 5

**File:** `src/universal_spec_mcp/server.py`
**Line:** 1021

**Context**

After fixing FIX-001 (wrong key), the directives block in the pre-task hook still silently shows only 5 and drops the rest:

```python
directives_text = "\n".join(f"- {d['text']}" for d in directives[:5]) if directives else "None"
```

With 10+ directives on a mature project, Amelia gets an incomplete picture with no indication more exist.

**Fix**

```python
shown = directives[:5]
directives_text = "\n".join(f"- {d['text']}" for d in shown) if shown else "None"
if len(directives) > 5:
    directives_text += f"\n  ... and {len(directives) - 5} more (call list_directives for full list)"
```

---

### SUG-006 — Missing tests for Wave 2/3 tools (ENH-003 through ENH-009)

**File:** `tests/test_server.py`

**Context**

The 17 new tests in v3 are grouped into `TestWave1Features` (phase gates, approve_phase, EARS, circular deps) and `TestWave2Features` (spec versioning, diff, check_coverage). The following tools introduced in Waves 2 and 3 have **zero test coverage**:

| Tool | Test gap |
|---|---|
| `run_hook` (pre + post) | No test with directives; no dep-blocking test; no memory-store test |
| `get_feature_summary` | No test at all |
| `add_feature_dependency` | No test at all |
| `get_feature_graph` | No test at all |
| `health_check` | No test at all |
| `search_specs` with pagination | No test for `offset` param |
| `approve_phase` with feature deps | No test for cross-feature blocking |

The `run_hook` KeyError (FIX-001) was entirely preventable with a test that adds a directive before calling the hook.

**Tests to add — new class `TestWave3Features`:**

```python
class TestWave3Features:
    """Tests for Wave 3 tools: run_hook, get_feature_summary, feature graph, health_check."""

    def _setup_full_feature(self, specs_dir, srv, feature_name="test"):
        """Helper: create a feature with all three phases approved."""
        srv.initialize_spec(feature_name, "desc")
        srv.write_requirements(feature_name, "desc", [
            {"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}
        ])
        srv.approve_phase(feature_name, "requirements")
        srv.write_design(feature_name, "arch with REQ-001", [
            {"id": "ADR-001", "title": "T", "context": "REQ-001", "decision": "D", "consequences": "Q"}
        ])
        srv.approve_phase(feature_name, "design")
        srv.write_tasks(feature_name, [
            {"id": "TASK-001", "title": "First", "description": "REQ-001", "estimated_hours": 2.0},
            {"id": "TASK-002", "title": "Second", "description": "REQ-001",
             "depends_on": ["TASK-001"], "estimated_hours": 3.0},
        ])
        srv.approve_phase(feature_name, "tasks")

    def test_pre_task_hook_blocks_incomplete_dependency(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        self._setup_full_feature(temp_specs_dir, srv)
        # TASK-002 depends on TASK-001 which is still pending
        result = srv.run_hook("pre_task", "test", "TASK-002")
        assert "✗" in result
        assert "TASK-001" in result

    def test_pre_task_hook_passes_when_deps_complete(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        self._setup_full_feature(temp_specs_dir, srv)
        srv.update_task_status("test", "TASK-001", "completed")
        result = srv.run_hook("pre_task", "test", "TASK-002")
        assert "✗" not in result
        assert "Ready" in result or "Dependency Check" in result

    def test_post_task_hook_requires_summary(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        self._setup_full_feature(temp_specs_dir, srv)
        result = srv.run_hook("post_task", "test", "TASK-001", "")
        assert "✗" in result
        assert "implementation_summary" in result.lower() or "required" in result.lower()

    def test_get_feature_summary_progress(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        self._setup_full_feature(temp_specs_dir, srv)
        srv.update_task_status("test", "TASK-001", "completed")
        result = srv.get_feature_summary("test")
        assert "1 / 2" in result
        assert "2.0h" in result

    def test_get_feature_summary_shows_blocked(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        self._setup_full_feature(temp_specs_dir, srv)
        result = srv.get_feature_summary("test")
        # TASK-002 is blocked by TASK-001 (pending)
        assert "TASK-002" in result or "blocked" in result.lower()

    def test_add_feature_dependency_persists(self, temp_specs_dir):
        import universal_spec_mcp.server as srv, json
        srv.initialize_spec("feature-a", "A")
        srv.initialize_spec("feature-b", "B")
        result = srv.add_feature_dependency("feature-b", "feature-a", "B needs A")
        assert "✓" in result
        graph_file = temp_specs_dir / ".system" / "feature_graph.json"
        assert graph_file.exists()
        data = json.loads(graph_file.read_text())
        assert data[0]["feature"] == "feature-b"
        assert data[0]["depends_on"] == "feature-a"

    def test_add_feature_dependency_no_duplicate(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        srv.initialize_spec("feature-a", "A")
        srv.initialize_spec("feature-b", "B")
        srv.add_feature_dependency("feature-b", "feature-a")
        result = srv.add_feature_dependency("feature-b", "feature-a")
        assert "already exists" in result

    def test_get_feature_graph_shows_blocked(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        srv.initialize_spec("feature-a", "A")
        srv.initialize_spec("feature-b", "B")
        srv.add_feature_dependency("feature-b", "feature-a")
        result = srv.get_feature_graph()
        assert "feature-b" in result
        assert "feature-a" in result

    def test_health_check_healthy_feature(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        self._setup_full_feature(temp_specs_dir, srv)
        result = srv.health_check("test")
        assert "🟢" in result or "Healthy" in result

    def test_health_check_all_features(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        self._setup_full_feature(temp_specs_dir, srv)
        result = srv.health_check()  # no argument = all features
        assert "Overall" in result
        assert "test" in result

    def test_health_check_error_on_ears_violation(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        srv.initialize_spec("bad", "desc")
        (temp_specs_dir / "bad" / "requirements.md").write_text(
            "# Requirements: bad\n\n### REQ-001 (must)\n\nUsers can log in\n"
        )
        result = srv.health_check("bad")
        assert "🔴" in result or "Error" in result

    def test_search_specs_pagination_offset(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        self._setup_full_feature(temp_specs_dir, srv)
        result_page1 = srv.search_specs("THE", limit=1, offset=0)
        result_page2 = srv.search_specs("THE", limit=1, offset=1)
        assert "Showing 1" in result_page1
        assert "Showing 2" in result_page2 or "offset=1" in result_page1

    def test_approve_phase_blocks_feature_with_incomplete_dep(self, temp_specs_dir):
        import universal_spec_mcp.server as srv
        self._setup_full_feature(temp_specs_dir, srv, "feature-a")
        self._setup_full_feature(temp_specs_dir, srv, "feature-b")
        srv.add_feature_dependency("feature-b", "feature-a")
        # feature-a is not in implementation/complete phase yet
        result = srv.approve_phase("feature-b", "tasks")
        assert "✗" in result
        assert "feature-a" in result
```

---

### SUG-007 — Git commit message says "Wave 1" but all three waves are shipped

**File:** `.git/COMMIT_EDITMSG` / git history

**Context**

The single commit `1be35f2` is titled "Wave 1: Critical bug fixes and phase gate enforcement" but actually contains all Wave 1, Wave 2, and Wave 3 items: spec versioning, diff, check_coverage, run_hook, get_feature_summary, add_feature_dependency, get_feature_graph, health_check, semantic search, and all structural fixes. The commit message lists "3 new MCP tools (17 total)" when the actual count is 25.

This makes git bisect unreliable and PR reviews confusing, and the shipped test count (57 in the message vs 65 actual) is wrong.

**Suggested action**

If history can be rewritten before the repo is shared publicly, rebase into three commits:

```
Wave 1: BUG-001, BUG-002, BUG-003, ISSUE-001, ISSUE-002, ENH-001, ENH-002
  → 57 tests, 17 tools

Wave 2: ISSUE-003, ISSUE-004, ISSUE-005, ISSUE-006, ENH-003, ENH-004, ENH-005
  → 62 tests, 22 tools

Wave 3: ISSUE-007, ENH-006, ENH-007, ENH-008, ENH-009
  → 65 tests, 25 tools
```

If the repo is already public or shared, add a follow-up commit with an accurate summary:

```
Fix: correct Wave 1–3 commit attribution

All three waves from the backlog were shipped together in the prior
commit. This note corrects the record: 25 tools total (was 14),
65 tests total (was 48), all backlog items addressed.
```

---

## Files to touch — consolidated

| File | Items |
|---|---|
| `src/universal_spec_mcp/server.py` | FIX-001, FIX-002, FIX-003, FIX-004, FIX-005, SUG-002, SUG-003, SUG-004, SUG-005 |
| `src/universal_spec_mcp/memory_store.py` | SUG-001 |
| `tests/test_server.py` | FIX-001 test, FIX-004 test, FIX-005 test, SUG-002 test, SUG-003 test, SUG-006 (full new test class) |
| `.git` (optional) | SUG-007 |

---

## Recommended order

```
1. FIX-001  run_hook KeyError              — one-line fix, highest impact
2. FIX-002  approve_phase dead return      — one-line delete
3. FIX-003  EOF dead code blocks           — ~30-line delete
4. FIX-004  post_task stale progress       — remove or fix progress block
5. FIX-005  get_feature_summary approval   — write approvals into phase_state.json
6. SUG-001  memory_store inline imports    — 4-line delete
7. SUG-005  run_hook directive truncation  — 3-line change
8. SUG-004  tasks.json versioning          — add backup logic to write_tasks_json
9. SUG-002  diff_spec current version      — update signature + resolver
10. SUG-003 health_check coverage count    — fix set-based dedup
11. SUG-006 add TestWave3Features          — new test class, ~13 tests
12. SUG-007 git commit message (optional)
```

---

*v3 fix & suggestion document — Universal Spec MCP*
*Generated from live code evaluation 2026-05-25*
