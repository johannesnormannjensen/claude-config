---
name: crew
description: Use when the owner types /crew <request>, /crew init, or asks for "the usual research, plan, implement, review flow" on a feature in any git repo. Runs the crew workflow on its own branch and worktree, then the orchestrator verifies and merges.
---

# /crew: research → plan → implement → review

One request becomes one branch in its own git worktree. Three researchers (prior art, craft,
code audit) feed a planner that cuts at most 3 vertical slices. Each slice gets an
implementer, a strict reviewer and one fix round. A final reviewer checks the whole branch.
You (the orchestrator) verify and merge.

| Command | Does |
|---------|------|
| `/crew <request>` | full run (~1 h) |
| `/crew quick: <request>` | audit-only research (~30 min); strip the prefix from `ask` |
| `/crew init` | write `.claude/crew.md` for this repo, nothing else |

## 0. Setup (first run in a repo, or `/crew init`)

`ROOT=$(git rev-parse --show-toplevel)`. If `$ROOT/.claude/crew.md` is missing, draft it:
read README, AGENTS.md/CLAUDE.md, the package manifest (package.json, Cargo.toml,
pyproject.toml, go.mod, *.csproj, Gemfile…), Makefile/justfile, CI config and lint/format
config. Fill [the template](crew-template.md); every command must be one you found or ran, not
guessed. Run the gate and test commands once to confirm they work. Show the draft to the owner,
then commit it on the default branch: worktrees start from `origin/<default>`, so an
uncommitted crew.md is invisible to the crew. Examples: [web app](examples/web-app.md),
[game](examples/game.md).

## 1. Launch

1. Pick a short kebab-case `slug`; branch = slug. `DEFAULT=$(git -C $ROOT symbolic-ref --short refs/remotes/origin/HEAD | cut -d/ -f2)` (no remote: the current default branch).
2. Worktree from the fresh default branch:
   `git -C $ROOT fetch -q && git -C $ROOT worktree add -b <slug> $ROOT/../$(basename $ROOT)-<slug> origin/$DEFAULT && git -C $ROOT/../$(basename $ROOT)-<slug> push -q -u origin <slug>`
   (no remote: branch from the local default and skip the push).
   Copy anything the crew must see that is not committed (an owner screenshot, a log) into the worktree and name its path in `ask`.
3. Run the workflow. Try `Workflow({ name: 'crew', args })`. If that name is unknown, or the
   tool refuses a path under `~/.claude`, copy the script into the repo and run it from there:
   `mkdir -p $ROOT/.claude/workflows && cp ~/.claude/workflows/crew.js $ROOT/.claude/workflows/ && echo .claude/workflows/crew.js >> $ROOT/.git/info/exclude`
   then `Workflow({ scriptPath: '$ROOT/.claude/workflows/crew.js', args })`.
   `args = { slug, worktree, branch: slug, ask, depth: 'full'|'quick', implementer }`.
   `ask` = the owner's words **verbatim**, then optionally `(Orchestrator notes: …)` with what
   you already know: file pointers, numbers, constraints, other crews running in parallel and
   which area each owns. `implementer` = crew.md's "Implementer agent", else omit.
4. Several requests at once: one workflow each, separate slugs, and tell each crew which area
   the others own so they don't collide.
5. Tell the owner in a few lines: slug/branch, depth, rough duration.
6. Keep resume notes (run ids, args) in a scratch file: sessions end, runs survive.

## 2. When a run finishes

Read the result: `decisions` (calls made on the owner's behalf), per-slice verdicts,
`branchReview`. The per-agent journal path in the notification has every full report.

- **Everything passed:** verify yourself. Merge the default branch into the slice branch, run
  crew.md's "Verify before merge" commands, open the screenshots the reviewers cite and LOOK.
  Merge `--no-ff`, push, `git worktree remove`. Report honestly per slice: passed / failed and
  why, what is untested.
- **A slice failed** (`stoppedAt`): the result carries `remaining`, the failed slice plus the
  skipped ones. Turn the reviewer's `fixes` into a first slice "Finish slice N: …" and run
  again with `args.slices = [thatFix, ...remaining.slice(1)]`. Research and planning are skipped.
- **Only the branch review failed:** same, with one fix slice made from its `fixes`. Small
  doc-only fixes are quicker with a single implementer agent.
- **Empty implementer report:** it hit its turn limit. Check `git status` in the worktree;
  the reviewer judges the branch, so a passed review still counts.
- **API errors (529/overloaded) or the machine shut down:** re-run with the same `scriptPath`,
  `args` and `resumeFromRunId`; finished agents replay from cache.
- **Merge conflicts with work merged meanwhile:** resolve keeping both sides' intent (version
  numbers: bump past both). For big semantic conflicts hand it to one implementer agent with
  both sides described.

## Rules

- The crew never merges; only you do, after verifying.
- Never work around a permission denial an agent hit. Surface it to the owner.
- Owner preferences in crew.md "Rules" (e.g. silent test runs, no migrations) bind every agent.
