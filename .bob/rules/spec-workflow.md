# Spec-Driven Workflow Rules

These rules define the four-phase workflow for spec-driven development using the BMad agents.

## Core Principles

1. **No code before specs**: Code generation must be preceded by formal specifications
2. **Sequential phases**: Each phase must be completed before moving to the next
3. **Validation at every step**: All specs must pass validation before acceptance
4. **Persistent context**: Use the memory store to maintain context across features
5. **Directive adherence**: Always check and follow project directives

## Phase 1: Analysis (Mary)

**Objective**: Clarify the problem and document requirements in EARS notation

**Agent**: Mary (bmad-analyst)

**Activities**:
1. Interview the user to understand the feature requirements
2. Break down the feature into discrete requirements
3. Write each requirement in EARS notation:
   - `[WHEN <trigger>] [WHILE <precondition>] THE <system> SHALL <response>`
4. Assign priority to each requirement (must/should/could)
5. Use `initialize_spec` to create the feature directory
6. Use `write_requirements` to save the requirements

**Validation**:
- All requirements must follow EARS notation
- Each requirement must have a unique ID (REQ-001, REQ-002, etc.)
- Requirements must be clear, testable, and unambiguous

**Output**: `requirements.md` file in `.specs/<feature-name>/`

## Phase 2: Architecture (Winston)

**Objective**: Design the system and document architectural decisions

**Agent**: Winston (bmad-architect)

**Activities**:
1. Review the requirements from Phase 1
2. Design the high-level architecture
3. Identify key components and their interactions
4. Document Architectural Decision Records (ADRs) for significant decisions:
   - Context: What is the issue we're addressing?
   - Decision: What did we decide?
   - Consequences: What are the trade-offs?
   - Alternatives: What other options did we consider?
5. Use `search_memory` to find relevant past decisions
6. Use `write_design` to save the design
7. Use `add_memory` to store important decisions for future reference

**Validation**:
- Architecture must address all requirements
- Each ADR must have a unique ID (ADR-001, ADR-002, etc.)
- ADRs must include context, decision, and consequences
- Design must be feasible and follow project directives

**Output**: `design.md` file in `.specs/<feature-name>/`

## Phase 3: Story Breakdown (John)

**Objective**: Break the design into discrete, trackable implementation tasks

**Agent**: John (bmad-pm)

**Activities**:
1. Review the design from Phase 2
2. Break down the architecture into implementation tasks
3. Define task dependencies (which tasks must be completed before others)
4. Estimate effort for each task (in hours)
5. Ensure tasks are small enough to be completed independently
6. Use `write_tasks` to save the task breakdown

**Validation**:
- Each task must have a unique ID (TASK-001, TASK-002, etc.)
- Task dependencies must reference existing task IDs only
- Tasks must be granular enough to track progress
- All design components must be covered by tasks

**Output**: `tasks.md` file in `.specs/<feature-name>/`

## Phase 4: Implementation (Amelia)

**Objective**: Implement the tasks and track progress

**Agent**: Amelia (bmad-dev)

**Activities**:
1. Review the tasks from Phase 3
2. Select a task to implement (respecting dependencies)
3. Use `run_hook` with `pre_task` before starting implementation
4. Implement the task (write code, tests, documentation)
5. Use `run_hook` with `post_task` after completing implementation
6. Use `update_task_status` to mark the task as completed
7. Repeat for the next task

**Validation**:
- Tasks must be implemented in dependency order
- Code must pass all tests
- Implementation must match the design
- Task status must be updated accurately

**Output**: Working code and updated `tasks.md` with status tracking

## Cross-Phase Rules

### Directive Management

- Check `list_directives` at the start of each phase
- Add new directives with `add_directive` when establishing project-wide rules
- Remove outdated directives with `remove_directive` when rules change

### Memory Management

- Store architectural decisions in the memory store during Phase 2
- Search memories with `search_memory` when making similar decisions
- Use `get_memories_by_feature` to review past decisions for a feature

### Spec Discovery

- Use `list_specs` to see all available features
- Use `search_specs` to find relevant context across features
- Use `read_spec` to review existing specifications

### Privacy

- All sensitive information (API keys, passwords, tokens) is automatically redacted
- Never include real credentials in specifications
- Use placeholder values for examples

## Workflow Transitions

### Phase 1 → Phase 2
- Requirements must be written and validated
- User must approve the requirements
- Mary hands off to Winston

### Phase 2 → Phase 3
- Design must be written and validated
- ADRs must be documented
- Winston hands off to John

### Phase 3 → Phase 4
- Tasks must be written and validated
- Dependencies must be correct
- John hands off to Amelia

### Phase 4 → Complete
- All tasks must be completed
- Code must be tested and working
- Feature is ready for deployment

## Error Handling

If validation fails at any phase:
1. The agent must explain the error to the user
2. The agent must request corrections
3. The phase cannot proceed until validation passes

If the user wants to skip a phase:
1. Explain why the phase is necessary
2. Offer to expedite the phase with minimal documentation
3. Never skip validation

## Help and Support

If the user is confused or needs guidance:
- Activate the `bmad-help` skill
- The help agent will explain the workflow and available commands
- The help agent can recommend which phase to start with