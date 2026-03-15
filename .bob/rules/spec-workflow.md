# Spec-Driven Workflow Rules

You are operating in a spec-driven development environment. You must strictly adhere to the following rules:

## 1. The 3-Phase Workflow
Never write implementation code before the spec is complete. You must follow these phases in order:
1. **Requirements:** Use the `write_requirements` tool. You MUST use EARS notation for all requirements (`[WHEN <trigger>] THE <system> SHALL <response>`).
2. **Design:** Use the `write_design` tool. Include Architecture, Sequence Diagrams, Data Models, and Error Handling.
3. **Tasks:** Use the `write_tasks` tool. Break the design down into discrete, trackable tasks.

## 2. Task Execution
When implementing code, you must track your progress:
- Before starting a task, use `run_hook` with `pre_task`.
- Update the task status to `in_progress` using `update_task_status`.
- Write the code.
- Update the task status to `completed` using `update_task_status`.
- After completing a task, use `run_hook` with `post_task`.

## 3. Steering Context
Always consider the context provided in the `.bob/steering/` directory (Product, Tech, Structure) when making design and implementation decisions.
