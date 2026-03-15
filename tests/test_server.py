"""
Tests for the Bob Spec Architect MCP Server.
Validates all tools: initialize_spec, write_requirements (EARS), write_design, write_tasks, update_task_status, run_hook.
"""
import sys
import os
import json
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set working directory to a temp test dir
TEST_DIR = Path("/tmp/bob-spec-test")
TEST_DIR.mkdir(exist_ok=True)
os.chdir(TEST_DIR)

from universal_spec_mcp.server import (
    initialize_spec,
    write_requirements,
    write_design,
    write_tasks,
    update_task_status,
    run_hook,
    validate_ears,
    RequirementsDoc,
    Requirement,
    DesignDoc,
    DesignSection,
    TasksDoc,
    Task,
)

FEATURE = "user-authentication"

def test_validate_ears():
    print("\n--- Test: EARS Validator ---")
    valid = "WHEN a user submits valid credentials THE SYSTEM SHALL grant access"
    invalid = "The user should be able to log in"
    assert validate_ears(valid), f"Should be valid EARS: {valid}"
    assert not validate_ears(invalid), f"Should be invalid EARS: {invalid}"
    print("PASS: EARS validator correctly accepts and rejects statements.")

def test_initialize_spec():
    print("\n--- Test: initialize_spec ---")
    result = initialize_spec(FEATURE, "requirements-first")
    assert "Successfully initialized" in result
    assert Path(f".specs/{FEATURE}/meta.json").exists()
    print(f"PASS: {result}")

def test_write_requirements_valid():
    print("\n--- Test: write_requirements (valid EARS) ---")
    req_data = RequirementsDoc(
        feature_name=FEATURE,
        description="User authentication system for secure login.",
        requirements=[
            Requirement(
                id="REQ-001",
                title="User Login",
                ears_statement="WHEN a user submits valid credentials THE SYSTEM SHALL grant access and create a session",
                acceptance_criteria=["User is redirected to dashboard", "Session token is created"]
            ),
            Requirement(
                id="REQ-002",
                title="Invalid Login",
                ears_statement="WHEN a user submits invalid credentials THE SYSTEM SHALL display an error message",
                acceptance_criteria=["Error message is shown", "No session is created"]
            ),
        ]
    )
    result = write_requirements(FEATURE, req_data)
    assert "Successfully wrote" in result
    assert Path(f".specs/{FEATURE}/requirements.md").exists()
    print(f"PASS: {result}")

def test_write_requirements_invalid_ears():
    print("\n--- Test: write_requirements (invalid EARS — should fail) ---")
    req_data = RequirementsDoc(
        feature_name=FEATURE,
        description="Test",
        requirements=[
            Requirement(
                id="REQ-BAD",
                title="Bad Requirement",
                ears_statement="Users should be able to log in easily",
                acceptance_criteria=["It works"]
            )
        ]
    )
    result = write_requirements(FEATURE, req_data)
    assert "Validation Failed" in result
    print(f"PASS: Correctly rejected invalid EARS. Message: {result[:80]}...")

def test_write_design():
    print("\n--- Test: write_design ---")
    design_data = DesignDoc(
        feature_name=FEATURE,
        sections=[
            DesignSection(title="Architecture", content="JWT-based stateless authentication with bcrypt password hashing."),
            DesignSection(title="Sequence Diagram", content="```\nUser -> API: POST /auth/login\nAPI -> DB: Verify credentials\nDB -> API: User record\nAPI -> User: JWT token\n```"),
            DesignSection(title="Data Models", content="User: {id, email, password_hash, created_at}"),
            DesignSection(title="Error Handling", content="Return 401 for invalid credentials, 429 for rate limit exceeded."),
        ]
    )
    result = write_design(FEATURE, design_data)
    assert "Successfully wrote" in result
    assert Path(f".specs/{FEATURE}/design.md").exists()
    print(f"PASS: {result}")

def test_write_tasks():
    print("\n--- Test: write_tasks ---")
    tasks_data = TasksDoc(
        feature_name=FEATURE,
        tasks=[
            Task(id="TASK-001", title="Create User model", description="Define the User SQLAlchemy model with id, email, password_hash fields."),
            Task(id="TASK-002", title="Implement login endpoint", description="POST /auth/login that validates credentials and returns a JWT.", dependencies=["TASK-001"]),
            Task(id="TASK-003", title="Write unit tests", description="Test login with valid and invalid credentials.", dependencies=["TASK-002"]),
        ]
    )
    result = write_tasks(FEATURE, tasks_data)
    assert "Successfully wrote" in result
    assert Path(f".specs/{FEATURE}/tasks.md").exists()
    print(f"PASS: {result}")

def test_update_task_status():
    print("\n--- Test: update_task_status ---")
    result = update_task_status(FEATURE, "TASK-001", "completed")
    assert "Successfully updated" in result
    with open(f".specs/{FEATURE}/tasks.json") as f:
        data = json.load(f)
    task = next(t for t in data["tasks"] if t["id"] == "TASK-001")
    assert task["status"] == "completed"
    print(f"PASS: {result}")

def test_run_hook():
    print("\n--- Test: run_hook ---")
    result = run_hook("pre_task", "Starting TASK-002")
    assert "executed successfully" in result
    bad_result = run_hook("unknown_hook")
    assert "Error" in bad_result
    print(f"PASS: Hook ran correctly. Unknown hook correctly rejected.")

def test_spec_files_content():
    print("\n--- Test: Verify generated spec file content ---")
    req_md = Path(f".specs/{FEATURE}/requirements.md").read_text()
    assert "WHEN a user submits valid credentials" in req_md
    assert "REQ-001" in req_md

    design_md = Path(f".specs/{FEATURE}/design.md").read_text()
    assert "Architecture" in design_md
    assert "Sequence Diagram" in design_md

    tasks_md = Path(f".specs/{FEATURE}/tasks.md").read_text()
    assert "TASK-001" in tasks_md
    assert "COMPLETED" in tasks_md
    print("PASS: All spec files contain expected content.")

if __name__ == "__main__":
    print("=" * 60)
    print("Universal Spec Architect MCP Server — Test Suite")
    print("=" * 60)

    try:
        test_validate_ears()
        test_initialize_spec()
        test_write_requirements_valid()
        test_write_requirements_invalid_ears()
        test_write_design()
        test_write_tasks()
        test_update_task_status()
        test_run_hook()
        test_spec_files_content()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    finally:
        # Cleanup
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
