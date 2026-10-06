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

### Crew workflow (`skills/crew/`, `workflows/crew.js`)

`/crew <request>` turns one feature request into a finished branch, in any git repo: a game, a web
app, a CLI, a library. It runs on its own git worktree, so you keep working (or run several
crews at once) while it goes:

1. **Research:** three agents in parallel. *Prior art* (how well-regarded projects solve it),
   *craft* (typical numbers, failure modes, how to measure quality) and an *audit* of your code
   (file:line pointers to what causes the problem today).
2. **Plan:** at most 3 vertical slices, each with objective acceptance checks. Open design
   choices get a sensible default, listed as `decisions` for you to overrule.
3. **Implement + review:** per slice, an implementer, then a strict reviewer who re-runs your
   gates and looks at the screenshots, then one fix round if needed. A final reviewer checks the
   whole branch.
4. **You merge.** Claude verifies the branch itself, then merges it `--no-ff`. The crew never merges.

Setup per repo is one file, `.claude/crew.md`: what the project is, its rules, and its gate,
test and evidence commands. Run `/crew init` and Claude drafts it from your README, manifests
and CI config, runs the commands to check them, and asks you to confirm. Template:
[`skills/crew/crew-template.md`](skills/crew/crew-template.md). Examples:
[web app](skills/crew/examples/web-app.md), [game](skills/crew/examples/game.md).

| Command | What it does |
|---------|--------------|
| `/crew init` | write and commit `.claude/crew.md` for this repo |
| `/crew <request>` | full run, about 1 hour |
| `/crew quick: <request>` | skip outside research (code audit only), about 30 minutes |

Needs Claude Code with the Workflow tool, and git. Agents commit after every step (and push if
the branch has an upstream), so a shutdown loses little: ask Claude to resume the run. If a
slice fails review twice, the crew stops and hands back the remaining slices. Claude can
continue from there without redoing research and planning.

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
7. Prints plugin installation commands to run manually inside Claude Code

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
├── workflows/
│   └── crew.js                # Crew workflow: research → plan → implement → review
└── skills/
    ├── crew/
    │   ├── SKILL.md           # /crew command: setup, launch, verify, merge, recover
    │   ├── crew-template.md   # Per-repo .claude/crew.md template
    │   └── examples/          # crew.md for a web app and a game
    └── omarchy/
        └── SKILL.md           # Omarchy desktop environment skill
```

## Customization

- **Add a new skill:** Create `skills/<name>/SKILL.md` and re-run `install.sh`
- **Add a workflow:** Drop `workflows/<name>.js` in and re-run `install.sh`
- **Add MCP servers:** Edit `.mcp.json` and re-run `install.sh` to merge
- **Change settings:** Edit `settings.json` and re-run `install.sh` to merge
- **Modify the status line:** Edit `statusline-command.sh` (it's symlinked, so changes take effect immediately)
