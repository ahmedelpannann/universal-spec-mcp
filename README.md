# Universal Spec MCP Server

A Model Context Protocol (MCP) server that enforces a structured, spec-driven development workflow for AI coding assistants. Ensures no code is generated before requirements, design, and tasks are properly documented and validated.

## Overview

The Universal Spec MCP Server implements the **BMad workflow** - a four-phase approach to software development:

1. **Analysis (Mary)** - Document requirements in EARS notation
2. **Architecture (Winston)** - Design the system and document ADRs
3. **Story Breakdown (John)** - Break down into trackable tasks
4. **Implementation (Amelia)** - Implement and track progress

## Features

- ✅ **20 MCP Tools** for spec management (3 new in Wave 1, 3 new in Wave 2)
- ✅ **Phase Gate Enforcement** - No code before specs are approved
- ✅ **Explicit Approval Workflow** - User sign-off required for phase transitions
- ✅ **EARS Notation Validation** for requirements (improved in Wave 1)
- ✅ **Architectural Decision Records (ADRs)** for design decisions
- ✅ **Task Dependency Management** with circular dependency detection
- ✅ **Thread-Safe Operations** with file locking
- ✅ **Privacy Filter** automatically redacts sensitive data
- ✅ **Persistent Memory Store** with full-text search (SQLite + FTS5)
- ✅ **Project Directives** for consistent rules across features
- ✅ **BMad Agent Skills** for guided workflow
- ✅ **Configurable Specs Directory** via environment variable
- ✅ **Spec Versioning** - Automatic backups with changelog (NEW in Wave 2) ⭐
- ✅ **Requirements Traceability** - Verify coverage across specs (NEW in Wave 2) ⭐
- ✅ **JSON Task Storage** - Machine-readable source of truth (NEW in Wave 2) ⭐

## Installation

### Prerequisites

- Python 3.11 or higher
- pip

### Install from Source

```bash
# Clone the repository
git clone <repository-url>
cd universal-spec-mcp

# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

### Configuration

Set the specs directory location (optional):

```bash
# Default: .specs in current directory
export UNIVERSAL_SPEC_DIR=/path/to/specs

# Or in your shell profile
echo 'export UNIVERSAL_SPEC_DIR=/path/to/specs' >> ~/.bashrc
```

## Quick Start

### 1. Configure Bob (or your AI assistant)

Add to `.bob/mcp.json`:

```json
{
  "mcpServers": {
    "universal-spec-mcp": {
      "command": "uvx",
      "args": ["fastmcp", "run", "src/universal_spec_mcp/server.py"]
    }
  }
}
```

### 2. Activate BMad Mode

In Bob, switch to the **BMad Spec Architect** mode to access the workflow.

### 3. Start Your First Feature

```
User: "I want to build user authentication"
→ Mary (Analyst) will guide you through requirements
→ Winston (Architect) will design the system
→ John (PM) will break down tasks
→ Amelia (Developer) will implement
```

## MCP Tools

### Spec Management

- `initialize_spec(feature_name, description)` - Create a new feature spec
- `write_requirements(feature_name, description, requirements)` - Write requirements (Phase 1)
- `write_design(feature_name, architecture, adrs, components)` - Write design (Phase 2, requires approved requirements)
- `write_tasks(feature_name, tasks)` - Write task breakdown (Phase 3, requires approved design)
- `read_spec(feature_name, spec_type)` - Read a spec file
- `list_specs()` - List all features
- `search_specs(query)` - Search across specs

### Phase Management (Wave 1) ⭐

- `get_spec_phase(feature_name)` - Get current workflow phase and status
- `approve_phase(feature_name, phase, approved_by, notes)` - Approve a phase and unlock the next
- `lock_phase(feature_name, phase)` - Internal: Mark a phase as complete

### Task Management

- `update_task_status(feature_name, task_id, status, notes)` - Update task progress (requires approved tasks)
- `run_hook(hook_type, feature_name, task_id)` - Run lifecycle hooks (enhanced in Wave 2)

### Versioning & Traceability (NEW in Wave 2) ⭐

- `spec_history(feature_name, spec_type)` - List all saved versions with timestamps
- `diff_spec(feature_name, spec_type, version1, version2)` - Show differences between versions
- `check_coverage(feature_name)` - Verify requirements are traced through design to tasks

### Directives

- `add_directive(directive, category)` - Add a project-wide rule
- `remove_directive(directive_id)` - Remove a directive
- `list_directives()` - List all directives

### Memory

- `add_memory(feature_name, content, memory_type)` - Store a decision
- `search_memory(query)` - Search past decisions
- `get_memories_by_feature(feature_name)` - Get feature memories

## Project Structure

```
.specs/                    # Generated specifications (configurable via UNIVERSAL_SPEC_DIR)
├── .system/              # System data (hidden)
│   ├── directives.json   # Project directives
│   └── memory.db         # Memory store
└── <feature-name>/       # Per-feature specs
    ├── README.md
    ├── requirements.md   # EARS notation requirements
    ├── design.md         # Architecture and ADRs
    ├── tasks.md          # Implementation tasks (generated from tasks.json)
    ├── tasks.json        # Machine-readable task data (NEW in Wave 2)
    ├── phase_state.json  # Current workflow phase (Wave 1)
    ├── approvals.md      # Phase approval records (Wave 1)
    ├── requirements.v*.md # Versioned backups (NEW in Wave 2)
    ├── design.v*.md      # Versioned backups (NEW in Wave 2)
    ├── tasks.v*.md       # Versioned backups (NEW in Wave 2)
    └── *.changelog.md    # Version changelogs (NEW in Wave 2)
