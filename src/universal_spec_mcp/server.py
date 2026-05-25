"""Universal Spec MCP Server - Main server implementation with all tools."""

import difflib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .directive_store import DirectiveStore
from .memory_store import MemoryStore
from .privacy import PrivacyFilter

# Initialize FastMCP server
mcp = FastMCP("universal-spec-mcp")

# Initialize stores
privacy_filter = PrivacyFilter()
directive_store = DirectiveStore()
memory_store = MemoryStore()

# Base specs directory (configurable via environment variable)
SPECS_DIR = Path(os.environ.get("UNIVERSAL_SPEC_DIR", ".specs"))

# File lock for thread-safe spec file updates
_file_lock = threading.Lock()


# ============================================================================
# Pydantic Models for Spec Documents
# ============================================================================

class Requirement(BaseModel):
    """A single requirement in EARS notation."""
    model_config = ConfigDict(extra='ignore')
    
    id: str = Field(..., description="Unique requirement ID (e.g., REQ-001)")
    text: str = Field(..., description="Requirement text in EARS notation")
    priority: Literal["must", "should", "could"] = Field(default="must")
    
    @field_validator('text')
    @classmethod
    def validate_ears_notation(cls, v: str) -> str:
        """Validate that the requirement follows EARS notation."""
        # EARS pattern: [WHEN <trigger>] [WHILE <precondition>] THE <system> SHALL [<response>]
        # Fixed: Made response text after SHALL optional to allow stub requirements
        ears_pattern = r'(?:WHEN\s+.+?\s+)?(?:WHILE\s+.+?\s+)?THE\s+.+?\s+SHALL(?:\s+.+)?'
        if not re.search(ears_pattern, v, re.IGNORECASE):
            raise ValueError(
                f"Requirement must follow EARS notation: "
                f"[WHEN <trigger>] [WHILE <precondition>] THE <system> SHALL [<response>]. "
                f"Got: {v}"
            )
        return v


class RequirementsDoc(BaseModel):
    """Requirements specification document."""
    model_config = ConfigDict(extra='ignore')
    
    feature_name: str = Field(..., description="Name of the feature")
    description: str = Field(..., description="Brief description of the feature")
    requirements: list[Requirement] = Field(..., description="List of requirements")


class ADR(BaseModel):
    """Architectural Decision Record."""
    model_config = ConfigDict(extra='ignore')
    
    id: str = Field(..., description="Unique ADR ID (e.g., ADR-001)")
    title: str = Field(..., description="Decision title")
    context: str = Field(..., description="What is the context of this decision?")
    decision: str = Field(..., description="What is the decision?")
    consequences: str = Field(..., description="What are the consequences?")
    alternatives: str = Field(default="", description="What alternatives were considered?")


class DesignDoc(BaseModel):
    """Design specification document."""
    model_config = ConfigDict(extra='ignore')
    
    feature_name: str = Field(..., description="Name of the feature")
    architecture: str = Field(..., description="High-level architecture description")
    adrs: list[ADR] = Field(..., description="List of Architectural Decision Records")
    components: list[str] = Field(default_factory=list, description="List of components")


class Task(BaseModel):
    """A single implementation task."""
    model_config = ConfigDict(extra='ignore')
    
    id: str = Field(..., description="Unique task ID (e.g., TASK-001)")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Detailed task description")
    status: Literal["pending", "in_progress", "completed", "blocked"] = Field(default="pending")
    depends_on: list[str] = Field(default_factory=list, description="List of task IDs this task depends on")
    estimated_hours: float = Field(default=0.0, description="Estimated hours to complete")


class TasksDoc(BaseModel):
    """Tasks specification document."""
    model_config = ConfigDict(extra='ignore')
    
    feature_name: str = Field(..., description="Name of the feature")
    tasks: list[Task] = Field(..., description="List of implementation tasks")
    
    @field_validator('tasks')
    @classmethod
    def validate_task_dependencies(cls, tasks: list[Task]) -> list[Task]:
        """Validate that task dependencies reference existing tasks and detect cycles."""
        task_ids = {task.id for task in tasks}
        
        # Check for duplicate IDs
        if len(task_ids) != len(tasks):
            raise ValueError("Duplicate task IDs found")
        
        # Check that all dependencies exist
        for task in tasks:
            for dep_id in task.depends_on:
                if dep_id not in task_ids:
                    raise ValueError(
                        f"Task {task.id} depends on non-existent task {dep_id}"
                    )
        
        # Check for circular dependencies using Kahn's algorithm
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


# ============================================================================
# Helper Functions
# ============================================================================
# Note: Extra argument handling is done via ConfigDict(extra='ignore') on all
# Pydantic models. FastMCP validates args before middleware can process them,
# so we rely on Pydantic's built-in extra field handling instead of middleware.

def get_feature_dir(feature_name: str) -> Path:
    """Get the directory path for a feature."""
    return SPECS_DIR / feature_name


def read_spec_file(feature_name: str, spec_type: Literal["requirements", "design", "tasks"]) -> str:
    """Read a specification file."""
    feature_dir = get_feature_dir(feature_name)
    file_path = feature_dir / f"{spec_type}.md"
    
    if not file_path.exists():
        raise FileNotFoundError(f"Spec file not found: {file_path}")
    
    return file_path.read_text(encoding='utf-8')


def write_spec_file(
    feature_name: str,
    spec_type: Literal["requirements", "design", "tasks"],
    content: str
) -> None:
    """Write a specification file with privacy filtering and versioning."""
    feature_dir = get_feature_dir(feature_name)
    feature_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = feature_dir / f"{spec_type}.md"
    
    # Create backup if file exists
    if file_path.exists():
        # Find next version number
        existing_versions = list(feature_dir.glob(f"{spec_type}.v*.md"))
        next_version = len(existing_versions) + 1
        backup_path = feature_dir / f"{spec_type}.v{next_version}.md"
        
        # Rename current file to backup
        file_path.rename(backup_path)
        
        # Append to changelog
        changelog = feature_dir / f"{spec_type}.changelog.md"
        timestamp = datetime.now().isoformat()
        entry = (
            f"\n## v{next_version + 1} — {timestamp}\n\n"
            f"Previous version saved as {backup_path.name}\n"
        )
        
        if changelog.exists():
            with open(changelog, 'a', encoding='utf-8') as f:
                f.write(entry)
        else:
            with open(changelog, 'w', encoding='utf-8') as f:
                f.write(f"# {spec_type.title()} Changelog\n" + entry)
    
    # Apply privacy filter
    filtered_content = privacy_filter.filter(content)
    
    file_path.write_text(filtered_content, encoding='utf-8')


def format_requirements_doc(doc: RequirementsDoc) -> str:
    """Format a requirements document as Markdown."""
    lines = [
        f"# Requirements: {doc.feature_name}",
        "",
        doc.description,
        "",
        "## Requirements",
        ""
    ]
    
    for req in doc.requirements:
        lines.append(f"### {req.id} ({req.priority})")
        lines.append(req.text)
        lines.append("")
    
    return "\n".join(lines)


