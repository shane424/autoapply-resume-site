# [Project Name] — CLAUDE.md

> Project-specific rules for Claude Code. Extends ~/.claude/CLAUDE.md.
> Anything here overrides global defaults for this project only.

---

## What This Project Is

<!-- One paragraph. What is it, what does it do, who is it for. -->
[FILL IN]

## Current Phase
<!-- Pre-launch / Alpha / Beta / Live / Scaling -->
Phase: [FILL IN]
Priority right now: [FILL IN]

---

## Stack

| Layer | Technology |
|---|---|
| Backend | [FILL IN] |
| Frontend | [FILL IN] |
| Database | [FILL IN] |
| Key APIs | [FILL IN] |
| Hosting | [FILL IN] |

---

## Project-Specific Code Rules

<!-- These override global defaults. Only add rules that differ from ~/.claude/CLAUDE.md -->

1. [e.g. "Vanilla JS only — no framework imports, no npm packages for frontend"]
2. [e.g. "All DB queries must include tenant_id filter — never query without it"]
3. [e.g. "GDScript 4.x only — never use 3.x syntax"]
4. [e.g. "API responses always use envelope: { success, data, error }"]

---

## Directory Structure

```
[project-root]/
├── [FILL IN]
└── [FILL IN]
```

---

## Build & Run Commands

```bash
# Install
[FILL IN]

# Dev server
[FILL IN]

# Test
[FILL IN]

# Build/deploy
[FILL IN]
```

---

## Active Context Files

<!-- Tell Claude which scaffold files are present and active in this project -->

- [ ] `docs/project.md` — project identity
- [ ] `docs/next_steps.md` — current priorities
- [ ] `docs/roadmap.md` — phased plan
- [ ] `docs/architecture.md` — system design patterns
- [ ] `docs/bug_log.md` — known issues
- [ ] `docs/art_bible.md` — visual style rules
- [ ] `docs/asset_manifest.md` — asset tracker
- [ ] `docs/trading_system.md` — trading rules

---

## Request Routing (project-specific overrides)

<!-- Only add rows that differ from the global workflow router -->

| Request type | Project-specific rule |
|---|---|
| [e.g. "New endpoint"] | [e.g. "Check architecture.md for route pattern first. Follow existing middleware chain."] |
| [e.g. "Art prompt"] | [e.g. "16-bit pixel art only — see art_bible.md. Ignore global gothic-cute default."] |

---

## Hard Rules for This Project

<!-- Non-negotiables. Claude must follow these without exception. -->

1. [FILL IN]
2. [FILL IN]

---

## Known Gotchas

<!-- Things Claude gets wrong on this project. Add as you discover them. -->

- [e.g. "The `reports` module uses a different DB connection than the rest of the app — don't consolidate"]
- [e.g. "Shopify webhooks must be verified with HMAC before processing — never skip this"]
