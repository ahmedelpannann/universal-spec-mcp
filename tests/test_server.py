"""Tests for the MCP server and tools."""

import json
import shutil
from pathlib import Path

import pytest

from universal_spec_mcp.directive_store import DirectiveStore
from universal_spec_mcp.memory_store import MemoryStore
from universal_spec_mcp.server import (
    RequirementsDoc,
    DesignDoc,
    TasksDoc,
    Requirement,
    ADR,
    Task,
    format_requirements_doc,
    format_design_doc,
    format_tasks_doc,
)


@pytest.fixture
def temp_specs_dir(tmp_path, monkeypatch):
    """Create a temporary specs directory for testing."""
    specs_dir = tmp_path / ".specs"
    specs_dir.mkdir()
    
    # Monkeypatch the SPECS_DIR in the server module
    import universal_spec_mcp.server as server_module
    monkeypatch.setattr(server_module, 'SPECS_DIR', specs_dir)
    
    yield specs_dir
    
    # Cleanup
    if specs_dir.exists():
        shutil.rmtree(specs_dir)


@pytest.fixture
def temp_directive_store(tmp_path):
    """Create a temporary directive store for testing."""
    directives_path = tmp_path / "directives.json"
    store = DirectiveStore(directives_path)
    yield store


@pytest.fixture
def temp_memory_store(tmp_path):
    """Create a temporary memory store for testing."""
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    yield store


