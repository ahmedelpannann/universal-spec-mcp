import os
import json
import re
from pathlib import Path
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("Universal Spec Architect")

# Base directory for specs
SPECS_DIR = Path(".specs")

# --- Pydantic Models for Strict LLM Outputs ---

class Requirement(BaseModel):
    id: str = Field(..., description="Unique identifier for the requirement, e.g., REQ-001")
    title: str = Field(..., description="Short title of the requirement")
    ears_statement: str = Field(
        ..., 
        description="The requirement written strictly in EARS notation: [WHEN <trigger>] [WHILE <precondition>] THE <system> SHALL <response>"
    )
    acceptance_criteria: List[str] = Field(..., description="List of testable acceptance criteria")

class RequirementsDoc(BaseModel):
    feature_name: str
    description: str
    requirements: List[Requirement]

class DesignSection(BaseModel):
    title: str = Field(..., description="Section title, e.g., Architecture, Data Models, Error Handling")
    content: str = Field(..., description="Markdown content for this section")

class DesignDoc(BaseModel):
    feature_name: str
    sections: List[DesignSection]

class Task(BaseModel):
    id: str = Field(..., description="Unique task identifier, e.g., TASK-001")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Detailed implementation instructions")
    status: Literal["todo", "in_progress", "completed"] = Field(default="todo")
    dependencies: List[str] = Field(default_factory=list, description="List of task IDs this task depends on")

class TasksDoc(BaseModel):
    feature_name: str
    tasks: List[Task]

# --- Helper Functions ---

def get_spec_dir(feature_name: str) -> Path:
    """Get the directory for a specific feature spec."""
    spec_dir = SPECS_DIR / feature_name
    spec_dir.mkdir(parents=True, exist_ok=True)
    return spec_dir

def validate_ears(statement: str) -> bool:
    """Validate if a statement follows EARS notation."""
    # Basic EARS pattern: Must contain "THE <system> SHALL"
    # Optionally starts with "WHEN" or "WHILE" or "IF"
    pattern = r"^(?:(?:WHEN|WHILE|IF|WHERE)\s+.*?\s+)?THE\s+.*?\s+SHALL\s+.*$"
    return bool(re.match(pattern, statement, re.IGNORECASE))

# --- MCP Tools ---

@mcp.tool()
def initialize_spec(feature_name: str, workflow_variant: Literal["requirements-first", "design-first"] = "requirements-first") -> str:
    """
    Initialize a new feature specification directory.
    This is the first step in the spec-driven workflow.
    """
    spec_dir = get_spec_dir(feature_name)
    
    # Create a metadata file to track the workflow
    meta = {
        "feature_name": feature_name,
        "workflow_variant": workflow_variant,
        "status": "initialized"
    }
    
    with open(spec_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)
        
    return f"Successfully initialized spec for '{feature_name}' using {workflow_variant} workflow at {spec_dir}. Next step: generate requirements.md or design.md depending on the workflow."

@mcp.tool()
def write_requirements(feature_name: str, requirements_data: RequirementsDoc) -> str:
    """
    Write the requirements.md file. 
    Enforces EARS notation for all requirements. If EARS is violated, this tool will return an error.
    """
    spec_dir = get_spec_dir(feature_name)
    
    # Validate EARS notation
    violations = []
    for req in requirements_data.requirements:
        if not validate_ears(req.ears_statement):
            violations.append(f"{req.id}: '{req.ears_statement}' does not match EARS pattern (must contain 'THE <system> SHALL').")
            
    if violations:
        error_msg = "Validation Failed: Requirements must use strict EARS notation.\n" + "\n".join(violations)
        return error_msg
        
    # Generate Markdown
    md_content = f"# Requirements: {requirements_data.feature_name}\n\n"
    md_content += f"{requirements_data.description}\n\n"
    
    for req in requirements_data.requirements:
        md_content += f"## {req.id}: {req.title}\n\n"
        md_content += f"**Requirement:** {req.ears_statement}\n\n"
        md_content += "**Acceptance Criteria:**\n"
        for ac in req.acceptance_criteria:
            md_content += f"- {ac}\n"
        md_content += "\n"
        
    with open(spec_dir / "requirements.md", "w") as f:
        f.write(md_content)
        
    # Save raw JSON for programmatic access later
    with open(spec_dir / "requirements.json", "w") as f:
        f.write(requirements_data.model_dump_json(indent=2))
        
    return f"Successfully wrote requirements.md for '{feature_name}'. All requirements passed EARS validation."

