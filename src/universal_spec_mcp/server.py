import json
import re
import sys
import os
from pathlib import Path
from typing import Any, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from fastmcp import FastMCP
from fastmcp.server.middleware.middleware import Middleware, MiddlewareContext, CallNext
import mcp.types as _mcp_types
from fastmcp.tools.tool import ToolResult as _ToolResult

# Allow running directly with `python server.py` as well as via package mode
_this_dir = Path(__file__).parent
if str(_this_dir) not in sys.path:
    sys.path.insert(0, str(_this_dir))

try:
    from .privacy import privacy_filter
    from .directive_store import DirectiveStore
    from .memory_store import MemoryStore
except ImportError:
    from privacy import privacy_filter
    from directive_store import DirectiveStore
    from memory_store import MemoryStore

# --- Middleware: strip extra arguments sent by LLMs (e.g. Cline sends 'task_progress') ---
class ExtraArgStripMiddleware(Middleware):
    """Silently discard any arguments that are not declared in the tool's input schema.
    
    Some LLM clients (e.g. Cline) inject extra fields such as 'task_progress' into
    every tool call. Pydantic's TypeAdapter raises a ValidationError for these unknown
    fields. This middleware filters them out before the call reaches the tool function.
    """
    async def on_call_tool(
        self,
        context: MiddlewareContext[_mcp_types.CallToolRequestParams],
        call_next: CallNext[_mcp_types.CallToolRequestParams, _ToolResult],
    ) -> _ToolResult:
        if context.fastmcp_context and context.message.arguments:
            server = context.fastmcp_context.fastmcp
            if server is not None:
                try:
                    tool = await server.get_tool(context.message.name)
                    if tool is not None:
                        schema = tool.parameters or {}
                        known_keys = set(schema.get("properties", {}).keys())
                        if known_keys:
                            filtered = {
                                k: v for k, v in context.message.arguments.items()
                                if k in known_keys
                            }
                            context = context.copy(
                                message=_mcp_types.CallToolRequestParams(
                                    name=context.message.name,
                                    arguments=filtered,
                                )
                            )
                except Exception:
                    pass  # If anything fails, pass through unmodified
        return await call_next(context)

# Initialize the MCP server
mcp = FastMCP("Universal Spec Architect", middleware=[ExtraArgStripMiddleware()])

# Base directory for all specs
SPECS_DIR = Path(".specs")

# Initialize DirectiveStore
directive_store = DirectiveStore(SPECS_DIR / ".system")

# Initialize MemoryStore
memory_store = MemoryStore(SPECS_DIR / ".system" / "memory.db")

# --- Pydantic Models for Strict LLM Outputs ---

