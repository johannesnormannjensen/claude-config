# claude-config

Personal configuration repository for [Claude Code](https://docs.anthropic.com/en/docs/claude-code), Anthropic's CLI for Claude. Provides a reproducible setup with custom status line, MCP servers, plugins, and skills — all installable via a single script.

## What's Included

### Status Line (`statusline-command.sh`)

A two-line status bar displayed during Claude Code sessions:

```
claude-opus-4-6 | Context: 23% | 5m 32s
main | my-project
```

- **Model name** in cyan
- **Context usage** color-coded: green (<50%), yellow (50–79%), red (≥80%)
- **Session timer** in blue
- **Git branch** in magenta
- **Project directory** in green

### MCP Servers (`.mcp.json`)

- **Sequential Thinking** — structured reasoning via `@modelcontextprotocol/server-sequential-thinking`

### Plugins (`settings.json`)

Six plugins are enabled:

| Plugin | Purpose |
|--------|---------|
| `superpowers` | Enhanced workflows (TDD, planning, brainstorming, debugging) |
| `code-simplifier` | Code quality and simplification reviews |
| `context7` | Up-to-date library documentation lookup |
| `csharp-lsp` | C# language server support |
| `frontend-design` | Production-grade frontend interface generation |
| `typescript-lsp` | TypeScript language server support |

### Skills (`skills/`)

- **Omarchy** — comprehensive knowledge of the [Omarchy](https://omarchy.com) Linux desktop environment (Arch Linux + Hyprland), including safe configuration patterns, command discovery, and troubleshooting.

### Crew workflow (`skills/crew/`, `workflows/crew.js`, `workflows/preview.js`)

`/crew <request>` turns one feature request into a finished branch, in any git repo: a game, a web
app, a CLI, a library. It runs on its own git worktree, so you keep working (or run several
crews at once) while it goes:

1. **Research:** three agents in parallel. *Prior art* (how well-regarded projects solve it),
   *craft* (typical numbers, failure modes, how to measure quality) and an *audit* of your code
   (file:line pointers to what causes the problem today).
2. **Plan:** as few vertical slices as the work needs (at most 3), each with objective acceptance checks. Open design
   choices get a sensible default, listed as `decisions` for you to overrule.
3. **Implement + review:** per slice, an implementer, then a strict reviewer who re-runs your
   gates and looks at what the change shows (a screenshot, sample output), then one fix round if needed. An implementer that runs
   out of turns hands off to a fresh one that starts from the uncommitted diff (at most twice). With more than one slice, a
   final reviewer checks the whole branch.
4. **You merge.** Claude verifies the branch itself, then merges it `--no-ff`. The crew never merges.
   The crew's notes (`.claude/research/`) stay on the branch; the merge commit message carries
   the conclusion: what landed, the decisions made for you, what is untested.

Setup per repo is one file, `.claude/crew.md`: what the project is, its rules, and its gate,
test and evidence commands. Run `/crew init` and Claude drafts it from your README, manifests
and CI config, runs the commands to check them, and asks you to confirm. Template:
[`skills/crew/crew-template.md`](skills/crew/crew-template.md). Examples:
[web app](skills/crew/examples/web-app.md), [game](skills/crew/examples/game.md),
[compiler](skills/crew/examples/compiler.md). Its "Show it" section says what a person looks at
to judge a change: screenshots for a website or game, saved output for a compiler or CLI, or none.

| Command | What it does |
|---------|--------------|
| `/crew init` | write and commit `.claude/crew.md` for this repo |
| `/crew <request>` | full run, about 1 hour |
| `/crew quick: <request>` | skip outside research (code audit only), about 30 minutes |
| `/crew preview: <request>` | one agent builds the smallest change worth showing (a screenshot, sample output), so you can judge it first |
| "start T12" | start a ticket; its `workflow:` field (preview, fast, crew:quick, crew:full) picks the run |
| "continue" | resume stopped crews found in `git worktree list` |

Needs Claude Code with the Workflow tool, and git. Agents commit after every step (and push if
the branch has an upstream), so a shutdown loses little: ask Claude to resume the run. If a
slice fails review twice, the crew stops and returns `resume` args. Claude resumes from there
without redoing research and planning: from the reviewer's fix list, or with a review first when
there is none, so finished work isn't rebuilt.
Run at most two crews at once. Start a crew in a message that says only that: the Workflow tool
shows every agent your latest chat message, so a crew launched while you talk about something
else can build the wrong thing. `skills/crew/crew-stats.py` prints run times, review outcomes
and cut-off implementers from the workflow records.

The planner runs on Fable; a Sonnet wrap-up agent ends a passed run with a landing note (version
bump, what to show, changelog and "To test" lines) that Claude applies when it merges. Small,
clear tickets take the **fast lane** (`workflow: fast`): one implementer, no planner or reviewer,
merged by hand, two tries and then parked for you. crew.md's optional "Fast lane and test
batches" section sets a "To test" list of landed changes you still have to check; past its
play-check limit, "start what makes sense" starts nothing that lands, and a test batch runs alone.

### Crew board mod (`mods/crew-board/`)

A Claude Code mod for the crew workflow. `/crew-board` opens a pane with the running worktrees
(slots used), the "To test" count, open tickets, the version (Cargo.toml or package.json) and
the last release commit, and **where the time goes**: tool time by kind (tests, build + lint,
git, reading, editing, thinking), whole-run wall clock per agent or workflow, the slowest single
calls and time spent waiting on you. It refuses a crew launch in a turn whose latest owner
message is not a start (background-task notices never count), and past the slot limit.
Options (`/config`): tracker path, "To test" heading, slot limit, play-check limit, start
words, a guarded agent type, the release-commit pattern and extra `label=regex` shell kinds.
`install.sh` installs it from this folder; elsewhere:

```
/plugin install crew-board --marketplace johannesnormannjensen/claude-config
```

### herdr (`herdr/config.toml`)

Config for the [herdr](https://github.com/herdrdev/herdr) terminal multiplexer, with keybinds that mirror
the Omarchy tmux setup (workspace = tmux session, tab = window, pane = pane). Prefix is `Ctrl+Space`.

| Keys | Action |
|------|--------|
| `prefix h` / `prefix v`, `Alt+Shift+Enter` | split horizontal / vertical |
| `prefix x`, `Alt+Esc` | close pane |
| `prefix z` / `prefix ;` | zoom / last pane |
| `Ctrl+Alt+arrows` | focus pane |
| `Ctrl+Alt+Shift+arrows` | resize pane |
| `prefix c` / `prefix r` / `prefix k` | new / rename / close tab |
| `prefix 1..9`, `Alt+1..9` | switch tab |
| `prefix p`/`n`, `Alt+Left`/`Right` | previous / next tab |
| `Alt+Shift+Left`/`Right` | move tab |
| `prefix C` / `prefix R` / `prefix K` | new / rename / close workspace |
| `prefix P`/`N`, `Alt+Up`/`Down` | previous / next workspace |
| `prefix O` | rename pane |
| `prefix [` | copy mode |
| `prefix q` / `prefix ?` / `prefix d` | reload config / help / detach |

## Installation

**Prerequisite:** [jq](https://jqlang.github.io/jq/) must be installed.

```bash
git clone <repo-url> ~/projects/claude-config
cd ~/projects/claude-config
./install.sh
```

The install script:

1. Creates `~/.claude/` and `~/.claude/skills/` if needed
2. Symlinks `statusline-command.sh` into `~/.claude/`
3. Merges `settings.json` into your existing Claude Code settings (preserves your existing keys)
4. Merges `.mcp.json` into your existing MCP configuration
5. Symlinks all skill directories into `~/.claude/skills/` (skips any that already exist as a real directory)
6. Symlinks the workflow scripts into `~/.claude/workflows/`
7. Symlinks `herdr/config.toml` into `~/.config/herdr/` (skips an existing real file)
8. Adds this folder as a plugin marketplace and installs the `crew-board` mod from it
9. Prints plugin installation commands to run manually inside Claude Code

After running the script, install each listed plugin inside a Claude Code session:

```
/install-plugin <plugin-name>
```

## File Structure

```
.
├── install.sh                 # Installation script
├── settings.json              # Claude Code settings (plugins, status line)
├── .mcp.json                  # MCP server configuration
├── statusline-command.sh      # Custom status line script
├── herdr/
│   └── config.toml            # herdr keybinds and UI (mirrors Omarchy tmux)
├── .claude-plugin/
│   └── marketplace.json       # Lists the mods under mods/
├── mods/
│   └── crew-board/            # /crew-board pane + crew launch guard
├── workflows/
│   ├── crew.js                # Crew workflow: research → plan → implement → review (and resume)
│   └── preview.js             # One agent, one artifact to judge before building
└── skills/
    ├── crew-ticket/
    │   └── SKILL.md           # /crew-ticket: idea → questions → ticket a crew can run
    ├── crew/
    │   ├── SKILL.md           # /crew command: setup, launch, verify, merge, recover
    │   ├── crew-template.md   # Per-repo .claude/crew.md template
    │   ├── crew-stats.py      # Crew run statistics from the workflow records
    │   └── examples/          # crew.md for a web app, a game and a compiler
    └── omarchy/
        └── SKILL.md           # Omarchy desktop environment skill
```

## Customization

- **Add a new skill:** Create `skills/<name>/SKILL.md` and re-run `install.sh`
- **Add a workflow:** Drop `workflows/<name>.js` in and re-run `install.sh`
- **Add MCP servers:** Edit `.mcp.json` and re-run `install.sh` to merge
- **Change settings:** Edit `settings.json` and re-run `install.sh` to merge
- **Modify the status line:** Edit `statusline-command.sh` (it's symlinked, so changes take effect immediately)