@mcp.tool()
def write_design(feature_name: str, design_data: DesignDoc) -> str:
    """
    Write the design.md file based on the requirements.
    """
    spec_dir = get_spec_dir(feature_name)
    
    # Generate Markdown
    md_content = f"# Technical Design: {design_data.feature_name}\n\n"
    
    for section in design_data.sections:
        md_content += f"## {section.title}\n\n"
        md_content += f"{section.content}\n\n"
        
    with open(spec_dir / "design.md", "w") as f:
        f.write(md_content)
        
    return f"Successfully wrote design.md for '{feature_name}'."

@mcp.tool()
def write_tasks(feature_name: str, tasks_data: TasksDoc) -> str:
    """
    Write the tasks.md file based on the design.
    This breaks the work down into discrete, trackable implementation steps.
    """
    spec_dir = get_spec_dir(feature_name)
    
    # Generate Markdown
    md_content = f"# Implementation Tasks: {tasks_data.feature_name}\n\n"
    
    for task in tasks_data.tasks:
        status_marker = "[ ]" if task.status == "todo" else ("[~]" if task.status == "in_progress" else "[x]")
        md_content += f"### {task.id}: {task.title}\n"
        md_content += f"Status: {status_marker} {task.status.upper()}\n\n"
        md_content += f"{task.description}\n\n"
        if task.dependencies:
            md_content += f"**Dependencies:** {', '.join(task.dependencies)}\n\n"
            
    with open(spec_dir / "tasks.md", "w") as f:
        f.write(md_content)
        
    # Save raw JSON for programmatic tracking
    with open(spec_dir / "tasks.json", "w") as f:
        f.write(tasks_data.model_dump_json(indent=2))
        
    return f"Successfully wrote tasks.md for '{feature_name}'. Ready for implementation phase."

if __name__ == "__main__":
    mcp.run()

@mcp.tool()
def update_task_status(feature_name: str, task_id: str, new_status: Literal["todo", "in_progress", "completed"]) -> str:
    """
    Update the status of a specific task in the tasks.md file.
    Use this to track implementation progress in real-time.
    """
    spec_dir = get_spec_dir(feature_name)
    tasks_json_path = spec_dir / "tasks.json"
    
    if not tasks_json_path.exists():
        return f"Error: tasks.json not found for feature '{feature_name}'. Run write_tasks first."
        
    with open(tasks_json_path, "r") as f:
        tasks_data = json.load(f)
        
    task_found = False
    for task in tasks_data["tasks"]:
        if task["id"] == task_id:
            task["status"] = new_status
            task_found = True
            break
            
    if not task_found:
        return f"Error: Task ID '{task_id}' not found."
        
    # Save updated JSON
    with open(tasks_json_path, "w") as f:
        json.dump(tasks_data, f, indent=2)
        
    # Regenerate Markdown
    md_content = f"# Implementation Tasks: {tasks_data['feature_name']}\n\n"
    for task in tasks_data["tasks"]:
        status_marker = "[ ]" if task["status"] == "todo" else ("[~]" if task["status"] == "in_progress" else "[x]")
        md_content += f"### {task['id']}: {task['title']}\n"
        md_content += f"Status: {status_marker} {task['status'].upper()}\n\n"
        md_content += f"{task['description']}\n\n"
        if task.get("dependencies"):
            md_content += f"**Dependencies:** {', '.join(task['dependencies'])}\n\n"
            
    with open(spec_dir / "tasks.md", "w") as f:
        f.write(md_content)
        
    return f"Successfully updated task '{task_id}' to status '{new_status}'."

@mcp.tool()
def run_hook(hook_name: str, context: str = "") -> str:
    """
    Simulate spec-driven Agent Hooks.
    Triggers predefined actions based on events (e.g., 'pre_task', 'post_task', 'post_save').
    """
    # In a real implementation, this would execute shell commands or trigger other agents.
    # For this MCP server, we simulate the hook execution and return the result.
    
    hooks = {
        "pre_task": "Running pre-task checks: Linting current workspace, checking steering rules...",
        "post_task": "Running post-task checks: Executing unit tests, checking for regressions...",
        "post_save": "Running post-save hooks: Formatting code, updating imports..."
    }
    
    if hook_name not in hooks:
        return f"Error: Unknown hook '{hook_name}'. Available hooks: {', '.join(hooks.keys())}"
        
    result = f"Hook '{hook_name}' executed successfully.\nAction: {hooks[hook_name]}\nContext: {context}"
    return result
