# Agent Knowledge Base

This directory contains persistent project knowledge for AI coding assistants and contributors.

## Purpose

Reduce repeated repository exploration and preserve important project knowledge across development sessions.

---

# Startup Procedure

Before working on a task:

1. Read [BOOTSTRAP.md](BOOTSTRAP.md).
2. Read [AGENTS.md](AGENTS.md).
3. Read [PROJECT_MAP.md](PROJECT_MAP.md).
4. Load only the skill files relevant to the current task.
5. Avoid unnecessary repository-wide searches.

---

# Directory Structure

```
.agent/
├── BOOTSTRAP.md         # Quick-start onboarding guide for agents
├── AGENTS.md            # High-level architecture, technologies, coding conventions, and workflows
├── PROJECT_MAP.md       # Directory layout and source file descriptions
├── DECISIONS.md         # History of major architectural and design decisions
├── LESSONS.md           # Debugging gotchas and solutions to prevent regression
└── skills/              # Subsystem-specific deep dives
    ├── analysis.md      # Stockfish engine and evaluation math
    ├── api.md           # External APIs and LLM integration
    ├── gui.md           # PyQt6 frontend architecture and threading
    └── storage.md       # Database schema and persistence layer
```

---

# Update Policy

Update project knowledge only after successful task completion.

Update:

* Architecture changes
* New subsystems
* Important design decisions
* Reusable debugging lessons
* Significant workflow improvements

Do not update for:

* Failed experiments
* Temporary debugging
* Session chatter
* One-off TODOs

---

# Documentation Principles

Prioritize:

* Accuracy
* Conciseness
* Stable knowledge
* Reusable information

Avoid:

* Duplication
* Excessive detail
* Temporary state
* Speculation

---

# Skill Files

We have the following subsystem-specific deep dives:

* [skills/analysis.md](skills/analysis.md) — Stockfish UCI integration, move evaluation classifications (Blunder, Mistake, etc.), accuracy math, and multi-PV performance.
* [skills/storage.md](skills/storage.md) — Database schema, cache and game history persistence, ConfigManager singleton rules, and duplicate detection.
* [skills/gui.md](skills/gui.md) — PyQt6 MainWindow architecture, QThread background worker patterns, centralized stylesheets, and the chessboard rendering engine.
* [skills/api.md](skills/api.md) — Integration with external APIs (Chess.com, Lichess), GitHub auto-updater, and LLM services for AI coach summaries.

Load only the skills needed for the current task.

---

# Decision Records

Review major architectural decisions, tradeoffs, and design rationale in [DECISIONS.md](DECISIONS.md).

---

# Lessons Learned

Review hard-earned debugging solutions and gotchas in [LESSONS.md](LESSONS.md) to prevent introducing regressions.

---

# Goal

Minimize token usage spent rediscovering project structure while maximizing implementation accuracy and consistency.
