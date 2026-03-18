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
    ln -sfn "$skill_dir" "$CLAUDE_DIR/skills/$skill_name"
    echo "  Linked skill: $skill_name"
  done
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
