# Project Structure - Universal Spec MCP Server

## Directory Layout

```
universal-spec-mcp/
├── .bob/                           # Bob AI assistant configuration
│   ├── mcp.json                   # MCP server connection config
│   ├── modes/                     # Custom modes
│   │   └── bmad-spec-architect.json
│   ├── rules/                     # Workflow rules
│   │   └── spec-workflow.md
│   ├── skills/                    # Agent skill definitions
│   │   ├── bmad-analyst.md       # Mary - Requirements analyst
│   │   ├── bmad-architect.md     # Winston - System architect
│   │   ├── bmad-pm.md            # John - Product manager
│   │   ├── bmad-dev.md           # Amelia - Developer
│   │   └── bmad-help.md          # Help guide
│   └── steering/                  # Project context
│       ├── product.md            # Product vision and goals
│       ├── tech.md               # Technical architecture
│       └── structure.md          # This file
│
├── .specs/                        # Generated specifications (gitignored)
│   ├── .system/                  # System data (hidden from list_specs)
│   │   ├── directives.json       # Project-wide rules
│   │   └── memory.db             # Architectural decision memory
│   └── <feature-name>/           # Per-feature specifications
│       ├── README.md             # Feature overview
│       ├── requirements.md       # EARS notation requirements
│       ├── design.md             # Architecture and ADRs
│       └── tasks.md              # Implementation tasks
│
├── src/
│   └── universal_spec_mcp/       # Main package
│       ├── __init__.py           # Package initialization
│       ├── server.py             # MCP server with 14 tools
│       ├── privacy.py            # Privacy filter for sensitive data
│       ├── directive_store.py    # Directive management
│       └── memory_store.py       # Memory storage with FTS5
│
├── tests/                         # Test suite
│   ├── test_privacy.py           # Privacy filter tests
│   └── test_server.py            # Server and integration tests
│
├── docs/                          # Documentation
│   ├── Project Context_ Universal Spec MCP Server (1).md
│   └── Bob Prompt_ Rebuild Universal Spec MCP Server (1).md
│
├── .gitignore                     # Git ignore rules
├── pyproject.toml                 # Project metadata and dependencies
└── README.md                      # Project README (if exists)
```

## Module Organization

### Core Modules

**`server.py`** (773 lines)
- Main MCP server implementation
- 14 tool definitions
- Pydantic models for validation
- Helper functions for formatting
- Middleware for extra argument handling

**`privacy.py`** (85 lines)
- PrivacyFilter class
- Regex patterns for sensitive data
- Convenience functions
- Extensible pattern system

**`directive_store.py`** (180 lines)
- DirectiveStore class
- Thread-safe JSON operations
- CRUD operations for directives
- Context formatting

**`memory_store.py`** (297 lines)
- MemoryStore class
- SQLite with FTS5 integration
- Full-text search capabilities
- Memory CRUD operations

## Configuration Files

### `pyproject.toml`

Defines:
- Project metadata (name, version, description)
- Python version requirement (>=3.11)
- Dependencies (fastmcp, pydantic)
- Dev dependencies (pytest)
- Entry point script
- Build system (hatchling)

### `.bob/mcp.json`

Configures Bob to connect to the MCP server:
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

### `.gitignore`

Ignores:
- Python artifacts (`__pycache__`, `*.pyc`, etc.)
- Virtual environments (`venv/`, `.venv`)
- Build artifacts (`dist/`, `build/`, `*.egg-info`)
- IDE files (`.vscode/`, `.idea/`)
- Test artifacts (`.pytest_cache/`, `.coverage`)
- Generated specs (`.specs/`)
- OS files (`.DS_Store`, `Thumbs.db`)

## BMad Agent Structure

### Mode Definition

**`.bob/modes/bmad-spec-architect.json`**
- Defines the orchestrator mode
- Lists all agent skills
- References workflow rules
- Includes steering context

### Workflow Rules

**`.bob/rules/spec-workflow.md`**
- Defines the four-phase workflow
- Specifies agent responsibilities
- Documents validation rules
- Explains phase transitions

### Agent Skills

Each agent has a dedicated skill file:

**`bmad-analyst.md`** (Mary)
- Requirements gathering
- EARS notation documentation
- Tools: initialize_spec, write_requirements

**`bmad-architect.md`** (Winston)
- System design
- ADR documentation
- Tools: write_design, add_memory, search_memory

**`bmad-pm.md`** (John)
- Task breakdown
- Dependency management
- Tools: write_tasks

**`bmad-dev.md`** (Amelia)
- Task implementation
- Progress tracking
- Tools: update_task_status, run_hook