```

## EARS Notation

Requirements must follow the Easy Approach to Requirements Syntax:

```
[WHEN <trigger>] [WHILE <precondition>] THE <system> SHALL [<response>]
```

**Note:** Response text after SHALL is now optional (improved in Wave 1), allowing stub requirements during drafting.

### Examples

✅ **Valid:**
- `THE system SHALL authenticate users with email and password`
- `THE system SHALL authenticate` (minimal form, useful for drafting)
- `WHEN a user submits invalid credentials THE system SHALL display an error`
- `WHILE a user is authenticated THE system SHALL allow access to protected resources`

❌ **Invalid:**
- `Users can log in` (not EARS notation)
- `The system should authenticate users` (use SHALL, not should)

## Architectural Decision Records (ADRs)

Each significant design decision must be documented:

```markdown
### ADR-001: Use JWT for Authentication

**Context:**
We need stateless authentication for microservices.

**Decision:**
Use JWT tokens signed with RS256.

**Consequences:**
+ Stateless and scalable
- Cannot revoke tokens before expiration

**Alternatives Considered:**
- Session cookies: Rejected due to need for shared session store
```

## Privacy & Security

The privacy filter automatically redacts:
- AWS keys (AKIA...)
- GitHub tokens (ghp_, gho_, etc.)
- Anthropic keys (sk-ant-...)
- OpenAI keys (sk-...)
- Database connection strings
- Private keys (PEM format)
- JWT tokens

## Phase Gate Workflow (NEW in Wave 1) ⭐

The server enforces a strict phase progression:

1. **Requirements Phase** → Write requirements → Approve with `approve_phase`
2. **Design Phase** → Write design (blocked until requirements approved) → Approve
3. **Tasks Phase** → Write tasks (blocked until design approved) → Approve
4. **Implementation Phase** → Update task status (blocked until tasks approved)

### Example Workflow

```python
# Phase 1: Requirements
initialize_spec("user-auth", "User authentication system")
write_requirements("user-auth", "desc", [
    {"id": "REQ-001", "text": "THE system SHALL authenticate users", "priority": "must"}
])
approve_phase("user-auth", "requirements", approved_by="alice", notes="Reviewed with stakeholders")

# Phase 2: Design (now unlocked)
write_design("user-auth", "Layered architecture", [
    {"id": "ADR-001", "title": "Use JWT", "context": "...", "decision": "...", "consequences": "..."}
])
approve_phase("user-auth", "design", approved_by="bob")

# Phase 3: Tasks (now unlocked)
write_tasks("user-auth", [
    {"id": "TASK-001", "title": "Implement login", "description": "..."}
])
approve_phase("user-auth", "tasks", approved_by="alice")

# Phase 4: Implementation (now unlocked)
update_task_status("user-auth", "TASK-001", "completed")
```

## Development

### Run Tests

```bash
pytest tests/ -v
# Wave 1: 57 tests passing (up from 48)
```

### Run Server Directly

```bash
# Using uvx (recommended)
uvx fastmcp run src/universal_spec_mcp/server.py

# Or using the installed script
universal-spec-mcp
```

## BMad Agents

### Mary - The Analyst 📋
Clarifies requirements and writes them in EARS notation.

### Winston - The Architect 🏗️
Designs systems and documents architectural decisions.

### John - The Product Manager 📝
Breaks down designs into trackable implementation tasks.

### Amelia - The Developer 💻
Implements tasks and tracks progress.

### Help Guide 🤝
Explains the workflow and provides guidance.

## Wave 1 Improvements (2026-05-25)

### Bug Fixes
- **BUG-001**: Fixed EARS regex to allow optional response text after SHALL
- **BUG-002**: Added circular dependency detection for tasks (Kahn's algorithm)
- **BUG-003**: Added file locking to prevent race conditions in multi-agent scenarios

### Issues Resolved
- **ISSUE-001**: Removed dead middleware code
- **ISSUE-002**: Made specs directory configurable via `UNIVERSAL_SPEC_DIR` environment variable

### Enhancements
- **ENH-001**: Phase gate enforcement - blocks write operations until previous phase is approved
- **ENH-002**: Explicit approval workflow with `approve_phase` tool and approval records

## Technology Stack

- **Python 3.11+** - Modern Python with type hints
- **FastMCP** - MCP server framework
- **Pydantic** - Data validation with strict EARS notation
- **SQLite + FTS5** - Full-text search for memories
- **Threading** - File locks for concurrent safety
- **pytest** - Testing framework (57 tests)

## Contributing

Contributions are welcome! Please ensure:
- All tests pass (`pytest tests/ -v`)
- Code follows PEP 8
- Type hints are used
- Docstrings are provided

## License

[Add your license here]

## Support

For issues, questions, or contributions, please [open an issue](link-to-issues).

---

**Made with ❤️ using the BMad workflow**