def format_design_doc(doc: DesignDoc) -> str:
    """Format a design document as Markdown."""
    lines = [
        f"# Design: {doc.feature_name}",
        "",
        "## Architecture",
        "",
        doc.architecture,
        ""
    ]
    
    if doc.components:
        lines.append("## Components")
        lines.append("")
        for component in doc.components:
            lines.append(f"- {component}")
        lines.append("")
    
    lines.append("## Architectural Decision Records")
    lines.append("")
    
    for adr in doc.adrs:
        lines.append(f"### {adr.id}: {adr.title}")
        lines.append("")
        lines.append("**Context:**")
        lines.append(adr.context)
        lines.append("")
        lines.append("**Decision:**")
        lines.append(adr.decision)
        lines.append("")
        lines.append("**Consequences:**")
        lines.append(adr.consequences)
        lines.append("")
        if adr.alternatives:
            lines.append("**Alternatives Considered:**")
            lines.append(adr.alternatives)
            lines.append("")
    
    return "\n".join(lines)


def format_tasks_doc(doc: TasksDoc) -> str:
    """Format a tasks document as Markdown."""
    lines = [
        f"# Tasks: {doc.feature_name}",
        "",
        "## Implementation Tasks",
        ""
    ]
    
    for task in doc.tasks:
        lines.append(f"### {task.id}: {task.title}")
        lines.append(f"**Status:** {task.status}")
        if task.depends_on:
            lines.append(f"**Depends on:** {', '.join(task.depends_on)}")
        if task.estimated_hours > 0:
            lines.append(f"**Estimated hours:** {task.estimated_hours}")
        lines.append("")
        lines.append(task.description)
        lines.append("")
    
    return "\n".join(lines)


def inject_directives(response: str, category: str | None = None) -> str:
    """
    Inject project directives into a tool response.
    
    Args:
        response: The response text to inject directives into
        category: Optional category to filter directives by
    
    Returns:
        Response with directives appended (if any exist)
    """
    directives_text = directive_store.format_for_context(category=category)
    if directives_text:
        return f"{response}\n\n{directives_text}"
    return response


def write_tasks_json(feature_name: str, doc: TasksDoc) -> None:
    """Write tasks to a machine-readable JSON file (source of truth) with versioning."""
    feature_dir = get_feature_dir(feature_name)
    json_path = feature_dir / "tasks.json"
    
    # Create backup if file exists
    if json_path.exists():
        # Find next version number
        existing_versions = list(feature_dir.glob("tasks.v*.json"))
        next_version = len(existing_versions) + 1
        backup_path = feature_dir / f"tasks.v{next_version}.json"
        
        # Rename current file to backup
        json_path.rename(backup_path)
        
        # Append to changelog
        changelog = feature_dir / "tasks.changelog.md"
        timestamp = datetime.now().isoformat()
        entry = (
            f"\n## v{next_version + 1} — {timestamp}\n\n"
            f"Previous version saved as {backup_path.name}\n"
        )
        
        if changelog.exists():
            with open(changelog, 'a', encoding='utf-8') as f:
                f.write(entry)
        else:
            with open(changelog, 'w', encoding='utf-8') as f:
                f.write(f"# Tasks Changelog\n" + entry)
    
    data = [task.model_dump() for task in doc.tasks]
    json_path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def read_tasks_json(feature_name: str) -> list[dict[str, Any]]:
    """Read tasks from the JSON source of truth."""
    feature_dir = get_feature_dir(feature_name)
    json_path = feature_dir / "tasks.json"
    if not json_path.exists():
        raise FileNotFoundError(f"tasks.json not found for {feature_name}")
    return json.loads(json_path.read_text(encoding='utf-8'))


def regenerate_tasks_md(feature_name: str) -> None:
    """Regenerate tasks.md from tasks.json source of truth."""
    tasks_data = read_tasks_json(feature_name)
    doc = TasksDoc(feature_name=feature_name, tasks=tasks_data)
    content = format_tasks_doc(doc)
    write_spec_file(feature_name, "tasks", content)


def _get_phase_state_path(feature_name: str) -> Path:
    """Get the path to the phase state file for a feature."""
    return get_feature_dir(feature_name) / "phase_state.json"


