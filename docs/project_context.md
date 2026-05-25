# Project Context: Universal Spec MCP Server

**Author:** ahmed elpannann

This document provides the architectural context and design decisions for the `universal-spec-mcp` project. It serves as a reference for the BMad agents when rebuilding or extending the codebase.

## System Overview

The `universal-spec-mcp` project is a Model Context Protocol (MCP) server designed to enforce a structured, spec-driven development workflow on AI coding assistants. It acts as a bridge between the AI assistant (e.g., Bob, Cline, Cursor) and the project repository, ensuring that no code is generated before requirements, design, and tasks are properly documented and validated.

## Core Components

The system consists of four main layers:

1.  **The User:** Interacts with the AI assistant, providing feature descriptions and reviewing outputs.
2.  **BMad Agents:** A set of specialized personas (Analyst, Architect, Product Manager, Developer) defined by Bob skill files. These agents guide the user through the workflow and call the appropriate MCP tools.
3.  **MCP Server:** A Python-based server built using the `fastmcp` framework. It exposes 14 tools that the agents use to read, write, and validate specification documents.
4.  **Project Repository:** The local file system where the specification documents (`requirements.md`, `design.md`, `tasks.md`) and persistent data (`directives.json`, `memory.db`) are stored within the `.specs/` directory.

## Key Architectural Decisions

### 1. Spec-Driven Workflow

The core philosophy is that code generation must be preceded by a formal specification process. The workflow is divided into four phases, each managed by a specific BMad agent:

*   **Phase 1: Analysis (Mary):** Clarifies the problem and writes EARS-notation requirements.
*   **Phase 2: Architecture (Winston):** Designs the system and documents Architectural Decision Records (ADRs).
*   **Phase 3: Story Breakdown (John):** Breaks the design into discrete, trackable tasks with dependencies.
*   **Phase 4: Implementation (Amelia):** Implements the tasks and updates their status.

### 2. Strict Validation

The MCP server enforces strict validation rules to ensure the quality and consistency of the specifications:

*   **EARS Notation:** All requirements must follow the Easy Approach to Requirements Syntax (EARS) pattern (`[WHEN <trigger>] [WHILE <precondition>] THE <system> SHALL <response>`).
*   **Task Dependencies:** Tasks can only depend on other tasks defined within the same feature specification.
*   **Unique IDs:** Requirement and task IDs must be unique within a feature.

### 3. Privacy by Default

A `PrivacyFilter` intercepts all text before it is written to the specification files. It uses regular expressions to identify and redact sensitive information, such as AWS keys, GitHub tokens, and database connection strings. This prevents secrets from being accidentally committed to the repository.

### 4. Persistent Memory and Directives

The system maintains persistent context across sessions and features:

*   **Memory Store:** An SQLite database (`memory.db`) stores architectural decisions and context. It uses the FTS5 extension to enable full-text search, allowing agents to retrieve relevant past decisions.
*   **Directive Store:** A JSON file (`directives.json`) stores project-wide rules (e.g., "Always use PostgreSQL"). These directives are injected into every MCP tool response, ensuring the agents adhere to them.

### 5. Robust Tooling

The MCP server exposes 14 tools to support the workflow:

*   `initialize_spec`: Creates a new feature specification directory.
*   `write_requirements`, `write_design`, `write_tasks`: Write the respective specification documents.
*   `update_task_status`: Updates the status of a specific task.
*   `read_spec`: Reads a specification document.
*   `list_specs`, `search_specs`: Discover and search existing specifications.
*   `add_directive`, `remove_directive`, `list_directives`: Manage project-wide rules.
*   `add_memory`, `search_memory`, `get_memories_by_feature`: Manage persistent architectural context.
*   `run_hook`: Simulates pre/post task lifecycle events.

## Technology Stack

*   **Language:** Python 3.11+
*   **MCP Framework:** `fastmcp`
*   **Validation:** `pydantic`
*   **Testing:** `pytest`
*   **Database:** SQLite (with FTS5)
