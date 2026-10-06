# Crew config — <project name>

Read by every agent of the `/crew` workflow. Keep it short: agents read it on every step.

## Project
<2–3 lines: what it is, stack and versions, constraints that shape every change
(e.g. "runs offline", "public API is semver-stable", "multiplayer, server-authoritative")>

## Rules
- <owner rules agents must not break: no migrations, no new dependencies without asking,
  accessibility level, style rules, files never to touch, secrets handling>
- <anything unattended runs must avoid: sound, opening browsers, network calls to prod>

## Gates
- gate: `<format + lint + typecheck, one command>`
- test: `<test command>`
- evidence: `<extra checks by area: e2e, screenshots, benchmarks, a smoke run>`

## Implement
- Skills to invoke: <e.g. superpowers:test-driven-development, or none>
- Implementer agent: <custom agent type from .claude/agents/, or omit for general-purpose>
- Kept-in-sync docs: <docs that must change with the code: API docs, changelog, module READMEs>

## References
- <products/projects/sources the prior-art researcher should study first>

## Verify before merge
- `<commands the orchestrator runs on the merged branch before merging to the default branch>`
