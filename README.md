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
5. Symlinks all skill directories into `~/.claude/skills/`
6. Prints plugin installation commands to run manually inside Claude Code

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
└── skills/
    └── omarchy/
        └── SKILL.md           # Omarchy desktop environment skill
```

## Customization

- **Add a new skill:** Create `skills/<name>/SKILL.md` and re-run `install.sh`
- **Add MCP servers:** Edit `.mcp.json` and re-run `install.sh` to merge
- **Change settings:** Edit `settings.json` and re-run `install.sh` to merge
- **Modify the status line:** Edit `statusline-command.sh` (it's symlinked, so changes take effect immediately)