class Requirement(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(..., description="Unique identifier for the requirement, e.g., REQ-001")
    title: str = Field(..., description="Short title of the requirement")
    ears_statement: str = Field(
        ..., 
        description="The requirement written strictly in EARS notation: [WHEN <trigger>] [WHILE <precondition>] THE <system> SHALL <response>"
    )
    acceptance_criteria: List[str] = Field(..., description="List of testable acceptance criteria")

class RequirementsDoc(BaseModel):
    model_config = ConfigDict(extra='ignore')
    feature_name: str
    description: str
    requirements: List[Requirement]

class DesignSection(BaseModel):
    model_config = ConfigDict(extra='ignore')
    title: str = Field(..., description="Section title, e.g., Architecture, Data Models, Error Handling")
    content: str = Field(..., description="Markdown content for this section")

class DesignDoc(BaseModel):
    model_config = ConfigDict(extra='ignore')
    feature_name: str
    sections: List[DesignSection]

class Task(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(..., description="Unique task identifier, e.g., TASK-001")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Detailed implementation instructions")
    status: Literal["todo", "in_progress", "completed"] = Field(default="todo")
    dependencies: List[str] = Field(default_factory=list, description="List of task IDs this task depends on")

class TasksDoc(BaseModel):
    model_config = ConfigDict(extra='ignore')
    feature_name: str
    tasks: List[Task]

# --- Helper Functions ---

def get_spec_dir(feature_name: str) -> Path:
    """Get the directory for a specific feature spec."""
    # FIX [INIT-04]: Reject empty feature names — previously created a spec at .specs/ root
    if not feature_name or not feature_name.strip():
        raise ValueError("feature_name cannot be empty")
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
def add_memory(feature_name: str, category: str, content: str) -> str:
    """
    Store an architectural decision, pattern, or context for future reference.
    Categories should be things like 'architecture', 'data_model', 'security', etc.
    """
    memory_id = memory_store.add_memory(feature_name, category, content)
    return f"Successfully stored memory {memory_id} for feature '{feature_name}' in category '{category}'."

@mcp.tool()
def search_memory(query: str) -> str:
    """
    Search the persistent memory store for past decisions, patterns, or context.
    Use this to ensure consistency with previous features.
    """
    # SQLite FTS5 requires queries to be formatted properly, simple fallback for basic queries
    # Replace spaces with AND for simple FTS matching
    fts_query = " AND ".join(query.split())
    
    try:
        results = memory_store.search_memories(fts_query)
    except Exception:
        # Fallback if FTS query syntax is invalid
        try:
            results = memory_store.search_memories(f'"{query}"')
        except Exception:
            return f"Failed to search memory with query: {query}"
            
    if not results:
        return f"No memories found matching '{query}'."
        
    formatted_results = [f"Search results for '{query}':"]
    for r in results:
        formatted_results.append(f"- [{r['feature_name']} | {r['category']}] {r['content']}")
        
    return "\n".join(formatted_results)

@mcp.tool()
def add_directive(content: str) -> str:
    """
    Add a new persistent directive (rule) that will be injected into all future tool responses.
    Use this to enforce project-wide constraints (e.g., "Always use PostgreSQL", "Never use relative imports").
    """
    directive_id = directive_store.add_directive(content)
    return f"Successfully added directive {directive_id}: '{content}'"

@mcp.tool()
def list_directives() -> str:
    """
    List all active directives currently enforced in the project.
    """
    directives = directive_store.list_directives()
    if not directives:
        return "No active directives."
    
    result = "Active Directives:\n"
    for d in directives:
        status = "ACTIVE" if d.get("active", True) else "INACTIVE"
        result += f"- [{d['id']}] ({status}) {d['content']}\n"
    return result

@mcp.tool()
def list_specs() -> str:
    """
    List all existing feature specifications in the project.
    Use this to discover what features have already been specced before creating a new one.
    """
    if not SPECS_DIR.exists():
        return "No specifications found. The .specs directory does not exist yet."
        
    specs = []
    for item in SPECS_DIR.iterdir():
        if item.is_dir():
            meta_path = item / "meta.json"
            status = "unknown"
            if meta_path.exists():
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                        status = meta.get("status", "unknown")
                except Exception:
                    pass
            specs.append(f"- {item.name} (Status: {status})")
            
    if not specs:
        return "No specifications found in the .specs directory."
        
    return "Existing specifications:\n" + "\n".join(specs)

@mcp.tool()
def search_specs(query: str) -> str:
    """
    Search across all existing specifications for a specific keyword or concept.
    Use this to find related features or check if a requirement already exists.
    """
    if not SPECS_DIR.exists():
        return "No specifications found to search."
        
    results = []
    query_lower = query.lower()
    
    for spec_dir in SPECS_DIR.iterdir():
        if not spec_dir.is_dir():
            continue
            
        # Search in requirements.md
        req_path = spec_dir / "requirements.md"
        if req_path.exists():
            try:
                with open(req_path, "r") as f:
                    content = f.read()
                    if query_lower in content.lower():
                        results.append(f"Match found in {spec_dir.name}/requirements.md")
            except Exception:
                pass
                
        # Search in design.md
        design_path = spec_dir / "design.md"
        if design_path.exists():
            try:
                with open(design_path, "r") as f:
                    content = f.read()
                    if query_lower in content.lower():
                        results.append(f"Match found in {spec_dir.name}/design.md")
            except Exception:
                pass
                
    if not results:
        return f"No matches found for '{query}' in any existing specifications."
        
    return f"Search results for '{query}':\n" + "\n".join(results)

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

    # FIX [REQ-02]: Detect duplicate requirement IDs before writing
    seen_ids = set()
    dup_ids = []
    for req in requirements_data.requirements:
        if req.id in seen_ids:
            dup_ids.append(req.id)
        seen_ids.add(req.id)
    if dup_ids:
        return f"Validation Failed: Duplicate requirement IDs found: {', '.join(dup_ids)}. Each requirement must have a unique ID."
        
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
        
    # Scrub sensitive data before writing
    scrubbed_md, md_result = privacy_filter.scrub(md_content)
    scrubbed_json, json_result = privacy_filter.scrub(requirements_data.model_dump_json(indent=2))
    
    with open(spec_dir / "requirements.md", "w") as f:
        f.write(scrubbed_md)
        
    # Save raw JSON for programmatic access later
    with open(spec_dir / "requirements.json", "w") as f:
        f.write(scrubbed_json)
        
    msg = f"Successfully wrote requirements.md for '{feature_name}'. All requirements passed EARS validation."
    if md_result.redactions > 0:
        msg += f" (Privacy Filter redacted {md_result.redactions} sensitive items: {', '.join(md_result.redacted_types)})"
        
    # Inject directives
    msg += directive_store.get_active_directives()
    
    # Inject relevant context from memory store
    recent_memories = memory_store.get_recent_memories(limit=3)
    if recent_memories:
        msg += "\n\nRELEVANT CONTEXT (from past decisions):\n"
        for m in recent_memories:
            msg += f"- [{m['feature_name']} | {m['category']}] {m['content']}\n"
            
    return msg

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
        
    # Scrub sensitive data before writing
    scrubbed_md, md_result = privacy_filter.scrub(md_content)
    
    with open(spec_dir / "design.md", "w") as f:
        f.write(scrubbed_md)
        
    msg = f"Successfully wrote design.md for '{feature_name}'."
    if md_result.redactions > 0:
        msg += f" (Privacy Filter redacted {md_result.redactions} sensitive items: {', '.join(md_result.redacted_types)})"
        
    # Inject directives
    msg += directive_store.get_active_directives()
    
    # Inject relevant context from memory store
    recent_memories = memory_store.get_recent_memories(limit=3)
    if recent_memories:
        msg += "\n\nRELEVANT CONTEXT (from past decisions):\n"
        for m in recent_memories:
            msg += f"- [{m['feature_name']} | {m['category']}] {m['content']}\n"
            
    return msg

@mcp.tool()
def write_tasks(feature_name: str, tasks_data: TasksDoc) -> str:
    """
    Write the tasks.md file based on the design.
    This breaks the work down into discrete, trackable implementation steps.
    """
    spec_dir = get_spec_dir(feature_name)

    # FIX [TASK-02]: Detect duplicate task IDs before writing
    seen_task_ids = set()
    dup_task_ids = []
    for task in tasks_data.tasks:
        if task.id in seen_task_ids:
            dup_task_ids.append(task.id)
        seen_task_ids.add(task.id)
    if dup_task_ids:
        return f"Validation Failed: Duplicate task IDs found: {', '.join(dup_task_ids)}. Each task must have a unique ID."

    # FIX [TASK-01]: Validate that all dependency references point to existing task IDs
    all_task_ids = {task.id for task in tasks_data.tasks}
    invalid_deps = []
    for task in tasks_data.tasks:
        for dep in task.dependencies:
            if dep not in all_task_ids:
                invalid_deps.append(f"{task.id} depends on unknown '{dep}'")
    if invalid_deps:
        return f"Validation Failed: Invalid task dependencies: {'; '.join(invalid_deps)}. All dependency IDs must reference tasks defined in this spec."

    # Generate Markdown
    md_content = f"# Implementation Tasks: {tasks_data.feature_name}\n\n"
    
    for task in tasks_data.tasks:
        status_marker = "[ ]" if task.status == "todo" else ("[~]" if task.status == "in_progress" else "[x]")
        md_content += f"### {task.id}: {task.title}\n"
        md_content += f"Status: {status_marker} {task.status.upper()}\n\n"
        md_content += f"{task.description}\n\n"
        if task.dependencies:
            md_content += f"**Dependencies:** {', '.join(task.dependencies)}\n\n"
            
    # Scrub sensitive data before writing
    scrubbed_md, md_result = privacy_filter.scrub(md_content)
    scrubbed_json, json_result = privacy_filter.scrub(tasks_data.model_dump_json(indent=2))
    
    with open(spec_dir / "tasks.md", "w") as f:
        f.write(scrubbed_md)
        
    # Save raw JSON for programmatic tracking
    with open(spec_dir / "tasks.json", "w") as f:
        f.write(scrubbed_json)
        
    msg = f"Successfully wrote tasks.md for '{feature_name}'. Ready for implementation phase."
    if md_result.redactions > 0:
        msg += f" (Privacy Filter redacted {md_result.redactions} sensitive items: {', '.join(md_result.redacted_types)})"
        
    # Inject directives
    msg += directive_store.get_active_directives()
    
    # Inject relevant context from memory store
    recent_memories = memory_store.get_recent_memories(limit=3)
    if recent_memories:
        msg += "\n\nRELEVANT CONTEXT (from past decisions):\n"
        for m in recent_memories:
            msg += f"- [{m['feature_name']} | {m['category']}] {m['content']}\n"
            
    return msg

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

# NOTE: mcp.run() is placed here at the very end, AFTER all @mcp.tool() decorators
# are registered. Previously it was placed before update_task_status and run_hook,
# which caused those 2 tools to be invisible to MCP clients (only 4/6 tools worked).
if __name__ == "__main__":
    mcp.run()