**`bmad-help.md`** (Help Guide)
- Workflow explanation
- Troubleshooting
- Tool reference

### Steering Files

**`product.md`**
- Product vision and goals
- User personas
- Success metrics

**`tech.md`**
- Technology stack
- Architecture overview
- Development workflow

**`structure.md`** (this file)
- Directory layout
- Module organization
- File purposes

## Specification Structure

### Feature Directory

Each feature gets its own directory under `.specs/`:

```
.specs/user-authentication/
├── README.md              # Feature overview
├── requirements.md        # Phase 1 output (Mary)
├── design.md             # Phase 2 output (Winston)
└── tasks.md              # Phase 3 output (John)
```

### Requirements Document Format

```markdown
# Requirements: <feature-name>

<description>

## Requirements

### REQ-001 (must)
THE system SHALL <requirement>

### REQ-002 (should)
WHEN <trigger> THE system SHALL <requirement>
```

### Design Document Format

```markdown
# Design: <feature-name>

## Architecture

<high-level architecture description>

## Components

- Component 1
- Component 2

## Architectural Decision Records

### ADR-001: <title>

**Context:**
<context>

**Decision:**
<decision>

**Consequences:**
<consequences>

**Alternatives Considered:**
<alternatives>
```

### Tasks Document Format

```markdown
# Tasks: <feature-name>

## Implementation Tasks

### TASK-001: <title>
**Status:** pending
**Depends on:** TASK-000
**Estimated hours:** 2.0

<description>
```

## System Data Structure

### Directives (JSON)

```json
[
  {
    "id": 1,
    "text": "Always use PostgreSQL for databases",
    "category": "architecture"
  },
  {
    "id": 2,
    "text": "Write unit tests for all services",
    "category": "testing"
  }
]
```

### Memory (SQLite)

**Tables:**

`memories` table:
- id (INTEGER PRIMARY KEY)
- feature_name (TEXT)
- content (TEXT)
- memory_type (TEXT)
- created_at (TEXT)
- metadata (TEXT, JSON)

`memories_fts` virtual table (FTS5):
- feature_name
- content
- memory_type

## Naming Conventions

### Files and Directories

- Use lowercase with hyphens for directories: `user-authentication/`
- Use lowercase with underscores for Python modules: `directive_store.py`
- Use lowercase with hyphens for markdown files: `spec-workflow.md`

### Code

- Classes: PascalCase (`PrivacyFilter`, `DirectiveStore`)
- Functions: snake_case (`initialize_spec`, `write_requirements`)
- Constants: UPPER_SNAKE_CASE (`SPECS_DIR`)
- Private members: prefix with underscore (`_lock`, `_read_directives`)

### Specifications

- Feature names: lowercase with hyphens (`user-authentication`)
- Requirement IDs: `REQ-001`, `REQ-002`, etc.
- ADR IDs: `ADR-001`, `ADR-002`, etc.
- Task IDs: `TASK-001`, `TASK-002`, etc.

## Import Structure

### Internal Imports

```python
from universal_spec_mcp.privacy import PrivacyFilter
from universal_spec_mcp.directive_store import DirectiveStore
from universal_spec_mcp.memory_store import MemoryStore
```

### External Imports

```python
from fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator
```

## Extension Points

### Adding New Tools

1. Define tool function in `server.py`
2. Decorate with `@mcp.tool()`
3. Add docstring with parameter descriptions
4. Implement validation and logic
5. Return formatted response with `inject_directives()`

### Adding New Privacy Patterns

```python
privacy_filter.add_pattern(
    r'CUSTOM-\d{6}',
    '[REDACTED_CUSTOM]'
)
```

### Adding New Agent Skills

1. Create skill file in `.bob/skills/`
2. Define agent personality and responsibilities
3. List MCP tools the agent uses
4. Provide workflow and examples
5. Add to mode configuration

## Best Practices

### Code Organization

- Keep modules focused and single-purpose
- Use type hints everywhere
- Write comprehensive docstrings
- Keep functions small (<50 lines)
- Use Pydantic for validation

### Testing

- Write tests alongside code
- Use fixtures for setup/teardown
- Test happy path and error cases
- Aim for high coverage (>90%)
- Use descriptive test names

### Documentation

- Keep steering files up to date
- Document architectural decisions
- Explain non-obvious code
- Provide examples in docstrings
- Update README for major changes

### Version Control

- Commit frequently with clear messages
- Don't commit `.specs/` directory
- Keep `.gitignore` comprehensive
- Tag releases semantically (v1.0.0)