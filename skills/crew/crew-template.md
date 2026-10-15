# Crew config — <project name>

Read by every agent of the `/crew` workflow. Keep it short: agents read it on every step.
Agents run only the commands this file names, so every section is filled: a real command,
`none`, or `omit` where marked optional. Never name a command that changes shared state
(deploy, apply, publish, migrate a live database).

## Project
<2–3 lines: what it is, stack and versions, constraints that shape every change
(e.g. "runs offline", "public API is semver-stable", "multiplayer, server-authoritative",
"output must be deterministic", "plan-only: never applied from here")>

## Rules
- <owner rules agents must not break: no migrations, no new dependencies without asking,
  accessibility level, style rules, files never to touch, secrets handling>
- <commands agents must never run, e.g. `terraform apply`, `npm publish`, deploy scripts>
- <anything unattended runs must avoid: sound, opening windows or browsers, network calls to prod>
- <commit style if not Conventional Commits; how version fields are bumped and how to resolve
  them in a merge conflict (e.g. "semver from the merged changes"), or "none">

## Gates
- gate: `<format + lint + typecheck, one command; the formatter in it is the one agents use>`
- test: `<test command, or none>`
- evidence: `<extra checks by area: e2e, golden/snapshot tests, benchmarks, fuzzing, a smoke run, a dry run; or none>`
- evidence record: <file or CI run that records which commit the evidence ran on, e.g.
  `target/evidence.stamp`; reviewers treat evidence from an older commit as unfinished. Or omit>

## Show it
- <how a person sees a change, by kind, with the command: a UI `pnpm shot <route>` (png), a game
  scene `scripts/screenshot.sh <scene>`, a CLI or compiler run on a sample input with stdout/stderr
  saved to a file, a perf change's benchmark table, infrastructure's saved plan or dry run. Or
  `none` (internals with nothing to look at).>

## Implement
- Skills to invoke: <e.g. superpowers:test-driven-development, or none>
- Implementer agent: <custom agent type from .claude/agents/ (give it `maxTurns: 150`: a cut-off
  implementer returns an empty report), or omit for general-purpose>
- Kept-in-sync docs: <docs that must change with the code: API docs, changelog, module READMEs; or none>

## References
- <products/projects/sources the prior-art researcher should study first, or none>

## Tickets (optional)
- Tracker: <file and section, e.g. `TODO.md` or `docs/status.md` "Next" numbered list; next free number. Or omit>
- Questions: <extra topics the crew-ticket skill asks about for this kind of project, e.g.
  multiplayer and gamepad for a game, browsers and accessibility for a website, backward
  compatibility of the language for a compiler, blast radius and accounts for infrastructure>

## Workflow field (optional)
One value per ticket, written by the crew-ticket skill and confirmed by the owner:
- `workflow: preview` — one "Show it" artifact to judge before building; the ticket stays open.
- `workflow: crew:quick` — read this repo, build, review.
- `workflow: crew:full` — default. The same build after web research.
<Tickets without the field: how to read older wording. A ticket saying "verify" or "no code" is
never auto-started. Or omit the section.>

## Verify before merge
- `<commands the orchestrator runs on the merged branch before merging to the default branch>`
