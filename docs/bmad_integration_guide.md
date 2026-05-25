# BMad + Spec-Driven MCP Integration Guide

## Overview

This project combines two complementary approaches to AI-assisted development:

- **The Spec-Driven MCP Server** — enforces a structured workflow at the tool level. The AI cannot skip phases because each phase is gated by a required MCP tool call.
- **The BMad Method** — provides named agent personas that guide the conversational layer. Each persona has a specific role, communication style, and set of responsibilities.

Together, they give you both **structural enforcement** (MCP) and **expert guidance** (BMad personas).

## The Four Agents

| Agent | Persona | Skill File | Phase | MCP Tool |
|---|---|---|---|---|
| Analyst | Mary | `bmad-analyst.md` | Analysis | `write_requirements` |
| Architect | Winston | `bmad-architect.md` | Architecture | `write_design` |
| Product Manager | John | `bmad-pm.md` | Story Breakdown | `write_tasks` |
| Developer | Amelia | `bmad-dev.md` | Implementation | `update_task_status` |

A fifth skill, `bmad-help.md`, provides orientation and a quick reference for the full workflow.

## File Structure

```
.bob/
├── modes/
│   ├── bmad-spec-architect.json   ← Full BMad orchestrator mode (recommended)
│   └── spec-architect.json        ← Legacy single-agent mode (still works)
├── rules/
│   └── spec-workflow.md           ← Phase rules and enforcement logic
├── skills/
│   ├── bmad-analyst.md            ← Mary: requirements and problem analysis
│   ├── bmad-architect.md          ← Winston: system design
│   ├── bmad-pm.md                 ← John: task breakdown
│   ├── bmad-dev.md                ← Amelia: implementation
│   └── bmad-help.md               ← Orientation and quick reference
└── steering/
    ├── product.md                 ← Your product context (fill this in)
    ├── tech.md                    ← Your technology stack (fill this in)
    └── structure.md               ← Your project structure (fill this in)
```

## Getting Started

### Step 1 — Fill in the Steering Files

Before starting any feature, fill in the three steering files in `.bob/steering/`. These give all agents the context they need to make good decisions.

- `product.md` — What are you building? Who is it for? What are the business goals?
- `tech.md` — What language, framework, database, and infrastructure are you using?
- `structure.md` — How is the codebase organised? Where do models, services, and tests live?

Example files are provided in `.bob/steering/` with the `_example` suffix.

### Step 2 — Activate the BMad Mode

In your AI assistant (Bob, Cline, Cursor, etc.), activate the `bmad-spec-architect` mode or tell the AI to load the skill files from `.bob/skills/`.

### Step 3 — Start with Mary

Tell the AI: *"Switch to the bmad-analyst skill. I want to build [feature name]."*

Mary will guide you through:
1. Clarifying the problem
2. Producing a product brief
3. Writing EARS-notation requirements via `write_requirements`

### Step 4 — Follow the Handoffs

Each agent ends their phase with an explicit handoff instruction. Follow it:

- Mary → *"Switch to the bmad-architect skill"*
- Winston → *"Switch to the bmad-pm skill"*
- John → *"Switch to the bmad-dev skill"*

### Step 5 — Implement with Amelia

Amelia works through the task list one task at a time, tracking status via `update_task_status`. When all tasks are `completed`, the feature is done.

## Comparison: BMad Mode vs Legacy Mode

| Feature | `bmad-spec-architect` | `spec-architect` (legacy) |
|---|---|---|
| Named agent personas | Yes (Mary, Winston, John, Amelia) | No |
| Phase handoffs | Explicit | Implicit |
| Product brief step | Yes (before requirements) | No |
| ADRs in design | Yes (Winston enforces this) | No |
| Task acceptance criteria | Yes (John enforces this) | No |
| MCP tool enforcement | Yes (same as legacy) | Yes |
| Backward compatible | Yes | Yes |

Both modes use the same MCP server and produce the same output files. The BMad mode adds a richer conversational layer on top.

## Using bmad-help

At any point, if you are unsure what to do next, tell the AI:

> "bmad-help — what should I do next?"

The AI will load the `bmad-help.md` skill and assess your current state based on which spec files exist.
