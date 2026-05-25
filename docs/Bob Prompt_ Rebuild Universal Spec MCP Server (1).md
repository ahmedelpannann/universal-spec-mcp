# Bob Prompt: Rebuild Universal Spec MCP Server

**Author:** ahmed elpannann

This prompt instructs Bob to rebuild the entire `universal-spec-mcp` codebase from scratch. It provides step-by-step instructions on how to structure the project, implement the MCP tools, and configure the BMad agent workflow.

## Instructions for Bob

1.  **Initialize the Project:**
    *   Create a new Python project named `universal-spec-mcp`.
    *   Set up a virtual environment and install the required dependencies: `fastmcp`, `pydantic`, `pytest`.
    *   Create the standard project structure: `src/universal_spec_mcp/`, `tests/`, `docs/`, `.bob/`.

2.  **Implement the Core Logic (`src/universal_spec_mcp/`):**
    *   **`privacy.py`:** Implement a `PrivacyFilter` class that uses regular expressions to redact sensitive information (e.g., API keys, tokens, connection strings) from text. Ensure the Anthropic key pattern (`sk-ant-...`) is checked before the generic OpenAI key pattern.
    *   **`directive_store.py`:** Implement a `DirectiveStore` class that manages persistent, project-wide rules (directives) stored in a JSON file (`.specs/.system/directives.json`). Use a `threading.Lock` to ensure thread safety during concurrent writes.
    *   **`memory_store.py`:** Implement a `MemoryStore` class that uses SQLite to store architectural decisions and context (`.specs/.system/memory.db`). Use SQLite's FTS5 extension to enable full-text search across memories.
    *   **`server.py`:** This is the main MCP server file.
        *   Define Pydantic models for the spec documents (`RequirementsDoc`, `DesignDoc`, `TasksDoc`) with `model_config = ConfigDict(extra='ignore')` to handle extra fields from LLMs.
        *   Implement a FastMCP middleware (`ExtraArgStripMiddleware`) to filter out unknown arguments from tool calls before Pydantic validation.
        *   Register the 14 MCP tools using the `@mcp.tool()` decorator: `initialize_spec`, `write_requirements`, `write_design`, `write_tasks`, `update_task_status`, `read_spec`, `list_specs`, `search_specs`, `add_directive`, `remove_directive`, `list_directives`, `add_memory`, `search_memory`, `get_memories_by_feature`, `run_hook`.
        *   Ensure `write_requirements` validates EARS notation.
        *   Ensure `write_tasks` validates task dependencies and checks for duplicate IDs.
        *   Ensure `list_specs` filters out hidden directories (e.g., `.system`).

3.  **Implement the Tests (`tests/`):**
    *   **`test_privacy.py`:** Write tests to verify the `PrivacyFilter` correctly redacts AWS keys, GitHub tokens, OpenAI keys, and Anthropic keys.
    *   **`test_server.py`:** Write comprehensive tests for all MCP tools. Use `pytest` fixtures to isolate the `.specs` directory during testing (e.g., using `tmp_path` and `monkeypatch`).

4.  **Configure the BMad Workflow (`.bob/`):**
    *   **`mcp.json`:** Configure Bob to connect to the `universal-spec-mcp` server using `uvx fastmcp run src/universal_spec_mcp/server.py`.
    *   **`modes/bmad-spec-architect.json`:** Define the orchestrator mode that coordinates the four BMad agents.
    *   **`rules/spec-workflow.md`:** Define the rules for the four-phase workflow (Analysis, Architecture, Story Breakdown, Implementation).
    *   **`skills/`:** Create the five skill files (`bmad-analyst.md`, `bmad-architect.md`, `bmad-pm.md`, `bmad-dev.md`, `bmad-help.md`) that define the behavior of each agent and map them to the corresponding MCP tools.
    *   **`steering/`:** Create the steering files (`product.md`, `tech.md`, `structure.md`) to provide project context.

5.  **Documentation (`docs/`):**
    *   Ensure all documentation, including the end-to-end exercise, is updated and reflects the BMad workflow.
    *   Remove any mentions of "manus" or "chatgpt" from the documentation and comments.
    *   Ensure the project name does not contain the word "procurement".

6.  **Final Review:**
    *   Run the test suite (`pytest tests/`) to ensure all tests pass.
    *   Verify that the BMad workflow functions correctly end-to-end.
