# Technical Context - Universal Spec MCP Server

## Technology Stack

### Core Technologies

- **Language**: Python 3.11+
- **MCP Framework**: FastMCP 2.0+
- **Validation**: Pydantic 2.0+
- **Database**: SQLite with FTS5 (Full-Text Search)
- **Testing**: pytest 7.0+

### Why These Choices?

**Python 3.11+**
- Excellent AI/ML ecosystem
- Strong typing support with type hints
- Great for rapid development
- Wide adoption in the AI tools space

**FastMCP**
- Purpose-built for MCP servers
- Simple, declarative API
- Built-in tool registration
- Excellent documentation

**Pydantic**
- Robust data validation
- Automatic type conversion
- Clear error messages
- Perfect for validating specs

**SQLite with FTS5**
- Zero-configuration database
- Full-text search built-in
- Perfect for local storage
- No external dependencies

**pytest**
- Industry standard for Python testing
- Rich plugin ecosystem
- Clear, readable test syntax
- Excellent fixtures support

## Architecture Overview

### System Layers

```
┌─────────────────────────────────────┐
│   AI Assistant (Bob, Cline, etc.)  │
├─────────────────────────────────────┤
│         BMad Agent Skills           │
│  (Mary, Winston, John, Amelia)     │
├─────────────────────────────────────┤
│         MCP Server (FastMCP)        │
│  - 14 Tools                         │
│  - Validation Middleware            │
│  - Privacy Filter                   │
├─────────────────────────────────────┤
│      Persistent Storage Layer       │
│  - Directive Store (JSON)           │
│  - Memory Store (SQLite + FTS5)     │
│  - Spec Files (Markdown)            │
└─────────────────────────────────────┘
```

### Core Components

**1. MCP Server (`server.py`)**
- Exposes 14 tools via FastMCP
- Validates all inputs using Pydantic models
- Applies privacy filtering to all outputs
- Injects directives into responses

**2. Privacy Filter (`privacy.py`)**
- Regex-based pattern matching
- Redacts sensitive information (API keys, passwords, tokens)
- Extensible pattern system
- Applied automatically to all spec writes

**3. Directive Store (`directive_store.py`)**
- Thread-safe JSON storage
- CRUD operations for directives
- Category-based organization
- Context formatting for injection

**4. Memory Store (`memory_store.py`)**
- SQLite database with FTS5
- Full-text search across memories
- Feature-based organization
- Metadata support for rich context

## Data Models

### Specification Documents

**Requirements Document**
```python
class Requirement:
    id: str              # REQ-001, REQ-002, etc.
    text: str            # EARS notation
    priority: Literal["must", "should", "could"]

class RequirementsDoc:
    feature_name: str
    description: str
    requirements: list[Requirement]
```

**Design Document**
```python
class ADR:
    id: str              # ADR-001, ADR-002, etc.
    title: str
    context: str
    decision: str
    consequences: str
    alternatives: str

class DesignDoc:
    feature_name: str
    architecture: str
    adrs: list[ADR]
    components: list[str]
```

**Tasks Document**
```python
class Task:
    id: str              # TASK-001, TASK-002, etc.
    title: str
    description: str
    status: Literal["pending", "in_progress", "completed", "blocked"]
    depends_on: list[str]
    estimated_hours: float

class TasksDoc:
    feature_name: str
    tasks: list[Task]
```

## File System Structure

```
project-root/
├── .specs/                    # All specifications
│   ├── .system/              # System data (hidden)
│   │   ├── directives.json   # Project directives
│   │   └── memory.db         # Memory store
│   ├── feature-1/            # Feature specs
│   │   ├── README.md
│   │   ├── requirements.md
│   │   ├── design.md
│   │   └── tasks.md
│   └── feature-2/
│       └── ...
├── src/
│   └── universal_spec_mcp/
│       ├── __init__.py
│       ├── server.py         # Main MCP server
│       ├── privacy.py        # Privacy filter
│       ├── directive_store.py
│       └── memory_store.py
├── tests/
│   ├── test_privacy.py
│   └── test_server.py
├── .bob/                     # Bob configuration
│   ├── mcp.json             # MCP server config
│   ├── modes/               # BMad mode
│   ├── rules/               # Workflow rules
│   ├── skills/              # Agent skills
│   └── steering/            # Context files
└── pyproject.toml
```

