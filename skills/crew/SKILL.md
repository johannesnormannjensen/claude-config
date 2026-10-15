---
name: crew
description: Use when the owner types /crew <request>, /crew init, says to start a ticket ("start T12", "start what makes sense"), to continue or resume a crew ("continue", or a slug that already has a worktree), or asks for "the usual research, plan, implement, review flow" on a feature in any git repo. Runs the crew or preview workflow on its own branch and worktree, then the orchestrator verifies and merges.
---

# /crew: research → plan → implement → review

One request becomes one branch in its own git worktree. Researchers (prior art, craft, code
audit) feed a planner that cuts as few vertical slices as the work needs (at most 3). Each slice
gets an implementer, a strict reviewer, hand-offs when the implementer is cut off, and one fix
round. With more than one slice, a final reviewer checks the whole branch. You (the orchestrator)
verify and merge.

| Command | Does |
|---------|------|
| `/crew <request>` | full run (~1 h) |
| `/crew quick: <request>` | audit-only research (~30 min); strip the prefix from `ask` |
| `/crew preview: <request>` | one agent, the smallest change worth showing (~20-30 min) |
| `/crew init` | write `.claude/crew.md` for this repo, nothing else |
| "start T12" | start a ticket from the tracker crew.md names, with its `workflow:` field |
| "continue" | Resume below |

## Which message does what

The Workflow harness shows every crew agent the owner's **latest chat message** as "the user
request" and tells it that message wins over the script's task. A guard line in the prompt does
not beat it. Crews launched in the wrong turn have built the wrong feature. So:

- Launch only in the turn whose owner message is the start and nothing else (`/crew …`,
  "start T12"). Never in a turn that answers a question, says "Yes", or talks about another feature.
- Never ask "should I start X?": a "Yes" would launch in the wrong turn. Say "X is next" and wait.
- `ask` is the owner's request or the ticket's full text from the tracker, copied verbatim, never
  a later chat sentence.
- Ideas and "add a ticket" go to the `crew-ticket` skill, which writes tickets and launches nothing.

## 0. Setup (first run in a repo, or `/crew init`)

Find the repo and its default branch once; every command below uses them:

```sh
ROOT=$(git rev-parse --show-toplevel)
if git -C "$ROOT" remote get-url origin >/dev/null 2>&1; then
  git -C "$ROOT" symbolic-ref -q refs/remotes/origin/HEAD >/dev/null || git -C "$ROOT" remote set-head origin --auto
  DEFAULT=$(git -C "$ROOT" symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||'); BASE=origin/$DEFAULT
else
  DEFAULT=$(git -C "$ROOT" branch --show-current); BASE=$DEFAULT   # no remote: run this from the main checkout on its default branch
fi
```

If `$ROOT/.claude/crew.md` is missing, draft it:
read README, AGENTS.md/CLAUDE.md, the package manifest (package.json, Cargo.toml,
pyproject.toml, go.mod, *.csproj, Gemfile…), Makefile/justfile, CI config and lint/format
config. Fill [the template](crew-template.md); every command must be one you found or ran, not
guessed. "Show it" depends on the kind of project: screenshots for a UI or game, saved sample
output for a CLI or compiler, a benchmark table for performance work, `none` when nothing is
worth looking at, or saved output of a command that changes no shared state (a plan, a dry run,
a diff, a link check) for infrastructure. A section with nothing to run says `none` (e.g.
`test: none` for a repo whose only check is a linter). Never put a command that changes shared
state (deploy, apply, migrate a live database, publish) under Gates or Show it, and write such
commands into Rules as forbidden. Run the gate and test commands once to confirm they work, but
not one that is missing a dry-run flag or that Rules forbid. Show the draft to the owner, then
commit it on `$DEFAULT` and, with a remote, push it: worktrees start from `$BASE`, so a crew.md
that is not on `$BASE` is invisible to the crew, and its agents stop with "crew.md missing". Examples: [web app](examples/web-app.md),
[game](examples/game.md), [compiler](examples/compiler.md).