class TestRequirementModel:
    """Test the Requirement Pydantic model."""
    
    def test_valid_ears_notation(self):
        """Test that valid EARS notation is accepted."""
        valid_requirements = [
            "THE system SHALL authenticate users",
            "WHEN a user logs in THE system SHALL verify credentials",
            "WHILE the user is authenticated THE system SHALL allow access",
            "WHEN a user submits a form WHILE the form is valid THE system SHALL save the data",
        ]
        
        for req_text in valid_requirements:
            req = Requirement(id="REQ-001", text=req_text, priority="must")
            assert req.text == req_text
    
    def test_invalid_ears_notation(self):
        """Test that invalid EARS notation is rejected."""
        invalid_requirements = [
            "This is not EARS notation",
            "The system should do something",
            "User can login",
        ]
        
        for req_text in invalid_requirements:
            with pytest.raises(ValueError, match="EARS notation"):
                Requirement(id="REQ-001", text=req_text)
    
    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored due to ConfigDict."""
        req = Requirement(
            id="REQ-001",
            text="THE system SHALL work",
            priority="must",
            extra_field="should be ignored"
        )
        assert req.id == "REQ-001"
        assert not hasattr(req, 'extra_field')


class TestRequirementsDoc:
    """Test the RequirementsDoc model."""
    
    def test_valid_requirements_doc(self):
        """Test creating a valid requirements document."""
        doc = RequirementsDoc(
            feature_name="user-auth",
            description="User authentication feature",
            requirements=[
                {"id": "REQ-001", "text": "THE system SHALL authenticate users", "priority": "must"},
                {"id": "REQ-002", "text": "THE system SHALL hash passwords", "priority": "must"},
            ]
        )
        
        assert doc.feature_name == "user-auth"
        assert len(doc.requirements) == 2
        assert doc.requirements[0].id == "REQ-001"
    
    def test_format_requirements_doc(self):
        """Test formatting a requirements document as Markdown."""
        doc = RequirementsDoc(
            feature_name="user-auth",
            description="User authentication feature",
            requirements=[
                {"id": "REQ-001", "text": "THE system SHALL authenticate users", "priority": "must"},
            ]
        )
        
        formatted = format_requirements_doc(doc)
        assert "# Requirements: user-auth" in formatted
        assert "User authentication feature" in formatted
        assert "### REQ-001 (must)" in formatted
        assert "THE system SHALL authenticate users" in formatted


class TestDesignDoc:
    """Test the DesignDoc model."""
    
    def test_valid_design_doc(self):
        """Test creating a valid design document."""
        doc = DesignDoc(
            feature_name="user-auth",
            architecture="Layered architecture with authentication middleware",
            adrs=[
                {
                    "id": "ADR-001",
                    "title": "Use JWT for authentication",
                    "context": "Need stateless authentication",
                    "decision": "Use JWT tokens",
                    "consequences": "Stateless but tokens can't be revoked easily",
                }
            ],
            components=["AuthService", "TokenManager"]
        )
        
        assert doc.feature_name == "user-auth"
        assert len(doc.adrs) == 1
        assert doc.adrs[0].id == "ADR-001"
        assert len(doc.components) == 2
    
    def test_format_design_doc(self):
        """Test formatting a design document as Markdown."""
        doc = DesignDoc(
            feature_name="user-auth",
            architecture="Layered architecture",
            adrs=[
                {
                    "id": "ADR-001",
                    "title": "Use JWT",
                    "context": "Need auth",
                    "decision": "JWT tokens",
                    "consequences": "Stateless",
                }
            ],
            components=["AuthService"]
        )
        
        formatted = format_design_doc(doc)
        assert "# Design: user-auth" in formatted
        assert "## Architecture" in formatted
        assert "## Components" in formatted
        assert "- AuthService" in formatted
        assert "### ADR-001: Use JWT" in formatted


class TestTasksDoc:
    """Test the TasksDoc model."""
    
    def test_valid_tasks_doc(self):
        """Test creating a valid tasks document."""
        doc = TasksDoc(
            feature_name="user-auth",
            tasks=[
                {
                    "id": "TASK-001",
                    "title": "Implement login endpoint",
                    "description": "Create POST /login endpoint",
                    "status": "pending",
                },
                {
                    "id": "TASK-002",
                    "title": "Add password hashing",
                    "description": "Use bcrypt for password hashing",
                    "status": "pending",
                    "depends_on": ["TASK-001"],
                }
            ]
        )
        
        assert doc.feature_name == "user-auth"
        assert len(doc.tasks) == 2
        assert doc.tasks[1].depends_on == ["TASK-001"]
    
    def test_duplicate_task_ids_rejected(self):
        """Test that duplicate task IDs are rejected."""
        with pytest.raises(ValueError, match="Duplicate task IDs"):
            TasksDoc(
                feature_name="user-auth",
                tasks=[
                    {"id": "TASK-001", "title": "Task 1", "description": "Desc 1"},
                    {"id": "TASK-001", "title": "Task 2", "description": "Desc 2"},
                ]
            )
    
    def test_invalid_dependency_rejected(self):
        """Test that invalid task dependencies are rejected."""
        with pytest.raises(ValueError, match="depends on non-existent task"):
            TasksDoc(
                feature_name="user-auth",
                tasks=[
                    {
                        "id": "TASK-001",
                        "title": "Task 1",
                        "description": "Desc 1",
                        "depends_on": ["TASK-999"],
                    }
                ]
            )
    
    def test_format_tasks_doc(self):
        """Test formatting a tasks document as Markdown."""
        doc = TasksDoc(
            feature_name="user-auth",
            tasks=[
                {
                    "id": "TASK-001",
                    "title": "Implement login",
                    "description": "Create login endpoint",
                    "status": "in_progress",
                    "estimated_hours": 4.0,
                }
            ]
        )
        
        formatted = format_tasks_doc(doc)
        assert "# Tasks: user-auth" in formatted
        assert "### TASK-001: Implement login" in formatted
        assert "**Status:** in_progress" in formatted
        assert "**Estimated hours:** 4.0" in formatted


class TestDirectiveStore:
    """Test the DirectiveStore class."""
    
    def test_add_directive(self, temp_directive_store):
        """Test adding a directive."""
        directive = temp_directive_store.add_directive(
            "Always use PostgreSQL for databases",
            category="architecture"
        )
        
        assert directive['id'] == 1
        assert directive['text'] == "Always use PostgreSQL for databases"
        assert directive['category'] == "architecture"
    
    def test_list_directives(self, temp_directive_store):
        """Test listing directives."""
        temp_directive_store.add_directive("Directive 1", "general")
        temp_directive_store.add_directive("Directive 2", "testing")
        
        directives = temp_directive_store.list_directives()
        assert len(directives) == 2
    
    def test_remove_directive(self, temp_directive_store):
        """Test removing a directive."""
        directive = temp_directive_store.add_directive("Test directive", "general")
        
        removed = temp_directive_store.remove_directive(directive['id'])
        assert removed is True
        
        directives = temp_directive_store.list_directives()
        assert len(directives) == 0
    
    def test_remove_nonexistent_directive(self, temp_directive_store):
        """Test removing a non-existent directive."""
        removed = temp_directive_store.remove_directive(999)
        assert removed is False
    
    def test_get_directive(self, temp_directive_store):
        """Test getting a specific directive."""
        directive = temp_directive_store.add_directive("Test directive", "general")
        
        retrieved = temp_directive_store.get_directive(directive['id'])
        assert retrieved is not None
        assert retrieved['text'] == "Test directive"
    
    def test_get_directives_by_category(self, temp_directive_store):
        """Test getting directives by category."""
        temp_directive_store.add_directive("Arch directive", "architecture")
        temp_directive_store.add_directive("Test directive", "testing")
        temp_directive_store.add_directive("Another arch", "architecture")
        
        arch_directives = temp_directive_store.get_directives_by_category("architecture")
        assert len(arch_directives) == 2
    
    def test_format_for_context(self, temp_directive_store):
        """Test formatting directives for context injection."""
        temp_directive_store.add_directive("Use PostgreSQL", "architecture")
        temp_directive_store.add_directive("Write unit tests", "testing")
        
        formatted = temp_directive_store.format_for_context()
        assert "## Project Directives" in formatted
        assert "Use PostgreSQL" in formatted
        assert "Write unit tests" in formatted


class TestMemoryStore:
    """Test the MemoryStore class."""
    
    def test_add_memory(self, temp_memory_store):
        """Test adding a memory."""
        memory_id = temp_memory_store.add_memory(
            feature_name="user-auth",
            content="Decided to use JWT for authentication",
            memory_type="decision"
        )
        
        assert memory_id > 0
    
    def test_get_memory(self, temp_memory_store):
        """Test getting a specific memory."""
        memory_id = temp_memory_store.add_memory(
            feature_name="user-auth",
            content="Test memory",
            memory_type="decision"
        )
        
        memory = temp_memory_store.get_memory(memory_id)
        assert memory is not None
        assert memory['content'] == "Test memory"
        assert memory['feature_name'] == "user-auth"
    
    def test_get_memories_by_feature(self, temp_memory_store):
        """Test getting all memories for a feature."""
        temp_memory_store.add_memory("user-auth", "Memory 1", "decision")
        temp_memory_store.add_memory("user-auth", "Memory 2", "context")
        temp_memory_store.add_memory("other-feature", "Memory 3", "decision")
        
        memories = temp_memory_store.get_memories_by_feature("user-auth")
        assert len(memories) == 2
    
    def test_search_memory(self, temp_memory_store):
        """Test full-text search of memories."""
        temp_memory_store.add_memory(
            "user-auth",
            "Decided to use JWT tokens for authentication",
            "decision"
        )
        temp_memory_store.add_memory(
            "user-auth",
            "Use bcrypt for password hashing",
            "decision"
        )
        
        # Search for JWT
        results = temp_memory_store.search_memory("JWT")
        assert len(results) >= 1
        assert any("JWT" in r['content'] for r in results)
    
    def test_delete_memory(self, temp_memory_store):
        """Test deleting a memory."""
        memory_id = temp_memory_store.add_memory(
            "user-auth",
            "Test memory",
            "decision"
        )
        
        deleted = temp_memory_store.delete_memory(memory_id)
        assert deleted is True
        
        memory = temp_memory_store.get_memory(memory_id)
        assert memory is None
    
    def test_list_all_memories(self, temp_memory_store):
        """Test listing all memories."""
        temp_memory_store.add_memory("feature1", "Memory 1", "decision")
        temp_memory_store.add_memory("feature2", "Memory 2", "context")
        
        memories = temp_memory_store.list_all_memories()
        assert len(memories) == 2


class TestServerTools:
    """Test the MCP server tools (integration tests)."""
    
    def test_initialize_spec(self, temp_specs_dir):
        """Test the initialize_spec tool."""
        from universal_spec_mcp.server import initialize_spec
        
        result = initialize_spec("user-auth", "User authentication feature")
        
        assert "✓ Initialized feature specification: user-auth" in result
        assert (temp_specs_dir / "user-auth").exists()
        assert (temp_specs_dir / "user-auth" / "README.md").exists()
    
    def test_initialize_spec_already_exists(self, temp_specs_dir):
        """Test initializing a spec that already exists."""
        from universal_spec_mcp.server import initialize_spec
        
        # Create the directory first
        (temp_specs_dir / "user-auth").mkdir()
        
        result = initialize_spec("user-auth", "User authentication feature")
        assert "already exists" in result
    
    def test_write_and_read_requirements(self, temp_specs_dir):
        """Test writing and reading requirements."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, read_spec
        
        # Initialize
        initialize_spec("user-auth", "User authentication")
        
        # Write requirements
        result = write_requirements(
            feature_name="user-auth",
            description="User authentication feature",
            requirements=[
                {"id": "REQ-001", "text": "THE system SHALL authenticate users", "priority": "must"}
            ]
        )
        
        assert "✓ Requirements written" in result
        
        # Read requirements
        content = read_spec("user-auth", "requirements")
        assert "REQ-001" in content
        assert "THE system SHALL authenticate users" in content
    
    def test_write_requirements_invalid_ears(self, temp_specs_dir):
        """Test that invalid EARS notation is rejected."""
        from universal_spec_mcp.server import initialize_spec, write_requirements
        
        initialize_spec("user-auth", "User authentication")
        
        result = write_requirements(
            feature_name="user-auth",
            description="User authentication feature",
            requirements=[
                {"id": "REQ-001", "text": "This is not EARS notation", "priority": "must"}
            ]
        )
        
        assert "✗ Error" in result
        assert "EARS notation" in result
    
    def test_write_and_read_design(self, temp_specs_dir):
        """Test writing and reading design."""
        from universal_spec_mcp.server import (
            initialize_spec, write_requirements, approve_phase, write_design, read_spec
        )
        
        initialize_spec("user-auth", "User authentication")
        
        # Write and approve requirements first (phase gate requirement)
        write_requirements(
            "user-auth",
            "User authentication system",
            [{"id": "REQ-001", "text": "THE system SHALL authenticate users", "priority": "must"}]
        )
        approve_phase("user-auth", "requirements")
        
        result = write_design(
            feature_name="user-auth",
            architecture="Layered architecture",
            adrs=[
                {
                    "id": "ADR-001",
                    "title": "Use JWT",
                    "context": "Need stateless auth",
                    "decision": "Use JWT tokens",
                    "consequences": "Stateless but can't revoke easily"
                }
            ],
            components=["AuthService"]
        )
        
        assert "✓ Design written" in result
        
        content = read_spec("user-auth", "design")
        assert "ADR-001" in content
        assert "Use JWT" in content
    
    def test_write_and_read_tasks(self, temp_specs_dir):
        """Test writing and reading tasks."""
        from universal_spec_mcp.server import (
            initialize_spec, write_requirements, approve_phase,
            write_design, write_tasks, read_spec
        )
        
        initialize_spec("user-auth", "User authentication")
        
        # Write and approve requirements
        write_requirements(
            "user-auth",
            "User authentication system",
            [{"id": "REQ-001", "text": "THE system SHALL authenticate users", "priority": "must"}]
        )
        approve_phase("user-auth", "requirements")
        
        # Write and approve design
        write_design(
            "user-auth",
            "Layered architecture",
            [{"id": "ADR-001", "title": "Use JWT", "context": "C", "decision": "D", "consequences": "Q"}]
        )
        approve_phase("user-auth", "design")
        
        result = write_tasks(
            feature_name="user-auth",
            tasks=[
                {
                    "id": "TASK-001",
                    "title": "Implement login",
                    "description": "Create login endpoint",
                    "status": "pending"
                }
            ]
        )
        
        assert "✓ Tasks written" in result
        
        content = read_spec("user-auth", "tasks")
        assert "TASK-001" in content
        assert "Implement login" in content
    
    def test_list_specs(self, temp_specs_dir):
        """Test listing specs."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, list_specs


class TestWave1Features:
    """Tests for Wave 1 bug fixes and enhancements."""
    
    def test_ears_minimal_valid(self):
        """BUG-001: Minimal valid EARS form — SHALL with no response text."""
        from universal_spec_mcp.server import Requirement
        req = Requirement(id="REQ-001", text="THE system SHALL authenticate")
        assert req.text == "THE system SHALL authenticate"
    
    def test_ears_with_trigger_no_response(self):
        """BUG-001: EARS with WHEN trigger and no response text."""
        from universal_spec_mcp.server import Requirement
        req = Requirement(id="REQ-001", text="WHEN user logs in THE system SHALL verify credentials")
        assert req.text is not None
    
    def test_circular_dependency_rejected(self):
        """BUG-002: Test that circular task dependencies are rejected."""
        from universal_spec_mcp.server import TasksDoc
        import pytest
        
        with pytest.raises(ValueError, match="Circular dependency"):
            TasksDoc(
                feature_name="user-auth",
                tasks=[
                    {"id": "TASK-001", "title": "A", "description": "A", "depends_on": ["TASK-002"]},
                    {"id": "TASK-002", "title": "B", "description": "B", "depends_on": ["TASK-001"]},
                ]
            )
    
    def test_three_way_circular_dependency_rejected(self):
        """BUG-002: Test that three-way circular dependencies are also caught."""
        from universal_spec_mcp.server import TasksDoc
        import pytest
        
        with pytest.raises(ValueError, match="Circular dependency"):
            TasksDoc(
                feature_name="user-auth",
                tasks=[
                    {"id": "TASK-001", "title": "A", "description": "A", "depends_on": ["TASK-003"]},
                    {"id": "TASK-002", "title": "B", "description": "B", "depends_on": ["TASK-001"]},
                    {"id": "TASK-003", "title": "C", "description": "C", "depends_on": ["TASK-002"]},
                ]
            )
    
    def test_phase_gate_blocks_write_design_before_requirements(self, temp_specs_dir):
        """ENH-001: Phase gate blocks write_design before requirements are approved."""
        from universal_spec_mcp.server import initialize_spec, write_design
        
        initialize_spec("test", "desc")
        result = write_design("test", "arch", [
            {"id": "ADR-001", "title": "T", "context": "C", "decision": "D", "consequences": "Q"}
        ])
        assert "✗" in result
        assert "requirements" in result.lower()
    
    def test_phase_gate_allows_write_design_after_approval(self, temp_specs_dir):
        """ENH-001: Phase gate allows write_design after requirements approval."""
        from universal_spec_mcp.server import (
            initialize_spec, write_requirements, approve_phase, write_design
        )
        
        initialize_spec("test", "desc")
        write_requirements("test", "desc", [
            {"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}
        ])
        approve_phase("test", "requirements")
        result = write_design("test", "arch", [
            {"id": "ADR-001", "title": "T", "context": "C", "decision": "D", "consequences": "Q"}
        ])
        assert "✓" in result
    
    def test_approve_phase_creates_approval_record(self, temp_specs_dir):
        """ENH-002: approve_phase creates approval record."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, approve_phase
        
        initialize_spec("test", "desc")
        write_requirements("test", "desc", [
            {"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}
        ])
        result = approve_phase("test", "requirements", "ahmed", "looks good")
        assert "✓" in result
        
        approval_file = temp_specs_dir / "test" / "approvals.md"
        assert approval_file.exists()
        content = approval_file.read_text()
        assert "requirements" in content
        assert "ahmed" in content
    
    def test_approve_phase_blocks_wrong_phase_order(self, temp_specs_dir):
        """ENH-002: approve_phase blocks wrong phase order."""
        from universal_spec_mcp.server import initialize_spec, approve_phase
        
        initialize_spec("test", "desc")
        result = approve_phase("test", "design")  # Can't approve design before requirements
        assert "✗" in result
    
    def test_get_spec_phase(self, temp_specs_dir):
        """ENH-001: get_spec_phase returns current phase state."""
        from universal_spec_mcp.server import (
            initialize_spec, write_requirements, approve_phase, get_spec_phase
        )
        
        initialize_spec("test", "desc")
        
        # Check initial phase
        result = get_spec_phase("test")
        assert "requirements" in result.lower()
        
        # Write and approve requirements
        write_requirements("test", "desc", [
            {"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}
        ])
        approve_phase("test", "requirements")
        
        # Check phase after approval
        result = get_spec_phase("test")
        assert "design" in result.lower()
        assert "requirements" in result  # Should show as locked
    
    def test_list_specs_filters_hidden_directories(self, temp_specs_dir):
        """Test that list_specs filters out hidden directories like .system."""
        from universal_spec_mcp.server import list_specs
        
        # Create a hidden directory
        (temp_specs_dir / ".system").mkdir()
        (temp_specs_dir / ".system" / "test.md").write_text("test")
        
        result = list_specs()
        assert ".system" not in result

class TestWave2Features:
    """Tests for Wave 2 enhancements."""
    
    def test_spec_versioning_creates_backup(self, temp_specs_dir):
        """Test that updating a spec creates a versioned backup."""
        from universal_spec_mcp.server import initialize_spec, write_requirements
        
        # Initialize and write first version
        initialize_spec("versioning-test")
        write_requirements(
            "versioning-test",
            "Test feature for versioning",
            [{"id": "REQ-001", "text": "THE system SHALL do something", "priority": "must"}]
        )
        
        # Write second version (this creates v1 backup)
        write_requirements(
            "versioning-test",
            "Test feature for versioning",
            [{"id": "REQ-001", "text": "THE system SHALL do something better", "priority": "must"}]
        )
        
        # Write third version (this creates v2 backup)
        write_requirements(
            "versioning-test",
            "Test feature for versioning",
            [{"id": "REQ-001", "text": "THE system SHALL do something even better", "priority": "must"}]
        )
        
        # Check that backups were created
        feature_dir = temp_specs_dir / "versioning-test"
        assert (feature_dir / "requirements.v1.md").exists()
        assert (feature_dir / "requirements.v2.md").exists()
        assert (feature_dir / "requirements.changelog.md").exists()
        
        # Check changelog content
        changelog = (feature_dir / "requirements.changelog.md").read_text()
        assert "v2" in changelog or "v3" in changelog
        assert "requirements.v" in changelog
    
    def test_spec_history_lists_versions(self, temp_specs_dir):
        """Test that spec_history lists all versions."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, spec_history
        
        # Create multiple versions
        initialize_spec("history-test")
        write_requirements(
            "history-test",
            "Test feature for history",
            [{"id": "REQ-001", "text": "THE system SHALL do v1", "priority": "must"}]
        )
        write_requirements(
            "history-test",
            "Test feature for history",
            [{"id": "REQ-001", "text": "THE system SHALL do v2", "priority": "must"}]
        )
        write_requirements(
            "history-test",
            "Test feature for history",
            [{"id": "REQ-001", "text": "THE system SHALL do v3", "priority": "must"}]
        )
        
        # Get history
        result = spec_history("history-test", "requirements")
        
        # Check that all versions are listed
        assert "Version 1" in result
        assert "Version 2" in result
        assert "requirements.v1.md" in result
        assert "requirements.v2.md" in result
        assert "Modified:" in result
        assert "Size:" in result
    
    def test_diff_spec_shows_changes(self, temp_specs_dir):
        """Test that diff_spec shows differences between versions."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, diff_spec
        
        # Create three versions to get v1 and v2 backups
        initialize_spec("diff-test")
        write_requirements(
            "diff-test",
            "Test feature for diff",
            [{"id": "REQ-001", "text": "THE system SHALL do original", "priority": "must"}]
        )
        write_requirements(
            "diff-test",
            "Test feature for diff",
            [{"id": "REQ-001", "text": "THE system SHALL do modified", "priority": "must"}]
        )
        write_requirements(
            "diff-test",
            "Test feature for diff",
            [{"id": "REQ-001", "text": "THE system SHALL do final", "priority": "must"}]
        )
        
        # Get diff between v1 and v2
        result = diff_spec("diff-test", "requirements", "1", "2")
        
        # Check diff format
        assert "```diff" in result
        assert "requirements.v1.md" in result
        assert "requirements.v2.md" in result
        # Should show the change
        assert "original" in result or "modified" in result
    
    def test_spec_history_no_versions(self, temp_specs_dir):
        """Test spec_history when no versions exist."""
        from universal_spec_mcp.server import initialize_spec, spec_history
        
        initialize_spec("no-versions")
        result = spec_history("no-versions", "requirements")
        
        assert "No version history" in result
    
    def test_diff_spec_missing_version(self, temp_specs_dir):
        """Test diff_spec with non-existent version."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, diff_spec
        
        initialize_spec("missing-version")
        write_requirements(
            "missing-version",
            "Test feature for missing version",
            [{"id": "REQ-001", "text": "THE system SHALL exist", "priority": "must"}]
        )
        write_requirements(
            "missing-version",
            "Test feature for missing version",
            [{"id": "REQ-001", "text": "THE system SHALL exist v2", "priority": "must"}]
        )
        
        # Now v1 exists, but v99 doesn't
        result = diff_spec("missing-version", "requirements", "1", "99")
        assert "not found" in result
    
    def test_check_coverage_all_requirements_traced(self, temp_specs_dir):
        """Test check_coverage when all requirements are properly traced."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, write_design, write_tasks, check_coverage, approve_phase
        
        initialize_spec("coverage-test")
        write_requirements(
            "coverage-test",
            "Test feature for coverage",
            [
                {"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"},
                {"id": "REQ-002", "text": "THE system SHALL scale", "priority": "must"}
            ]
        )
        approve_phase("coverage-test", "requirements", "tester")
        write_design(
            "coverage-test",
            "Architecture covering both requirements",
            [
                {
                    "id": "ADR-001",
                    "title": "Use microservices",
                    "context": "Need to satisfy REQ-001 and REQ-002",
                    "decision": "Use microservices architecture",
                    "consequences": "Better scalability"
                }
            ]
        )
        approve_phase("coverage-test", "design", "tester")
        write_tasks(
            "coverage-test",
            [
                {
                    "id": "TASK-001",
                    "title": "Implement service",
                    "description": "Implements REQ-001 and REQ-002",
                    "estimated_hours": 5.0
                }
            ]
        )
        
        result = check_coverage("coverage-test")
        assert "REQ-001" in result
        assert "REQ-002" in result
        assert "✓ In design" in result
        assert "✓ In tasks" in result
        assert "2/2 requirements fully covered" in result
        assert "0 gap(s) found" in result
    
    def test_check_coverage_detects_requirement_not_in_design(self, temp_specs_dir):
        """Test check_coverage detects requirements missing from design."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, write_design, write_tasks, check_coverage, approve_phase
        
        initialize_spec("gap-test")
        write_requirements(
            "gap-test",
            "Test feature with gaps",
            [
                {"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"},
                {"id": "REQ-002", "text": "THE system SHALL scale", "priority": "must"}
            ]
        )
        approve_phase("gap-test", "requirements", "tester")
        write_design(
            "gap-test",
            "Architecture covering only REQ-001",
            [
                {
                    "id": "ADR-001",
                    "title": "Basic design",
                    "context": "Covers REQ-001 only",
                    "decision": "Simple approach",
                    "consequences": "Works for now"
                }
            ]
        )
        approve_phase("gap-test", "design", "tester")
        write_tasks(
            "gap-test",
            [
                {
                    "id": "TASK-001",
                    "title": "Implement both",
                    "description": "Covers REQ-001 and REQ-002",
                    "estimated_hours": 5.0
                }
            ]
        )
        
        result = check_coverage("gap-test")
        assert "REQ-002" in result
        assert "✗ Not in design" in result
        assert "1 gap(s) found" in result
    
    def test_check_coverage_detects_task_without_requirement(self, temp_specs_dir):
        """Test check_coverage detects tasks without requirement linkage."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, write_design, write_tasks, check_coverage, approve_phase
        
        initialize_spec("orphan-test")
        write_requirements(
            "orphan-test",
            "Test feature",
            [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}]
        )
        approve_phase("orphan-test", "requirements", "tester")
        write_design(
            "orphan-test",
            "Architecture with REQ-001",
            [
                {
                    "id": "ADR-001",
                    "title": "Design",
                    "context": "Covers REQ-001",
                    "decision": "Do it",
                    "consequences": "Good"
                }
            ]
        )
        approve_phase("orphan-test", "design", "tester")
        write_tasks(
            "orphan-test",
            [
                {
                    "id": "TASK-001",
                    "title": "Implement REQ-001",
                    "description": "Covers REQ-001",
                    "estimated_hours": 3.0
                },
                {
                    "id": "TASK-002",
                    "title": "Random task",
                    "description": "Does something unrelated",
                    "estimated_hours": 2.0
                }
            ]
        )
        
        result = check_coverage("orphan-test")
        assert "TASK-002" in result
        assert "No requirement linkage found" in result



class TestWave3Features:
    """Tests for run_hook, get_feature_summary, feature graph, health_check,
    and other Wave 2-3 tools that previously had no test coverage."""

    def _setup_full_feature(self, srv, feature_name: str = "test") -> None:
        """Helper: create a feature that has passed all three phases."""
        srv.initialize_spec(feature_name, "desc")
        srv.write_requirements(
            feature_name, "desc",
            [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}]
        )
        srv.approve_phase(feature_name, "requirements", "ahmed")
        srv.write_design(
            feature_name,
            "Architecture with REQ-001 at its core",
            [{"id": "ADR-001", "title": "T", "context": "REQ-001",
              "decision": "D", "consequences": "Q"}]
        )
        srv.approve_phase(feature_name, "design", "ahmed")
        srv.write_tasks(
            feature_name,
            [
                {"id": "TASK-001", "title": "Implement auth",
                 "description": "REQ-001 referenced here", "estimated_hours": 2.0},
                {"id": "TASK-002", "title": "Write tests",
                 "description": "REQ-001 coverage",
                 "depends_on": ["TASK-001"], "estimated_hours": 1.0},
            ]
        )
        srv.approve_phase(feature_name, "tasks", "ahmed")

    # ------------------------------------------------------------------ run_hook

    def test_pre_task_hook_blocks_incomplete_dependency(self, temp_specs_dir):
        """run_hook pre_task must block when a dependency task is not completed."""
        import universal_spec_mcp.server as srv
        self._setup_full_feature(srv)
        result = srv.run_hook("pre_task", "test", "TASK-002")
        assert "\u2717" in result
        assert "TASK-001" in result

    def test_pre_task_hook_passes_when_deps_complete(self, temp_specs_dir):
        """run_hook pre_task must pass when all dependency tasks are completed."""
        import universal_spec_mcp.server as srv
        self._setup_full_feature(srv)
        srv.update_task_status("test", "TASK-001", "completed")
        result = srv.run_hook("pre_task", "test", "TASK-002")
        assert "\u2717" not in result
        assert "Ready" in result or "Dependency Check" in result

    def test_pre_task_hook_with_directives(self, temp_specs_dir, temp_directive_store,
                                            monkeypatch):
        """run_hook pre_task must render directives without raising KeyError."""
        import universal_spec_mcp.server as srv
        monkeypatch.setattr(srv, "directive_store", temp_directive_store)
        temp_directive_store.add_directive("Always write tests", "testing")
        self._setup_full_feature(srv)
        result = srv.run_hook("pre_task", "test", "TASK-001")
        assert "Always write tests" in result
        assert "\u2717" not in result

    def test_post_task_hook_requires_summary(self, temp_specs_dir):
        """run_hook post_task must return an error when summary is empty."""
        import universal_spec_mcp.server as srv
        self._setup_full_feature(srv)
        result = srv.run_hook("post_task", "test", "TASK-001", "")
        assert "\u2717" in result

    def test_post_task_hook_stores_memory(self, temp_specs_dir, temp_memory_store,
                                          monkeypatch):
        """run_hook post_task must store a memory entry for the completed task."""
        import universal_spec_mcp.server as srv
        monkeypatch.setattr(srv, "memory_store", temp_memory_store)
        self._setup_full_feature(srv)
        result = srv.run_hook(
            "post_task", "test", "TASK-001",
            "Implemented login endpoint using JWT"
        )
        assert "\u2713" in result
        memories = temp_memory_store.get_memories_by_feature("test")
        assert any("TASK-001" in m["content"] for m in memories)

    # -------------------------------------------------------- get_feature_summary

    def test_get_feature_summary_progress(self, temp_specs_dir):
        """get_feature_summary must report correct task count and hours after completion."""
        import universal_spec_mcp.server as srv
        self._setup_full_feature(srv)
        srv.update_task_status("test", "TASK-001", "completed")
        result = srv.get_feature_summary("test")
        assert "1 / 2" in result
        assert "2.0h" in result

    def test_get_feature_summary_shows_blocked_task(self, temp_specs_dir):
        """get_feature_summary must list TASK-002 as blocked when TASK-001 is pending."""
        import universal_spec_mcp.server as srv
        self._setup_full_feature(srv)
        result = srv.get_feature_summary("test")
        assert "TASK-002" in result or "blocked" in result.lower()

    def test_get_feature_summary_approval_timestamp(self, temp_specs_dir):
        """get_feature_summary approval_info must reflect the timestamp written by approve_phase."""
        import universal_spec_mcp.server as srv
        self._setup_full_feature(srv)
        phase = srv._get_phase("test")
        assert "approvals" in phase
        assert "tasks" in phase["approvals"]

    # --------------------------------------------------- add_feature_dependency

    def test_add_feature_dependency_persists(self, temp_specs_dir):
        """add_feature_dependency must write the edge to feature_graph.json."""
        import universal_spec_mcp.server as srv, json
        srv.initialize_spec("feature-a", "A")
        srv.initialize_spec("feature-b", "B")
        result = srv.add_feature_dependency("feature-b", "feature-a", "B needs A")
        assert "\u2713" in result
        graph_file = temp_specs_dir / ".system" / "feature_graph.json"
        assert graph_file.exists()
        data = json.loads(graph_file.read_text())
        assert data[0]["feature"] == "feature-b"
        assert data[0]["depends_on"] == "feature-a"

    def test_add_feature_dependency_no_duplicate(self, temp_specs_dir):
        """add_feature_dependency must reject a duplicate edge."""
        import universal_spec_mcp.server as srv
        srv.initialize_spec("feature-a", "A")
        srv.initialize_spec("feature-b", "B")
        srv.add_feature_dependency("feature-b", "feature-a")
        result = srv.add_feature_dependency("feature-b", "feature-a")
        assert "already exists" in result

    def test_approve_phase_blocks_on_incomplete_feature_dep(self, temp_specs_dir):
        """approve_phase(tasks) must block when a cross-feature dependency is not ready."""
        import universal_spec_mcp.server as srv
        srv.initialize_spec("feature-a", "A")
        srv.write_requirements(
            "feature-a", "A",
            [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}]
        )
        srv.approve_phase("feature-a", "requirements", "ahmed")
        srv.initialize_spec("feature-b", "B")
        srv.write_requirements(
            "feature-b", "B",
            [{"id": "REQ-001", "text": "THE system SHALL scale", "priority": "must"}]
        )
        srv.approve_phase("feature-b", "requirements", "ahmed")
        srv.write_design(
            "feature-b", "arch REQ-001",
            [{"id": "ADR-001", "title": "T", "context": "REQ-001",
              "decision": "D", "consequences": "Q"}]
        )
        srv.approve_phase("feature-b", "design", "ahmed")
        srv.write_tasks(
            "feature-b",
            [{"id": "TASK-001", "title": "A",
              "description": "REQ-001", "estimated_hours": 1.0}]
        )
        srv.add_feature_dependency("feature-b", "feature-a")
        result = srv.approve_phase("feature-b", "tasks")
        assert "\u2717" in result
        assert "feature-a" in result

    # -------------------------------------------------------------- health_check

    def test_health_check_single_healthy_feature(self, temp_specs_dir):
        """health_check must return healthy for a fully traced feature."""
        import universal_spec_mcp.server as srv
        self._setup_full_feature(srv)
        result = srv.health_check("test")
        assert "\U0001f7e2" in result or "Healthy" in result

    def test_health_check_all_features_returns_summary(self, temp_specs_dir):
        """health_check() with no argument must check all features and show an overall line."""
        import universal_spec_mcp.server as srv
        self._setup_full_feature(srv)
        result = srv.health_check()
        assert "Overall" in result
        assert "test" in result

    def test_health_check_detects_ears_violation(self, temp_specs_dir):
        """health_check must flag a error when a requirements file has an EARS violation."""
        import universal_spec_mcp.server as srv
        srv.initialize_spec("bad", "desc")
        (temp_specs_dir / "bad" / "requirements.md").write_text(
            "# Requirements: bad\n\n### REQ-001 (must)\n\nUsers can log in\n"
        )
        result = srv.health_check("bad")
        assert "\U0001f534" in result or "Error" in result

    # --------------------------------------------------------- search_specs paging

    def test_search_specs_pagination_offset(self, temp_specs_dir):
        """search_specs must honour the offset parameter for pagination."""
        import universal_spec_mcp.server as srv
        self._setup_full_feature(srv)
        result_p1 = srv.search_specs("THE", limit=1, offset=0)
        result_p2 = srv.search_specs("THE", limit=1, offset=1)
        assert "Showing 1" in result_p1
        assert result_p1 != result_p2 or "offset=1" in result_p1

    # --------------------------------------------------------- diff_spec 'current'

    def test_diff_spec_current_vs_backup(self, temp_specs_dir):
        """diff_spec must accept 'current' as a version to compare to a backup."""
        from universal_spec_mcp.server import initialize_spec, write_requirements, diff_spec
        initialize_spec("diff-current")
        write_requirements(
            "diff-current", "Test",
            [{"id": "REQ-001", "text": "THE system SHALL work", "priority": "must"}]
        )
        write_requirements(
            "diff-current", "Test",
            [{"id": "REQ-001", "text": "THE system SHALL scale", "priority": "must"}]
        )
        result = diff_spec("diff-current", "requirements", "current", "1")
        assert "```diff" in result
        assert "current" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
# Made with Bob Bob