## Validation Rules

### EARS Notation Validation

Requirements must match this pattern:
```regex
(?:WHEN\s+.+?\s+)?(?:WHILE\s+.+?\s+)?THE\s+.+?\s+SHALL\s+.+
```

Examples:
- ✅ `THE system SHALL authenticate users`
- ✅ `WHEN a user logs in THE system SHALL verify credentials`
- ❌ `Users can log in` (not EARS)

### Task Dependency Validation

- All task IDs must be unique within a feature
- Dependencies must reference existing task IDs
- No circular dependencies allowed

### Privacy Validation

Automatically redact:
- AWS keys (AKIA...)
- GitHub tokens (ghp_, gho_, etc.)
- Anthropic keys (sk-ant-...)
- OpenAI keys (sk-...)
- Database connection strings
- Private keys (PEM format)
- JWT tokens

## Performance Considerations

### SQLite FTS5

- Full-text search is fast for up to millions of records
- Indexes are automatically maintained
- Query performance is O(log n) for most operations

### File System

- Markdown files are small and fast to read/write
- Directory structure allows for easy navigation
- No database overhead for spec storage

### Thread Safety

- Directive store uses threading.Lock for concurrent writes
- Memory store uses SQLite's built-in locking
- File writes are atomic at the OS level

## Security Considerations

### Privacy Filter

- Runs on all spec writes
- Cannot be disabled
- Patterns are comprehensive but not exhaustive
- Users should still review specs before committing

### Data Storage

- All data is stored locally
- No external API calls
- No telemetry or tracking
- User has full control

### Validation

- Pydantic validates all inputs
- SQL injection is prevented by parameterized queries
- Path traversal is prevented by Path validation

## Testing Strategy

### Unit Tests

- Test each component in isolation
- Mock external dependencies
- Use pytest fixtures for setup/teardown
- Aim for >90% code coverage

### Integration Tests

- Test MCP tools end-to-end
- Use temporary directories for isolation
- Test validation rules thoroughly
- Test error handling

### Test Organization

```python
tests/
├── test_privacy.py          # Privacy filter tests
└── test_server.py           # Server and tool tests
    ├── TestRequirementModel
    ├── TestDesignDoc
    ├── TestTasksDoc
    ├── TestDirectiveStore
    ├── TestMemoryStore
    └── TestServerTools
```

## Development Workflow

### Local Development

1. Create virtual environment: `python -m venv venv`
2. Activate: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
3. Install dependencies: `pip install -e ".[dev]"`
4. Run tests: `pytest tests/ -v`
5. Run server: `uvx fastmcp run src/universal_spec_mcp/server.py`

### Code Style

- Follow PEP 8
- Use type hints everywhere
- Write docstrings for public APIs
- Keep functions small and focused
- Prefer composition over inheritance

## Deployment

### As MCP Server

Configure in `.bob/mcp.json`:
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

### As Python Package

Install from source:
```bash
pip install -e .
```

Run directly:
```bash
universal-spec-mcp
```

## Monitoring and Debugging

### Logging

- FastMCP provides built-in logging
- Use Python's logging module for custom logs
- Log levels: DEBUG, INFO, WARNING, ERROR

### Debugging

- Use pytest's `-v` flag for verbose output
- Use `--pdb` to drop into debugger on failure
- Check `.specs/.system/` for persistent data
- Review spec files for validation issues

## Future Technical Improvements

- **Async support**: Make all I/O operations async
- **Caching**: Cache frequently accessed specs
- **Compression**: Compress old specs to save space
- **Backup**: Automatic backup of memory.db
- **Migration system**: Version and migrate data schemas
- **Performance metrics**: Track tool execution times