## 1. Launch

1. **Pick.** A preview only makes sense when crew.md's "Show it" is not `none`; otherwise
   offer `crew:quick`. For a ticket: it qualifies when its questions are answered, it is unblocked ("after
   Tx" merged), has no worktree in `git worktree list`, and is a build. A ticket saying "verify" or
   "no code" is not a build: ask the owner. The workflow comes from its `workflow:` field
   (crew.md "Workflow field"); no field means `crew:full`, or the mapping crew.md gives.
2. **Slots.** At most 2 crews running at once, previews included. With more, timing-sensitive
   checks fail under load and each false failure costs a fix round. Say which wait.
3. **Overlap.** If a running crew owns the same module or files, or the ticket waits on it, hold it
   until that crew merges and say why.
4. **Worktree.** Short kebab-case `slug`; branch = slug (a preview: `preview-<slug>`).
   Worktrees live only under `$ROOT/.claude/worktrees/` (once per repo:
   `grep -qx .claude/worktrees/ $ROOT/.git/info/exclude || echo .claude/worktrees/ >> $ROOT/.git/info/exclude`).
   One at a time (parallel calls race on git's lock):
   - with a remote: `git -C $ROOT fetch -q && git -C $ROOT worktree add -b <slug> $ROOT/.claude/worktrees/<slug> $BASE && git -C $ROOT/.claude/worktrees/<slug> push -q -u origin <slug>`
   - no remote: `git -C $ROOT worktree add -b <slug> $ROOT/.claude/worktrees/<slug> $BASE`

   A crew after an accepted preview branches from `preview-<slug>` instead of `$BASE`, then
   `git worktree remove .claude/worktrees/preview-<slug>`.
   Copy anything the crew must see that is not committed (a screenshot, a log, a failing input) into the worktree and name its path in `ask`.
5. **Run.** Try `Workflow({ name: 'crew', args })` (or `name: 'preview'`). If that name is
   unknown, or the tool refuses a path under `~/.claude`, copy the scripts into the repo and run
   them from there:
   `mkdir -p $ROOT/.claude/workflows && cp ~/.claude/workflows/{crew,preview}.js $ROOT/.claude/workflows/ && printf '%s\n' .claude/workflows/crew.js .claude/workflows/preview.js >> $ROOT/.git/info/exclude`
   then `Workflow({ scriptPath: '$ROOT/.claude/workflows/crew.js', args })`.
   - crew: `args = { slug, worktree, branch: slug, ask, goal, depth: 'full'|'quick', implementer }`, plus `fromPreview: true` when the branch came from a preview.
   - preview: `args = { slug: 'preview-<slug>', worktree, branch: 'preview-<slug>', ask, goal, implementer }`.
   `goal` = one plain line for the progress view ("T12: export to CSV"). `ask` may end with
   `(Orchestrator notes: …)`: file pointers, numbers, constraints, other crews running and which
   area each owns. `implementer` = crew.md's "Implementer agent", else omit.
6. Tell the owner in a few lines: slug/branch, workflow, rough duration.
7. Keep resume notes (run ids, args) in a scratch file: sessions end, runs survive.

## 2. When a run finishes

Read the result: `decisions` (calls made on the owner's behalf), `results` (one per slice; its
`review` is one verdict, or `{ first, final, reviews, continues }` after hand-offs or a fix
round), `branchReview` (null for a one-slice run: not required, its slice review covered the
branch) and `resume` (only when something failed). The per-agent journal path in the
notification has every full report.

- **Preview:** show the note and open each artifact it made (LOOK first). Accepted: start a crew from
  the preview branch (`fromPreview: true`; the ticket's field becomes `crew:quick` or `crew:full`).
  Rejected: `git worktree remove .claude/worktrees/preview-<slug>`.
- **Everything passed** (no `resume`): verify yourself. Merge the default branch into the crew branch, run
  crew.md's "Verify before merge" commands, open what the reviewers showed (crew.md "Show it") and LOOK.
  Check reviewers' claims against the repo before acting on them. Then land it:
  1. Drop the crew's notes on the crew branch, so they never reach `$DEFAULT`:
     `git -C <worktree> rm -r -q --ignore-unmatch .claude/research && git -C <worktree> commit -q -m "chore: drop crew notes for <slug>"` (skip the commit when nothing was removed).
  2. Merge `--no-ff` into `$DEFAULT`. The merge commit message is the conclusion: one line on what
     landed, the planner's `decisions` as bullets, what is untested, and where the full notes live
     (`git show <slug-branch-tip>~1:.claude/research/<slug>-plan.md`, with the hash written out).
  3. Push if there is a remote, `git worktree remove`.
  Report honestly per slice: passed / failed and why, what is untested.
- **A slice or the branch review failed:** run `crew` again with `{ ...originalArgs, ...result.resume }`.
  Research and planning are skipped. For a failed slice, `resume` carries the reviewer's fix list,
  or `reviewFirst: true` when there is none (a cut-off implementer). For a failed branch review,
  it appends one fix slice. Small doc-only fixes are quicker with a single implementer agent.
- **Many cut-off continues** (`continue:` labels): the implementer's turn cap is too low for the
  slices. Give the implementer agent `maxTurns: 150`; keep the planner sizing slices at ~60 tool calls.
- **Merge conflicts with work merged meanwhile:** resolve keeping both sides' intent. Version
  fields: resolve them the way crew.md's Rules describe (e.g. semver from the merged changes);
  if Rules say nothing, ask the owner. For big semantic conflicts hand it to one
  implementer agent with both sides described.

## 3. Resume

Same session, interrupted run (API errors, 529, shutdown): re-run with the same `scriptPath` or
`name`, the ORIGINAL `args` and `resumeFromRunId`; finished agents replay from cache. Without the
original `args` the script crashes.

Later session ("continue", or a slug): only branches in `git worktree list` under
`.claude/worktrees/` count, `preview-*` excluded. A bare directory there is not a crew. Per slug:
- branch merged into the default branch (`git -C $ROOT branch --merged $DEFAULT`) and worktree clean: stale. Do not
  resume; removing the worktree is fine.
- a workflow for that slug is still running: leave it alone.
- otherwise run `crew` again with the original args plus `slices`, `start`, `fixes` and
  `reviewFirst` (set both of the last two). Restart point, in this order:
  1. `.claude/crew-resume/<slug>.json` on the default branch (written on pause: slices, start,
     fixes). Delete it in a commit after launching, so it never runs twice.
  2. the latest workflow record for the slug (`~/.claude/projects/<project>/*/workflows/wf_*.json`):
     its result's `resume`, as is.
  3. the plan file `.claude/research/<slug>-plan.md` on the branch: `start` = the first slice not
     known to have passed, `reviewFirst: true`.
  None of these: ask the owner. Never rebuild slices from a guess at `git log`, and never start a
  fresh crew for a slug that has a worktree.

`reviewFirst` opens the start slice with a review, so finished work is not re-implemented.
Pausing a crew for a later session: write its resume args to `.claude/crew-resume/<slug>.json`
on the default branch and commit (and push, with a remote).

## 4. Measure

`python3 ~/.claude/skills/crew/crew-stats.py` (run from the repo) reads the workflow records and
prints wall time, agent-time per phase, review outcomes, cut-off implementers and stopped runs;
`--csv` for one row per run. Measure before changing models or caps. The records' `tokens` field
leaves out cache reads, so it is not a cost number.

## Rules

- The crew never merges; only you do, after verifying.
- Never work around a permission denial an agent hit. Surface it to the owner.
- Owner preferences in crew.md "Rules" (e.g. silent test runs, no migrations) bind every agent.