def _get_phase(feature_name: str) -> dict[str, Any]:
    """Get the current phase state for a feature."""
    phase_file = _get_phase_state_path(feature_name)
    
    if not phase_file.exists():
        # Default state: uninitialized
        return {
            "current_phase": "uninitialized",
            "locked_phases": [],
            "last_updated": datetime.now().isoformat()
        }
    
    with open(phase_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_phase(feature_name: str, phase_state: dict[str, Any]) -> None:
    """Save the phase state for a feature."""
    phase_file = _get_phase_state_path(feature_name)
    phase_state["last_updated"] = datetime.now().isoformat()
    
    with open(phase_file, 'w', encoding='utf-8') as f:
        json.dump(phase_state, f, indent=2)


def _check_phase_gate(feature_name: str, required_phase: str) -> tuple[bool, str]:
    """
    Check if a phase gate allows proceeding.
    
    Returns:
        (allowed, error_message) - allowed is True if gate passes, False otherwise
    """
    phase_state = _get_phase(feature_name)
    locked_phases = phase_state.get("locked_phases", [])
    
    if required_phase not in locked_phases:
        phase_names = {
            "requirements": "requirements",
            "design": "design",
            "tasks": "tasks"
        }
        return False, (
            f"✗ Cannot proceed: {phase_names.get(required_phase, required_phase)} "
            f"phase is not yet locked. Complete and approve the {required_phase} phase first "
            f"(use approve_phase tool)."
        )
    
    return True, ""


# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool()
def initialize_spec(feature_name: str, description: str = "") -> str:
    """
    Initialize a new feature specification directory.
    
    Args:
        feature_name: Name of the feature (will be used as directory name)
        description: Optional brief description of the feature
    
    Returns:
        Confirmation message with next steps
    """
    feature_dir = get_feature_dir(feature_name)
    
    if feature_dir.exists():
        return inject_directives(
            f"Feature '{feature_name}' already exists at {feature_dir}. "
            f"Use write_requirements, write_design, or write_tasks to update specs."
        )
    
    feature_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a README
    readme_path = feature_dir / "README.md"
    readme_content = f"# {feature_name}\n\n{description}\n\n## Specification Files\n\n"
    readme_content += "- `requirements.md` - Requirements in EARS notation\n"
    readme_content += "- `design.md` - Architecture and ADRs\n"
    readme_content += "- `tasks.md` - Implementation tasks\n"
    
    readme_path.write_text(privacy_filter.filter(readme_content), encoding='utf-8')
    
    response = (
        f"✓ Initialized feature specification: {feature_name}\n"
        f"Location: {feature_dir}\n\n"
        f"Next steps:\n"
        f"1. Use write_requirements to document requirements in EARS notation\n"
        f"2. Use write_design to document architecture and ADRs\n"
        f"3. Use write_tasks to break down implementation tasks"
    )
    
    return inject_directives(response)


@mcp.tool()
def write_requirements(
    feature_name: str,
    description: str,
    requirements: list[dict[str, Any]]
) -> str:
    """
    Write or update the requirements specification for a feature.
    
    Args:
        feature_name: Name of the feature
        description: Brief description of the feature
        requirements: List of requirement dictionaries with 'id', 'text', and optional 'priority'
    
    Returns:
        Confirmation message
    """
    try:
        # Validate using Pydantic model
        doc = RequirementsDoc(
            feature_name=feature_name,
            description=description,
            requirements=requirements
        )
        
        # Format and write
        content = format_requirements_doc(doc)
        write_spec_file(feature_name, "requirements", content)
        
        # Initialize phase state if this is the first spec
        phase_state = _get_phase(feature_name)
        if phase_state["current_phase"] == "uninitialized":
            phase_state["current_phase"] = "requirements"
            _save_phase(feature_name, phase_state)
        
        response = (
            f"✓ Requirements written for '{feature_name}'\n"
            f"Total requirements: {len(doc.requirements)}\n"
            f"File: {get_feature_dir(feature_name) / 'requirements.md'}\n\n"
            f"Next step: Review and approve requirements using approve_phase('{feature_name}', 'requirements')"
        )
        
        return inject_directives(response, category="requirements")
        
    except Exception as e:
        return inject_directives(f"✗ Error writing requirements: {str(e)}")


@mcp.tool()
def write_design(
    feature_name: str,
    architecture: str,
    adrs: list[dict[str, Any]],
    components: list[str] | None = None
) -> str:
    """
    Write or update the design specification for a feature.
    
    Args:
        feature_name: Name of the feature
        architecture: High-level architecture description
        adrs: List of ADR dictionaries with 'id', 'title', 'context', 'decision', 'consequences'
        components: Optional list of component names
    
    Returns:
        Confirmation message
    """
    try:
        # Phase gate: requirements must be locked
        allowed, error_msg = _check_phase_gate(feature_name, "requirements")
        if not allowed:
            return inject_directives(error_msg)
        
        # Validate using Pydantic model
        doc = DesignDoc(
            feature_name=feature_name,
            architecture=architecture,
            adrs=adrs,
            components=components or []
        )
        
        # Format and write
        content = format_design_doc(doc)
        write_spec_file(feature_name, "design", content)
        
        # Update phase state
        phase_state = _get_phase(feature_name)
        if phase_state["current_phase"] == "requirements":
            phase_state["current_phase"] = "design"
            _save_phase(feature_name, phase_state)
        
        # Store ADRs in memory for future reference
        for adr in doc.adrs:
            memory_store.add_memory(
                feature_name=feature_name,
                content=f"{adr.title}: {adr.decision}",
                memory_type="decision",
                metadata={"adr_id": adr.id}
            )
        
        response = (
            f"✓ Design written for '{feature_name}'\n"
            f"Total ADRs: {len(doc.adrs)}\n"
            f"Components: {len(doc.components)}\n"
            f"File: {get_feature_dir(feature_name) / 'design.md'}\n\n"
            f"Next step: Review and approve design using approve_phase('{feature_name}', 'design')"
        )
        
        return inject_directives(response, category="architecture")
        
    except Exception as e:
        return inject_directives(f"✗ Error writing design: {str(e)}")


@mcp.tool()
def write_tasks(
    feature_name: str,
    tasks: list[dict[str, Any]]
) -> str:
    """
    Write or update the tasks specification for a feature.
    
    Args:
        feature_name: Name of the feature
        tasks: List of task dictionaries with 'id', 'title', 'description', optional 'status', 'depends_on', 'estimated_hours'
    
    Returns:
        Confirmation message
    """
    try:
        # Phase gate: design must be locked
        allowed, error_msg = _check_phase_gate(feature_name, "design")
        if not allowed:
            return inject_directives(error_msg)
        
        # Validate using Pydantic model
        doc = TasksDoc(
            feature_name=feature_name,
            tasks=tasks
        )
        
        # Write JSON source of truth
        write_tasks_json(feature_name, doc)
        
        # Generate markdown from JSON
        content = format_tasks_doc(doc)
        write_spec_file(feature_name, "tasks", content)
        
        # Update phase state
        phase_state = _get_phase(feature_name)
        if phase_state["current_phase"] == "design":
            phase_state["current_phase"] = "tasks"
            _save_phase(feature_name, phase_state)
        
        response = (
            f"✓ Tasks written for '{feature_name}'\n"
            f"Total tasks: {len(doc.tasks)}\n"
            f"Files: {get_feature_dir(feature_name) / 'tasks.md'}, tasks.json\n\n"
            f"Next step: Review and approve tasks using approve_phase('{feature_name}', 'tasks')"
        )
        
        return inject_directives(response, category="testing")
        
    except Exception as e:
        return inject_directives(f"✗ Error writing tasks: {str(e)}")


@mcp.tool()
def update_task_status(
    feature_name: str,
    task_id: str,
    status: Literal["pending", "in_progress", "completed", "blocked"],
    notes: str = ""
) -> str:
    """
    Update the status of a specific task.
    
    Args:
        feature_name: Name of the feature
        task_id: ID of the task to update
        status: New status for the task
        notes: Optional notes about the status change
    
    Returns:
        Confirmation message
    """
    try:
        # Phase gate: tasks must be locked
        allowed, error_msg = _check_phase_gate(feature_name, "tasks")
        if not allowed:
            return inject_directives(error_msg)
        
        # Use file lock to prevent race conditions in multi-agent scenarios
        with _file_lock:
            # Read tasks from JSON source of truth
            tasks_data = read_tasks_json(feature_name)
            
            # Find and update the task
            task_found = False
            for task in tasks_data:
                if task["id"] == task_id:
                    task["status"] = status
                    task_found = True
                    break
            
            if not task_found:
                return inject_directives(f"✗ Task {task_id} not found in {feature_name}")
            
            # Write updated JSON
            feature_dir = get_feature_dir(feature_name)
            json_path = feature_dir / "tasks.json"
            json_path.write_text(json.dumps(tasks_data, indent=2), encoding='utf-8')
            
            # Regenerate markdown from JSON
            regenerate_tasks_md(feature_name)
        
        # Add to memory if completed (outside lock - memory_store has its own lock)
        if status == "completed":
            memory_store.add_memory(
                feature_name=feature_name,
                content=f"Completed task {task_id}: {notes}" if notes else f"Completed task {task_id}",
                memory_type="progress"
            )
        
        response = f"✓ Updated {task_id} status to '{status}'"
        if notes:
            response += f"\nNotes: {notes}"
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error updating task status: {str(e)}")


@mcp.tool()
def read_spec(
    feature_name: str,
    spec_type: Literal["requirements", "design", "tasks"]
) -> str:
    """
    Read a specification document.
    
    Args:
        feature_name: Name of the feature
        spec_type: Type of spec to read (requirements, design, or tasks)
    
    Returns:
        The specification document content
    """
    try:
        content = read_spec_file(feature_name, spec_type)
        return inject_directives(content)
    except Exception as e:
        return inject_directives(f"✗ Error reading spec: {str(e)}")


@mcp.tool()
def list_specs() -> str:
    """
    List all feature specifications.
    
    Returns:
        List of all feature names with their available specs
    """
    if not SPECS_DIR.exists():
        return inject_directives("No specifications found. Use initialize_spec to create one.")
    
    features = []
    for item in SPECS_DIR.iterdir():
        # Skip hidden directories like .system
        if item.is_dir() and not item.name.startswith('.'):
            specs = []
            if (item / "requirements.md").exists():
                specs.append("requirements")
            if (item / "design.md").exists():
                specs.append("design")
            if (item / "tasks.md").exists():
                specs.append("tasks")
            
            # Show all features, even if they have no specs yet
            if specs:
                features.append(f"- {item.name}: {', '.join(specs)}")
            else:
                features.append(f"- {item.name}: (initialized, no specs yet)")
    
    if not features:
        return inject_directives("No specifications found. Use initialize_spec to create one.")
    
    response = "## Available Feature Specifications\n\n" + "\n".join(features)
    return inject_directives(response)


@mcp.tool()
def search_specs(query: str, limit: int = 10, offset: int = 0, include_memories: bool = True) -> str:
    """
    Search across specification documents and optionally the memory store.
    
    Args:
        query: Search query string
        limit: Maximum number of file results to return (default 10)
        offset: Number of results to skip for pagination (default 0)
        include_memories: Also search the SQLite memory store (default True)
    
    Returns:
        Combined results grouped by source, labelled clearly
    """
    response_parts = []
    
    # Search spec files
    if SPECS_DIR.exists():
        file_results = []
        
        for feature_dir in SPECS_DIR.iterdir():
            if not feature_dir.is_dir() or feature_dir.name.startswith('.'):
                continue
            
            for spec_file in feature_dir.glob("*.md"):
                content = spec_file.read_text(encoding='utf-8')
                
                # Simple search - find lines containing query
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if query.lower() in line.lower():
                        # Get context (line before and after)
                        context_start = max(0, i - 1)
                        context_end = min(len(lines), i + 2)
                        context = '\n'.join(lines[context_start:context_end])
                        
                        file_results.append(
                            f"**{feature_dir.name}/{spec_file.name}** (line {i+1}):\n```\n{context}\n```\n"
                        )
        
        if file_results:
            # Apply pagination to file results
            total = len(file_results)
            paginated = file_results[offset:offset + limit]
            
            file_section = f"### From spec files\n"
            file_section += f"Showing {offset + 1}–{offset + len(paginated)} of {total}\n\n"
            file_section += "\n".join(paginated)
            
            if total > offset + limit:
                file_section += f"\n\nUse offset={offset + limit} to see more file results."
            
            response_parts.append(file_section)
    
    # Search memory store
    if include_memories:
        try:
            memory_results = memory_store.search_memory(query, limit=5)
            if memory_results:
                mem_lines = ["### From memory store\n"]
                for m in memory_results:
                    content_preview = m['content'][:120]
                    if len(m['content']) > 120:
                        content_preview += "..."
                    mem_lines.append(
                        f"- **[MEM-{m['id']}]** {m['feature_name']} · {m['memory_type']} — {content_preview}"
                    )
                response_parts.append("\n".join(mem_lines))
        except Exception:
            # Memory store might not be initialized, skip silently
            pass
    
    if not response_parts:
        return inject_directives(f"No results found for '{query}'")
    
    response = f"## Search Results for '{query}'\n\n" + "\n\n".join(response_parts)
    return inject_directives(response)


@mcp.tool()
def add_directive(directive: str, category: str = "general") -> str:
    """
    Add a project-wide directive (rule).
    
    Args:
        directive: The directive text
        category: Category for organizing directives
    
    Returns:
        Confirmation message
    """
    result = directive_store.add_directive(directive, category)
    response = f"✓ Added directive #{result['id']} in category '{category}':\n{directive}"
    return inject_directives(response)


@mcp.tool()
def remove_directive(directive_id: int) -> str:
    """
    Remove a project-wide directive.
    
    Args:
        directive_id: ID of the directive to remove
    
    Returns:
        Confirmation message
    """
    if directive_store.remove_directive(directive_id):
        return inject_directives(f"✓ Removed directive #{directive_id}")
    else:
        return inject_directives(f"✗ Directive #{directive_id} not found")


@mcp.tool()
def list_directives() -> str:
    """
    List all project-wide directives.
    
    Returns:
        List of all directives organized by category
    """
    directives = directive_store.list_directives()
    
    if not directives:
        return inject_directives("No directives defined. Use add_directive to create one.")
    
    # Group by category
    categories: dict[str, list[dict[str, Any]]] = {}
    for directive in directives:
        category = directive.get('category', 'general')
        if category not in categories:
            categories[category] = []
        categories[category].append(directive)
    
    lines = ["## Project Directives\n"]
    for category, cat_directives in sorted(categories.items()):
        lines.append(f"### {category.title()}")
        for directive in cat_directives:
            lines.append(f"- **#{directive['id']}**: {directive['text']}")
        lines.append("")
    
    return "\n".join(lines)


@mcp.tool()
def add_memory(
    feature_name: str,
    content: str,
    memory_type: str = "decision",
    metadata: dict[str, Any] | None = None
) -> str:
    """
    Add a memory (architectural decision, context, etc.) to the persistent store.
    
    Args:
        feature_name: Name of the feature this memory relates to
        content: The memory content
        memory_type: Type of memory (decision, context, constraint, etc.)
        metadata: Optional additional metadata
    
    Returns:
        Confirmation message
    """
    memory_id = memory_store.add_memory(feature_name, content, memory_type, metadata)
    response = f"✓ Added memory #{memory_id} for feature '{feature_name}' (type: {memory_type})"
    return inject_directives(response)


@mcp.tool()
def search_memory(query: str, limit: int = 10) -> str:
    """
    Search memories using full-text search.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
    
    Returns:
        Search results with matching memories
    """
    results = memory_store.search_memory(query, limit)
    
    if not results:
        return inject_directives(f"No memories found for '{query}'")
    
    lines = [f"## Memory Search Results for '{query}'\n"]
    for memory in results:
        lines.append(f"### Memory #{memory['id']} - {memory['feature_name']} ({memory['memory_type']})")
        lines.append(memory['content'])
        lines.append(f"*Created: {memory['created_at']}*")
        lines.append("")
    
    return inject_directives("\n".join(lines))


@mcp.tool()
def get_memories_by_feature(feature_name: str) -> str:
    """
    Get all memories for a specific feature.
    
    Args:
        feature_name: Name of the feature
    
    Returns:
        List of all memories for the feature
    """
    memories = memory_store.get_memories_by_feature(feature_name)
    
    if not memories:
        return inject_directives(f"No memories found for feature '{feature_name}'")
    
    lines = [f"## Memories for '{feature_name}'\n"]
    for memory in memories:
        lines.append(f"### Memory #{memory['id']} ({memory['memory_type']})")
        lines.append(memory['content'])
        lines.append(f"*Created: {memory['created_at']}*")
        lines.append("")
    
    return inject_directives("\n".join(lines))


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
    
    Returns:
        Hook execution result
    """
    try:
        timestamp = datetime.now().isoformat()
        
        if hook_type == "pre_task":
            # Read tasks from JSON
            tasks_data = read_tasks_json(feature_name)
            
            # Find the task
            task = None
            for t in tasks_data:
                if t["id"] == task_id:
                    task = t
                    break
            
            if not task:
                return inject_directives(f"✗ Task {task_id} not found in {feature_name}")
            
            # Check dependencies
            incomplete_deps = []
            if task.get("depends_on"):
                for dep_id in task["depends_on"]:
                    for dep_task in tasks_data:
                        if dep_task["id"] == dep_id:
                            if dep_task.get("status", "pending") != "completed":
                                incomplete_deps.append(f"{dep_id} ({dep_task.get('title', 'Unknown')})")
                            break
            
            if incomplete_deps:
                return inject_directives(
                    f"✗ Cannot start {task_id}: Incomplete dependencies\n\n"
                    f"The following tasks must be completed first:\n" +
                    "\n".join(f"  - {dep}" for dep in incomplete_deps)
                )
            
            # Get directives
            directives = directive_store.list_directives()
            shown = directives[:5]
            directives_text = "\n".join(f"- {d['text']}" for d in shown) if shown else "None"
            if len(directives) > 5:
                directives_text += f"\n  ... and {len(directives) - 5} more (call list_directives for full list)"
            
            # Get relevant memories
            memories = memory_store.get_memories_by_feature(feature_name)
            task_keywords = task.get("title", "").lower().split()
            relevant_memories = []
            for mem in memories:
                mem_text = mem["content"].lower()
                if any(keyword in mem_text for keyword in task_keywords if len(keyword) > 3):
                    relevant_memories.append(f"  - {mem['content'][:100]}...")
            
            memories_text = "\n".join(relevant_memories[:3]) if relevant_memories else "  None found"
            
            response = (
                f"🔄 Pre-task Hook: {task_id}\n"
                f"Feature: {feature_name}\n"
                f"Task: {task.get('title', 'Unknown')}\n\n"
                f"✓ Dependency Check: All dependencies completed\n\n"
                f"📋 Active Directives (top 5):\n{directives_text}\n\n"
                f"💡 Relevant Memories:\n{memories_text}\n\n"
                f"Ready to begin implementation."
            )
            
            return inject_directives(response)
        
        else:  # post_task
            if not implementation_summary:
                return inject_directives(
                    f"✗ implementation_summary is required for post_task hook"
                )
            
            # Store memory of what was done
            memory_store.add_memory(
                feature_name=feature_name,
                content=f"Task {task_id}: {implementation_summary}",
                memory_type="progress",
                metadata={"task_id": task_id, "timestamp": timestamp}
            )
            
            # Check for decision keywords
            decision_keywords = ["chose", "decided", "rejected", "instead of", "opted for", "selected"]
            has_decision = any(keyword in implementation_summary.lower() for keyword in decision_keywords)
            
            response = (
                f"✓ Post-task Hook: {task_id}\n"
                f"Feature: {feature_name}\n\n"
                f"📝 Implementation Summary:\n{implementation_summary}\n\n"
                f"💾 Memory stored for future reference\n"
            )
            
            if has_decision:
                response += (
                    f"\n💡 Decision detected in summary. "
                    f"Consider documenting this as an ADR in write_design."
                )
            
            response += (
                f"\n\nNext: Update task status with update_task_status('{feature_name}', '{task_id}', 'completed')\n"
                f"To see current progress, use get_feature_summary('{feature_name}')"
            )
            
            return inject_directives(response)
    
    except FileNotFoundError:
        return inject_directives(
            f"✗ Tasks not found for '{feature_name}'. Write tasks first using write_tasks."
        )
    except Exception as e:
        return inject_directives(f"✗ Error in {hook_type} hook: {str(e)}")


@mcp.tool()
def get_spec_phase(feature_name: str) -> str:
    """
    Get the current workflow phase of a feature.
    
    Phases: uninitialized → requirements → design → tasks → implementation → complete
    
    Args:
        feature_name: Name of the feature
    
    Returns:
        Current phase name and what is allowed next
    """
    try:
        phase_state = _get_phase(feature_name)
        current = phase_state.get("current_phase", "uninitialized")
        locked = phase_state.get("locked_phases", [])
        
        phase_order = ["requirements", "design", "tasks", "implementation"]
        
        # Determine what's next
        if current == "uninitialized":
            next_action = "Use initialize_spec and write_requirements to begin"
        elif current in phase_order:
            idx = phase_order.index(current)
            if current in locked:
                if idx + 1 < len(phase_order):
                    next_phase = phase_order[idx + 1]
                    next_action = f"Current phase is locked. Proceed to {next_phase} phase"
                else:
                    next_action = "All phases complete"
            else:
                next_action = f"Complete and approve {current} phase using approve_phase"
        else:
            next_action = "Unknown state"
        
        response = (
            f"## Phase Status for '{feature_name}'\n\n"
            f"**Current Phase:** {current}\n"
            f"**Locked Phases:** {', '.join(locked) if locked else 'None'}\n"
            f"**Last Updated:** {phase_state.get('last_updated', 'N/A')}\n\n"
            f"**Next Action:** {next_action}"
        )
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error getting phase: {str(e)}")


@mcp.tool()
def lock_phase(feature_name: str, phase: Literal["requirements", "design", "tasks"]) -> str:
    """
    Mark a phase as complete, enabling the next phase to begin.
    
    This is called internally by approve_phase. Use approve_phase for user-facing approvals.
    
    Args:
        feature_name: Name of the feature
        phase: Phase to lock (requirements, design, or tasks)
    
    Returns:
        Confirmation and next allowed action
    """
    try:
        phase_state = _get_phase(feature_name)
        locked_phases = phase_state.get("locked_phases", [])
        
        # Check if phase is already locked
        if phase in locked_phases:
            return inject_directives(f"✓ Phase '{phase}' is already locked for '{feature_name}'")
        
        # Add to locked phases
        locked_phases.append(phase)
        phase_state["locked_phases"] = locked_phases
        
        # Update current phase to next
        phase_order = ["requirements", "design", "tasks", "implementation"]
        if phase in phase_order:
            idx = phase_order.index(phase)
            if idx + 1 < len(phase_order):
                phase_state["current_phase"] = phase_order[idx + 1]
        
        _save_phase(feature_name, phase_state)
        
        response = f"✓ Locked '{phase}' phase for '{feature_name}'\n"
        if phase_state["current_phase"] != phase:
            response += f"Next phase: {phase_state['current_phase']}"
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error locking phase: {str(e)}")


@mcp.tool()
def approve_phase(
    feature_name: str,
    phase: Literal["requirements", "design", "tasks"],
    approved_by: str = "user",
    notes: str = ""
) -> str:
    """
    Record explicit approval of a completed phase and unlock the next phase.
    
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
    try:
        # Check that the phase exists (file must be written)
        phase_file_map = {
            "requirements": "requirements.md",
            "design": "design.md",
            "tasks": "tasks.md"
        }
        
        feature_dir = get_feature_dir(feature_name)
        spec_file = feature_dir / phase_file_map[phase]
        
        if not spec_file.exists():
            return inject_directives(
                f"✗ Cannot approve {phase} phase: specification file not found. "
                f"Write the {phase} specification first."
            )
        
        # Check phase order - can't approve design before requirements
        phase_state = _get_phase(feature_name)
        locked_phases = phase_state.get("locked_phases", [])
        
        if phase == "design" and "requirements" not in locked_phases:
            return inject_directives(
                f"✗ Cannot approve design phase: requirements phase must be approved first"
            )
        elif phase == "tasks" and "design" not in locked_phases:
            return inject_directives(
                f"✗ Cannot approve tasks phase: design phase must be approved first"
            )
        
        # Check feature dependencies when approving tasks phase
        if phase == "tasks":
            graph_file = SPECS_DIR / ".system" / "feature_graph.json"
            if graph_file.exists():
                graph_data = json.loads(graph_file.read_text(encoding='utf-8'))
                
                # Find dependencies for this feature
                incomplete_deps = []
                for dep in graph_data:
                    if dep["feature"] == feature_name:
                        depends_on = dep["depends_on"]
                        dep_phase_state = _get_phase(depends_on)
                        dep_phase = dep_phase_state.get("current_phase", "unknown")
                        
                        # Dependency must be in implementation or complete phase
                        if dep_phase not in ["implementation", "complete"]:
                            incomplete_deps.append(f"{depends_on} (currently in {dep_phase} phase)")
                
                if incomplete_deps:
                    return inject_directives(
                        f"✗ Cannot approve tasks phase: feature dependencies not complete\n\n"
                        f"The following features must reach implementation or complete phase first:\n" +
                        "\n".join(f"  - {dep}" for dep in incomplete_deps)
                    )
        
        # Lock the phase
        lock_result = lock_phase(feature_name, phase)
        
        # Write approval record
        approvals_file = feature_dir / "approvals.md"
        timestamp = datetime.now().isoformat()
        
        approval_entry = f"\n## {phase} — approved\n\n"
        approval_entry += f"- **Approved by:** {approved_by}\n"
        approval_entry += f"- **Timestamp:** {timestamp}\n"
        if notes:
            approval_entry += f"- **Notes:** {notes}\n"
        approval_entry += "\n"
        
        # Append to approvals file
        if approvals_file.exists():
            existing = approvals_file.read_text(encoding='utf-8')
            approvals_file.write_text(existing + approval_entry, encoding='utf-8')
        else:
            header = f"# Approvals for {feature_name}\n"
            approvals_file.write_text(header + approval_entry, encoding='utf-8')
        
        # Update phase state with approval metadata
        phase_state = _get_phase(feature_name)
        if "approvals" not in phase_state:
            phase_state["approvals"] = {}
        phase_state["approvals"][phase] = {
            "approved_by": approved_by,
            "timestamp": timestamp,
            "notes": notes
        }
        _save_phase(feature_name, phase_state)
        
        # Add to memory
        memory_store.add_memory(
            feature_name=feature_name,
            content=f"Phase '{phase}' approved by {approved_by}" + (f": {notes}" if notes else ""),
            memory_type="approval",
            metadata={"phase": phase, "approved_by": approved_by, "timestamp": timestamp}
        )
        
        response = (
            f"✓ Phase '{phase}' approved for '{feature_name}'\n"
            f"Approved by: {approved_by}\n"
            f"Approval recorded in: {approvals_file}\n\n"
        )
        
        # Add next step guidance
        phase_order = ["requirements", "design", "tasks"]
        if phase in phase_order:
            idx = phase_order.index(phase)
            if idx + 1 < len(phase_order):
                next_phase = phase_order[idx + 1]
                response += f"Next step: Write {next_phase} specification using write_{next_phase}"
            else:
                response += "Next step: Begin implementation using update_task_status"
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error approving phase: {str(e)}")


@mcp.tool()
def spec_history(feature_name: str, spec_type: str) -> str:
    """
    List all saved versions of a specification file with timestamps and sizes.
    
    Args:
        feature_name: Name of the feature
        spec_type: Type of spec ('requirements', 'design', or 'tasks')
    
    Returns:
        Formatted list of all versions with metadata
    """
    try:
        feature_dir = SPECS_DIR / feature_name
        if not feature_dir.exists():
            return inject_directives(f"✗ Feature '{feature_name}' not found")
        
        # Find all version files
        pattern = f"{spec_type}.v*.md"
        version_files = sorted(feature_dir.glob(pattern))
        
        if not version_files:
            return inject_directives(f"No version history found for {spec_type}.md")
        
        # Build response
        response = f"# Version History: {feature_name}/{spec_type}.md\n\n"
        
        for vfile in version_files:
            # Extract version number
            version = vfile.stem.split('.v')[1]
            
            # Get file stats
            stat = vfile.stat()
            size = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            response += f"## Version {version}\n"
            response += f"- File: {vfile.name}\n"
            response += f"- Modified: {mtime}\n"
            response += f"- Size: {size} bytes\n\n"
        
        # Check for changelog
        changelog_file = feature_dir / f"{spec_type}.changelog.md"
        if changelog_file.exists():
            response += f"\nChangelog available: {changelog_file.name}\n"
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error retrieving version history: {str(e)}")


@mcp.tool()
def diff_spec(feature_name: str, spec_type: str, version1: str, version2: str) -> str:
    """
    Show the differences between two versions of a specification.
    
    Args:
        feature_name: Name of the feature
        spec_type: Type of spec ('requirements', 'design', or 'tasks')
        version1: First version (number or "current" for current file)
        version2: Second version (number or "current" for current file)
    
    Returns:
        Unified diff showing changes between versions
    """
    try:
        feature_dir = SPECS_DIR / feature_name
        if not feature_dir.exists():
            return inject_directives(f"✗ Feature '{feature_name}' not found")
        
        # Helper to get file path and label
        def get_version_file(version: str) -> tuple[Path, str]:
            if str(version).lower() == "current":
                file_path = feature_dir / f"{spec_type}.md"
                label = f"{spec_type}.md (current)"
            else:
                try:
                    version_num = int(version)
                    file_path = feature_dir / f"{spec_type}.v{version_num}.md"
                    label = f"{spec_type}.v{version_num}.md"
                except ValueError:
                    raise ValueError(f"Invalid version: {version}. Use a number or 'current'")
            return file_path, label
        
        # Get version files
        v1_file, v1_label = get_version_file(version1)
        v2_file, v2_label = get_version_file(version2)
        
        if not v1_file.exists():
            return inject_directives(f"✗ Version '{version1}' not found")
        if not v2_file.exists():
            return inject_directives(f"✗ Version '{version2}' not found")
        
        # Read file contents
        v1_content = v1_file.read_text(encoding='utf-8').splitlines(keepends=True)
        v2_content = v2_file.read_text(encoding='utf-8').splitlines(keepends=True)
        
        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            v1_content,
            v2_content,
            fromfile=v1_label,
            tofile=v2_label,
            lineterm=''
        ))
        
        if not diff_lines:
            return inject_directives(f"No differences found between {version1} and {version2}")
        
        # Format response
        response = f"# Diff: {feature_name}/{spec_type}.md ({version1} → {version2})\n\n"
        response += "```diff\n"
        response += ''.join(diff_lines)
        response += "\n```\n"
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error generating diff: {str(e)}")


