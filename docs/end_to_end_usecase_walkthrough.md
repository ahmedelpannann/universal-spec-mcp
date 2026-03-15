# End-to-End Spec-Driven Use Case: Expense Report Submission

This document walks through a complete, realistic example of how the Universal Spec Architect MCP server operates when connected to an AI coding assistant (like Cline, Cursor, or IBM Bob). 

In this scenario, the user asks the assistant to build an **Expense Report Submission** feature. Instead of immediately writing code, the assistant uses the MCP server to enforce a rigorous three-phase engineering workflow.

---

## Phase 1: Initialization & Requirements

**User:**
> "I need to build an expense report submission feature. Employees should be able to submit receipts, and managers should approve or reject them."

**Assistant:**
> "Before writing any code, I will follow the spec-driven workflow. Let me initialize the spec for this feature."

**Tool Call:** `initialize_spec("expense-report-submission", "requirements-first")`
**Result:** Creates the `.specs/expense-report-submission/` directory.

**Assistant:**
> "Now I will draft the requirements using EARS notation. Every requirement must follow the strict `WHEN <trigger> THE SYSTEM SHALL <response>` format."

**Tool Call:** `write_requirements(...)`
The assistant passes a structured JSON object containing the requirements. The MCP server validates the EARS notation. If the assistant writes a vague requirement like *"Users should be able to upload files"*, the server rejects it. 

The assistant successfully submits:
- **REQ-001:** `WHEN an employee submits an expense report with at least one receipt THE SYSTEM SHALL create a new expense report record with status 'pending' and notify the employee's line manager by email`
- **REQ-002:** `WHEN an employee uploads a receipt file WHILE the file size is under 10MB and the format is PDF, PNG, or JPG THE SYSTEM SHALL store the file securely and attach it to the expense report`

**Result:** The server generates `requirements.md`.

---

## Phase 2: Technical Design

**Assistant:**
> "Requirements are validated and saved. Now I will produce the technical design covering architecture, data models, sequence diagrams, and error handling."

**Tool Call:** `write_design(...)`
The assistant reads the requirements and generates a structured design document. It decides to use PostgreSQL for data, IBM Cloud Object Storage for receipts, and RabbitMQ for payroll integration.

**Result:** The server generates `design.md` containing:
- **Architecture Overview**
- **Data Models** (ExpenseReport, ExpenseReceipt)
- **Sequence Diagrams** (Submit Expense, Manager Approval)
- **Error Handling Table** (e.g., 413 FILE_TOO_LARGE)

---

## Phase 3: Implementation Tasks

**Assistant:**
> "Design is complete. Now I will break the work into discrete, trackable implementation tasks. Only after this step will I write any code."

**Tool Call:** `write_tasks(...)`
The assistant breaks the design down into 7 sequential tasks.

**Result:** The server generates `tasks.md` containing:
- `[ ] TASK-001`: Create database migrations
- `[ ] TASK-002`: Implement SQLAlchemy models
- `[ ] TASK-003`: Implement DuplicateDetectionService
- `[ ] TASK-004`: Implement receipt file upload to COS
- `[ ] TASK-005`: Implement POST /api/expenses endpoint
- `[ ] TASK-006`: Implement PATCH approve/reject endpoints
- `[ ] TASK-007`: Write unit and integration tests

---

## Phase 4: Implementation & Hooks

Now the assistant actually starts writing code. For every task, it interacts with the MCP server to track progress and run automated checks.

**Assistant:**
> "Starting implementation of TASK-001."

**Tool Call:** `run_hook("pre_task", "Starting TASK-001")`
*(The server simulates running pre-task checks like linting or verifying steering rules).*

**Tool Call:** `update_task_status("TASK-001", "in_progress")`
*(The server updates `tasks.md` to show `[~] IN_PROGRESS`).*

*(The assistant writes the Alembic migration script in the workspace).*

**Tool Call:** `update_task_status("TASK-001", "completed")`
*(The server updates `tasks.md` to show `[x] COMPLETED`).*

**Tool Call:** `run_hook("post_task", "Completed TASK-001")`
*(The server simulates running post-task checks like unit tests).*

The assistant repeats this loop for TASK-002 through TASK-007 until the feature is fully built, tested, and documented.

---

## Why This Matters

If you had asked a standard coding assistant to "build an expense report feature," it would have immediately started writing random Python files. It likely would have forgotten to handle file size limits, duplicate detection, or database migrations.

By forcing the assistant through the **Universal Spec Architect MCP Server**, you guarantee that:
1. Edge cases are caught in the Requirements phase.
2. Architecture is agreed upon in the Design phase.
3. Code is written systematically against a trackable Task list.
