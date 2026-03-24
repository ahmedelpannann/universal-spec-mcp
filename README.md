# Universal Spec Architect — MCP Server

A universal, spec-driven engineering MCP server that works with any MCP-compatible AI coding assistant. It enforces a structured three-phase workflow — Requirements, Design, and Tasks — before writing a single line of implementation code.

---

## Supported Assistants

| Assistant | Config File | Status |
|---|---|---|
| **IBM Bob** | `.bob/mcp.json` | Supported |
| **Cursor** | `.cursor/mcp.json` | Supported |
| **VS Code (GitHub Copilot)** | `.vscode/mcp.json` | Supported |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` | Supported |
| **Claude Desktop** | `claude_desktop_config.json` | Supported |
| **Cline (VS Code Extension)** | `cline_mcp_settings.json` | Supported |

---

## The Three-Phase Workflow

| Phase | File | Content |
|---|---|---|
| 1. Requirements | `requirements.md` | User stories in EARS notation (`WHEN... THE SYSTEM SHALL...`) |
| 2. Design | `design.md` | Architecture, sequence diagrams, data models, error handling |
| 3. Tasks | `tasks.md` | Discrete, trackable implementation tasks |

---

## Project Structure

```
universal-spec-mcp/
├── src/
│   └── universal_spec_mcp/
│       ├── __init__.py
│       └── server.py              # The MCP server — all tools defined here
├── tests/
│   └── test_server.py             # Full test suite (9 tests)
├── configs/
│   ├── cursor/
│   │   └── mcp.json               # Copy to .cursor/mcp.json
│   ├── vscode/
│   │   └── mcp.json               # Copy to .vscode/mcp.json
│   ├── windsurf/
│   │   └── mcp_config.json        # Merge into ~/.codeium/windsurf/mcp_config.json
│   ├── claude/
│   │   └── claude_desktop_config.json  # Merge into Claude Desktop config
│   └── cline/
│       └── cline_mcp_settings.json     # Merge into Cline MCP settings
├── .bob/
│   ├── mcp.json                   # IBM Bob MCP configuration
│   ├── modes/
│   │   └── spec-architect.json    # IBM Bob custom mode
│   ├── rules/
│   │   └── spec-workflow.md       # IBM Bob workflow rules
│   └── steering/
│       ├── product.md             # Fill in: product context
│       ├── tech.md                # Fill in: technology stack
│       └── structure.md           # Fill in: project structure
├── .specs/                        # Generated spec artifacts
├── SETUP_GUIDE.md                 # Per-assistant setup instructions
├── pyproject.toml
└── README.md
```

---

## Installation

**Prerequisites:** Python 3.11+, `uv` installed.

```bash
pip install fastmcp pydantic
# Or install as a package
pip install -e .
```

---

## Quick Setup (Any Assistant)

**Step 1** — Copy the right config file for your assistant (see table above and `SETUP_GUIDE.md`).

**Step 2** — Fill in the steering files in `.bob/steering/` with your project's product, tech stack, and structure details.

**Step 3** — Start your assistant and ask it to build a feature. The MCP server will enforce Requirements → Design → Tasks before any code is written.

---

## MCP Tools Reference

| Tool | Description |
|---|---|
| `initialize_spec(feature_name, workflow_variant)` | Creates the `.specs/{feature}/` directory and metadata. |
| `write_requirements(feature_name, requirements_data)` | Writes `requirements.md`. Validates EARS notation; rejects violations. |
| `write_design(feature_name, design_data)` | Writes `design.md` with structured sections. |
| `write_tasks(feature_name, tasks_data)` | Writes `tasks.md` with trackable tasks. |
| `update_task_status(feature_name, task_id, new_status)` | Updates a task's status in real-time. |
| `run_hook(hook_name, context)` | Executes a named hook (`pre_task`, `post_task`, `post_save`). |

---

## Built-in Security: Privacy Filter

The server includes a built-in **Privacy Filter** that automatically scrubs sensitive data from all AI-generated content *before* it is written to the `.specs/` directory. This prevents the assistant from accidentally leaking credentials into your project's git repository.

It automatically detects and redacts:
- AWS Access and Secret Keys
- GitHub Tokens
- OpenAI and Anthropic API Keys
- Generic API Keys and Bearer Tokens
- Passwords and SSH Private Keys
- Database Connection Strings
- Internal IP Addresses

---

## Running Tests

```bash
python3 tests/test_server.py
```

---

## EARS Notation Reference

Every requirement must follow the Easy Approach to Requirements Syntax (EARS):

```
[WHEN <trigger>] [WHILE <precondition>] THE <system> SHALL <response>
```

**Valid:** `WHEN a user submits valid credentials THE SYSTEM SHALL grant access`

**Invalid (rejected):** `Users should be able to log in` — missing SHALL

---

## Per-Assistant Setup

See `SETUP_GUIDE.md` for detailed, step-by-step instructions for each supported assistant.