@mcp.tool()
def check_coverage(feature_name: str) -> str:
    """
    Check requirements traceability across specifications.
    
    Verifies that:
    - Each requirement appears in the design
    - Each requirement appears in at least one task
    - Each task references at least one requirement
    
    Args:
        feature_name: Name of the feature to check
    
    Returns:
        Coverage report showing gaps and summary
    """
    try:
        # Read all spec files
        feature_dir = SPECS_DIR / feature_name
        if not feature_dir.exists():
            return inject_directives(f"✗ Feature '{feature_name}' not found")
        
        req_file = feature_dir / "requirements.md"
        design_file = feature_dir / "design.md"
        tasks_file = feature_dir / "tasks.md"
        
        if not req_file.exists():
            return inject_directives(f"✗ No requirements.md found for '{feature_name}'")
        if not design_file.exists():
            return inject_directives(f"✗ No design.md found for '{feature_name}'")
        if not tasks_file.exists():
            return inject_directives(f"✗ No tasks.md found for '{feature_name}'")
        
        req_content = req_file.read_text(encoding='utf-8')
        design_content = design_file.read_text(encoding='utf-8')
        tasks_content = tasks_file.read_text(encoding='utf-8')
        
        # Extract requirement IDs
        req_ids = set(re.findall(r'REQ-\d+', req_content))
        task_ids = set(re.findall(r'TASK-\d+', tasks_content))
        
        lines = [f"## Coverage Report — {feature_name}\n"]
        gaps = 0
        
        # Check each requirement
        for req_id in sorted(req_ids):
            in_design = req_id in design_content
            in_tasks = req_id in tasks_content
            status = "✓" if (in_design and in_tasks) else "✗"
            if not (in_design and in_tasks):
                gaps += 1
            design_mark = "✓ In design" if in_design else "✗ Not in design"
            tasks_mark = "✓ In tasks" if in_tasks else "✗ No task references"
            lines.append(f"{status} {req_id}  {design_mark}  {tasks_mark}")
        
        # Check each task has requirement linkage
        for task_id in sorted(task_ids):
            # Find the task section in tasks.md
            task_section_match = re.search(
                rf'### {task_id}:.*?(?=### TASK-|\Z)', 
                tasks_content, 
                re.DOTALL
            )
            if task_section_match:
                section_text = task_section_match.group()
                has_req_ref = bool(re.search(r'REQ-\d+', section_text))
                if not has_req_ref:
                    gaps += 1
                    lines.append(f"✗ {task_id}  No requirement linkage found")
        
        covered = len(req_ids) - gaps
        lines.append(f"\nSummary: {covered}/{len(req_ids)} requirements fully covered · {gaps} gap(s) found")
        
        return inject_directives("\n".join(lines))
        
    except Exception as e:
        return inject_directives(f"✗ Error checking coverage: {str(e)}")


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
    try:
        # Check if feature exists
        feature_dir = SPECS_DIR / feature_name
        if not feature_dir.exists():
            return inject_directives(f"✗ Feature '{feature_name}' not found")
        
        # Read tasks from JSON
        try:
            tasks_data = read_tasks_json(feature_name)
        except FileNotFoundError:
            return inject_directives(f"✗ No tasks found for '{feature_name}'. Write tasks first.")
        
        # Get phase information
        phase_state = _get_phase(feature_name)
        current_phase = phase_state.get("current_phase", "unknown")
        
        # Find approval timestamp for current phase
        approval_info = ""
        if current_phase in phase_state.get("approvals", {}):
            approval_ts = phase_state["approvals"][current_phase].get("timestamp", "")
            if approval_ts:
                approval_info = f" ({current_phase} approved {approval_ts[:10]})"
        
        # Calculate task statistics
        total_tasks = len(tasks_data)
        completed_tasks = sum(1 for t in tasks_data if t.get("status") == "completed")
        in_progress_tasks = sum(1 for t in tasks_data if t.get("status") == "in_progress")
        
        # Calculate hours
        total_hours = sum(t.get("estimated_hours", 0.0) for t in tasks_data)
        completed_hours = sum(
            t.get("estimated_hours", 0.0) for t in tasks_data
            if t.get("status") == "completed"
        )
        remaining_hours = total_hours - completed_hours
        
        # Calculate progress percentages
        task_progress_pct = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        hours_progress_pct = (completed_hours / total_hours * 100) if total_hours > 0 else 0
        
        # Find blocked tasks
        blocked_tasks = []
        for task in tasks_data:
            if task.get("depends_on"):
                incomplete_deps = []
                for dep_id in task["depends_on"]:
                    for dep_task in tasks_data:
                        if dep_task["id"] == dep_id:
                            if dep_task.get("status", "pending") != "completed":
                                incomplete_deps.append(f"{dep_id} ({dep_task.get('status', 'pending')})")
                            break
                if incomplete_deps:
                    blocked_tasks.append(f"{task['id']} blocked by {', '.join(incomplete_deps)}")
        
        # Find next available task
        next_task = None
        for task in tasks_data:
            if task.get("status", "pending") == "pending":
                # Check if all dependencies are complete
                can_start = True
                if task.get("depends_on"):
                    for dep_id in task["depends_on"]:
                        for dep_task in tasks_data:
                            if dep_task["id"] == dep_id:
                                if dep_task.get("status", "pending") != "completed":
                                    can_start = False
                                break
                if can_start:
                    next_task = f"{task['id']} — {task.get('title', 'Unknown')}"
        
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
            if len(blocked_tasks) > 1:
                for blocked in blocked_tasks[1:]:
                    response += f"            {blocked}\n"
        
        if next_task:
            response += f"Next up:    {next_task}\n"
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error generating feature summary: {str(e)}")


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
    
    Returns:
        Confirmation message
    """
    try:
        # Verify both features exist
        feature_dir = SPECS_DIR / feature_name
        depends_dir = SPECS_DIR / depends_on_feature
        
        if not feature_dir.exists():
            return inject_directives(f"✗ Feature '{feature_name}' not found")
        if not depends_dir.exists():
            return inject_directives(f"✗ Feature '{depends_on_feature}' not found")
        
        # Load or create feature graph
        graph_file = SPECS_DIR / ".system" / "feature_graph.json"
        graph_file.parent.mkdir(parents=True, exist_ok=True)
        
        if graph_file.exists():
            graph_data = json.loads(graph_file.read_text(encoding='utf-8'))
        else:
            graph_data = []
        
        # Check if dependency already exists
        for dep in graph_data:
            if dep["feature"] == feature_name and dep["depends_on"] == depends_on_feature:
                return inject_directives(
                    f"✗ Dependency already exists: {feature_name} → {depends_on_feature}"
                )
        
        # Add new dependency
        new_dep = {
            "feature": feature_name,
            "depends_on": depends_on_feature,
            "notes": notes,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        graph_data.append(new_dep)
        
        # Save graph
        graph_file.write_text(json.dumps(graph_data, indent=2), encoding='utf-8')
        
        response = f"✓ Added feature dependency: {feature_name} → {depends_on_feature}"
        if notes:
            response += f"\nNotes: {notes}"
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error adding feature dependency: {str(e)}")


@mcp.tool()
def get_feature_graph() -> str:
    """
    Returns the full inter-feature dependency graph.
    
    Shows: all features and their current phases, dependency edges,
    which features are blocked by incomplete dependencies,
    and critical path estimate based on estimated_hours.
    
    Returns:
        Formatted dependency graph with status
    """
    try:
        # Load feature graph
        graph_file = SPECS_DIR / ".system" / "feature_graph.json"
        
        if not graph_file.exists():
            return inject_directives("No feature dependencies defined yet. Use add_feature_dependency to create one.")
        
        graph_data = json.loads(graph_file.read_text(encoding='utf-8'))
        
        if not graph_data:
            return inject_directives("No feature dependencies defined yet.")
        
        # Get all features and their phases
        feature_phases = {}
        if SPECS_DIR.exists():
            for item in SPECS_DIR.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    phase_state = _get_phase(item.name)
                    feature_phases[item.name] = phase_state.get("current_phase", "unknown")
        
        # Build response
        response = "## Feature Dependency Graph\n\n"
        
        # List all dependencies
        response += "### Dependencies\n\n"
        for dep in graph_data:
            feature = dep["feature"]
            depends_on = dep["depends_on"]
            notes = dep.get("notes", "")
            
            feature_phase = feature_phases.get(feature, "unknown")
            depends_phase = feature_phases.get(depends_on, "unknown")
            
            # Check if blocked
            blocked = depends_phase not in ["complete", "implementation"]
            status_icon = "🔴" if blocked else "🟢"
            
            response += f"{status_icon} **{feature}** ({feature_phase}) → **{depends_on}** ({depends_phase})\n"
            if notes:
                response += f"   _{notes}_\n"
            response += "\n"
        
        # Find blocked features
        blocked_features = []
        for dep in graph_data:
            depends_phase = feature_phases.get(dep["depends_on"], "unknown")
            if depends_phase not in ["complete", "implementation"]:
                blocked_features.append(dep["feature"])
        
        if blocked_features:
            response += f"### Blocked Features\n\n"
            for feature in set(blocked_features):
                blockers = [
                    dep["depends_on"] for dep in graph_data 
                    if dep["feature"] == feature and feature_phases.get(dep["depends_on"], "unknown") not in ["complete", "implementation"]
                ]
                response += f"- **{feature}**: waiting for {', '.join(blockers)}\n"
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error retrieving feature graph: {str(e)}")
        

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
    try:
        # Determine which features to check
        if feature_name:
            features_to_check = [feature_name]
            # Verify feature exists
            if not (SPECS_DIR / feature_name).exists():
                return inject_directives(f"✗ Feature '{feature_name}' not found")
        else:
            # Check all features
            if not SPECS_DIR.exists():
                return inject_directives("No specifications found.")
            features_to_check = [
                item.name for item in SPECS_DIR.iterdir()
                if item.is_dir() and not item.name.startswith('.')
            ]
        
        if not features_to_check:
            return inject_directives("No features to check.")
        
        # Run checks for each feature
        results = []
        healthy_count = 0
        warning_count = 0
        error_count = 0
        
        for feature in features_to_check:
            feature_dir = SPECS_DIR / feature
            issues = []
            warnings = []
            
            # Check 1: EARS compliance
            req_file = feature_dir / "requirements.md"
            if req_file.exists():
                content = req_file.read_text(encoding='utf-8')
                # Extract requirement texts
                req_pattern = r'### (REQ-\d+) \((\w+)\)\n\n(.+?)(?=\n###|\n##|\Z)'
                matches = re.findall(req_pattern, content, re.DOTALL)
                
                for req_id, priority, req_text in matches:
                    req_text = req_text.strip()
                    try:
                        # Validate EARS notation
                        Requirement(id=req_id, text=req_text, priority=priority)
                    except Exception as e:
                        issues.append(f"EARS violation in {req_id}")
            
            # Check 2: Task dependency cycles
            tasks_json = feature_dir / "tasks.json"
            if tasks_json.exists():
                try:
                    tasks_data = read_tasks_json(feature)
                    # Try to create TasksDoc which validates dependencies
                    TasksDoc(feature_name=feature, tasks=tasks_data)
                except Exception as e:
                    if "circular" in str(e).lower() or "cycle" in str(e).lower():
                        issues.append("Circular task dependencies detected")
            
            # Check 3: Requirements coverage
            if req_file.exists():
                design_file = feature_dir / "design.md"
                tasks_file = feature_dir / "tasks.md"
                
                if design_file.exists() and tasks_file.exists():
                    req_content = req_file.read_text(encoding='utf-8')
                    design_content = design_file.read_text(encoding='utf-8')
                    tasks_content = tasks_file.read_text(encoding='utf-8')
                    
                    req_ids = set(re.findall(r'REQ-\d+', req_content))
                    
                    for req_id in req_ids:
                        in_design = req_id in design_content
                        in_tasks = req_id in tasks_content
                        
                        if not in_design:
                            warnings.append(f"{req_id} not referenced in design")
                        if not in_tasks:
                            warnings.append(f"{req_id} has no task")
            
            # Check 4: Phase gate status
            phase_state = _get_phase(feature)
            current_phase = phase_state.get("current_phase", "unknown")
            locked_phases = phase_state.get("locked_phases", [])
            
            # Check 5: Cross-feature dependencies
            graph_file = SPECS_DIR / ".system" / "feature_graph.json"
            if graph_file.exists():
                graph_data = json.loads(graph_file.read_text(encoding='utf-8'))
                
                for dep in graph_data:
                    if dep["feature"] == feature:
                        depends_on = dep["depends_on"]
                        dep_phase_state = _get_phase(depends_on)
                        dep_phase = dep_phase_state.get("current_phase", "unknown")
                        
                        if current_phase == "implementation" and dep_phase not in ["implementation", "complete"]:
                            warnings.append(f"Depends on {depends_on} (in {dep_phase} phase)")
            
            # Check 6: Privacy filter check
            for spec_file in feature_dir.glob("*.md"):
                content = spec_file.read_text(encoding='utf-8')
                # Check for common unredacted patterns
                if re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}', content):
                    warnings.append(f"Possible unredacted email in {spec_file.name}")
                if re.search(r'\b\d{3}-\d{2}-\d{4}\b', content):
                    warnings.append(f"Possible SSN pattern in {spec_file.name}")
            
            # Determine status
            if issues:
                status = "🔴 Error"
                error_count += 1
            elif warnings:
                status = "🟡 Warning"
                warning_count += 1
            else:
                status = "🟢 Healthy"
                healthy_count += 1
            
            # Build feature result
            coverage_info = ""
            if req_file.exists() and design_file.exists() and tasks_file.exists():
                req_content = req_file.read_text(encoding='utf-8')
                req_ids = set(re.findall(r'REQ-\d+', req_content))
                if req_ids:
                    # Extract unique requirement IDs from warnings to avoid double-counting
                    uncovered_reqs = set()
                    for warning in warnings:
                        match = re.search(r'(REQ-\d+)', warning)
                        if match and ("has no task" in warning or "not referenced" in warning):
                            uncovered_reqs.add(match.group(1))
                    
                    covered = len(req_ids) - len(uncovered_reqs)
                    coverage_pct = (covered / len(req_ids) * 100) if req_ids else 0
                    coverage_info = f", coverage: {coverage_pct:.0f}%"
            
            result_line = f"{status:12} {feature:30} (phase: {current_phase}{coverage_info})"
            
            if issues:
                result_line += "\n" + "\n".join(f"           ✗ {issue}" for issue in issues)
            if warnings:
                result_line += "\n" + "\n".join(f"           ⚠ {warning}" for warning in warnings[:3])
                if len(warnings) > 3:
                    result_line += f"\n           ⚠ ... and {len(warnings) - 3} more warnings"
            
            results.append(result_line)
        
        # Build response
        if feature_name:
            response = f"# Health Check — {feature_name}\n\n"
        else:
            response = f"# Health Check — all features\n\n"
        
        response += "─" * 80 + "\n"
        response += "\n".join(results)
        response += "\n" + "─" * 80 + "\n\n"
        response += f"Overall: {healthy_count} healthy · {warning_count} warning · {error_count} error"
        
        return inject_directives(response)
        
    except Exception as e:
        return inject_directives(f"✗ Error running health check: {str(e)}")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    mcp.run()

# Made with Bob
