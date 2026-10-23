#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

mkdir -p "$CLAUDE_DIR"
mkdir -p "$CLAUDE_DIR/skills"

echo "Installing Claude Code config from $SCRIPT_DIR"

# Status line script
ln -sf "$SCRIPT_DIR/statusline-command.sh" "$CLAUDE_DIR/statusline-command.sh"
echo "  Linked statusline-command.sh"

# Settings — merge into existing settings.json if present
if [ -f "$CLAUDE_DIR/settings.json" ]; then
  # Merge: repo settings take precedence, but preserve existing keys
  tmp=$(jq -s '.[0] * .[1]' "$CLAUDE_DIR/settings.json" "$SCRIPT_DIR/settings.json")
  echo "$tmp" > "$CLAUDE_DIR/settings.json"
  echo "  Merged settings.json (preserved existing keys)"
else
  cp "$SCRIPT_DIR/settings.json" "$CLAUDE_DIR/settings.json"
  echo "  Copied settings.json"
fi

# MCP servers — merge into existing .mcp.json if present
if [ -f "$SCRIPT_DIR/.mcp.json" ]; then
  if [ -f "$CLAUDE_DIR/.mcp.json" ]; then
    tmp=$(jq -s '.[0] * .[1]' "$CLAUDE_DIR/.mcp.json" "$SCRIPT_DIR/.mcp.json")
    echo "$tmp" > "$CLAUDE_DIR/.mcp.json"
    echo "  Merged .mcp.json (preserved existing servers)"
  else
    cp "$SCRIPT_DIR/.mcp.json" "$CLAUDE_DIR/.mcp.json"
    echo "  Copied .mcp.json"
  fi
fi

# Skills — symlink each skill directory
if [ -d "$SCRIPT_DIR/skills" ]; then
  for skill_dir in "$SCRIPT_DIR/skills"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    target="$CLAUDE_DIR/skills/$skill_name"
    # A real directory there would swallow the link (ln puts it inside); leave it to the user.
    if [ -d "$target" ] && [ ! -L "$target" ]; then
      echo "  Skipped skill: $skill_name ($target exists and is not a link; move it away and re-run)"
      continue
    fi
    ln -sfn "${skill_dir%/}" "$target"
    echo "  Linked skill: $skill_name"
  done
fi

# Workflows — symlink each workflow script
if [ -d "$SCRIPT_DIR/workflows" ]; then
  mkdir -p "$CLAUDE_DIR/workflows"
  for wf in "$SCRIPT_DIR/workflows"/*.js; do
    [ -f "$wf" ] || continue
    ln -sf "$wf" "$CLAUDE_DIR/workflows/$(basename "$wf")"
    echo "  Linked workflow: $(basename "$wf")"
  done
fi

# herdr — symlink the config (keybinds mirror the Omarchy tmux setup)
HERDR_DIR="$HOME/.config/herdr"
mkdir -p "$HERDR_DIR"
if [ -f "$HERDR_DIR/config.toml" ] && [ ! -L "$HERDR_DIR/config.toml" ]; then
  echo "  Skipped herdr config ($HERDR_DIR/config.toml exists; move it away and re-run)"
else
  ln -sf "$SCRIPT_DIR/herdr/config.toml" "$HERDR_DIR/config.toml"
  echo "  Linked herdr/config.toml"
fi

# Mods — this repo is a folder marketplace, so installed mods are read from it (edit + /reload-plugins)
if command -v claude >/dev/null 2>&1; then
  # Re-runs find both already there; that is not a failure.
  claude plugin marketplace add "$SCRIPT_DIR" >/dev/null 2>&1 && echo "  Added marketplace: claude-config" || true
  claude plugin install crew-board@claude-config >/dev/null 2>&1 && echo "  Installed mod: crew-board" || echo "  crew-board not installed (already installed?)"
else
  echo "  Skipped mods (claude not on PATH): claude plugin marketplace add $SCRIPT_DIR && claude plugin install crew-board@claude-config"
fi

# Plugins — install from official marketplace
PLUGINS=(
  "superpowers"
  "code-simplifier"
  "context7"
  "csharp-lsp"
  "frontend-design"
  "typescript-lsp"
)

echo ""
echo "Plugins to install (run these manually in Claude Code):"
for plugin in "${PLUGINS[@]}"; do
  echo "  /plugin install $plugin"
done

echo ""
echo "Done! Restart Claude Code to apply changes."
echo "Then run the /plugin install commands above to install plugins."
