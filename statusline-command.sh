#!/usr/bin/env bash
input=$(cat)
# ANSI color codes
RESET="\033[0m"
BOLD="\033[1m"
# Foreground colors
CYAN="\033[36m"
YELLOW="\033[33m"
BLUE="\033[34m"
MAGENTA="\033[35m"
GREEN="\033[32m"
RED="\033[31m"
DIM="\033[2m"
# Model display name — cyan
model=$(echo "$input" | jq -r '.model.display_name // "Unknown Model"')
model_colored="${BOLD}${CYAN}${model}${RESET}"
# Context usage percentage — yellow, turning red when high
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
if [ -n "$used_pct" ]; then
  used_pct_int=$(printf "%.0f" "$used_pct")
  if [ "$used_pct_int" -ge 80 ]; then
    ctx_color="${RED}"
  elif [ "$used_pct_int" -ge 50 ]; then
    ctx_color="${YELLOW}"
  else
    ctx_color="${GREEN}"
  fi
  context_colored="${DIM}Context:${RESET} ${BOLD}${ctx_color}${used_pct_int}%${RESET}"
else
  context_colored="${DIM}Context: -${RESET}"
fi
# Session timer — blue (elapsed since session start)
duration_ms=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')
duration_s=$(( duration_ms / 1000 ))
hours=$(( duration_s / 3600 ))
mins=$(( (duration_s % 3600) / 60 ))
secs=$(( duration_s % 60 ))
session_clock=$(printf "%02d:%02d:%02d" "$hours" "$mins" "$secs")
clock_colored="${DIM}${BLUE}${session_clock}${RESET}"
# Session cost (USD) — green
cost_usd=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')
if [ -n "$cost_usd" ]; then
  cost_fmt=$(awk -v c="$cost_usd" 'BEGIN{printf "$%.2f", c}')
  cost_colored="${BOLD}${GREEN}${cost_fmt}${RESET}"
else
  cost_colored="${DIM}\$-${RESET}"
fi
# Total tokens used — sum across all assistant turns in the transcript
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')
tokens_total=0
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
  tokens_total=$(jq -r 'try (.message.usage | (.input_tokens // 0) + (.output_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)) // empty' "$transcript_path" 2>/dev/null \
    | awk '{s+=$1} END{print s+0}')
fi
if [ "$tokens_total" -ge 1000000 ]; then
  tokens_fmt=$(awk -v t="$tokens_total" 'BEGIN{printf "%.1fM", t/1000000}')
elif [ "$tokens_total" -ge 1000 ]; then
  tokens_fmt=$(awk -v t="$tokens_total" 'BEGIN{printf "%.0fk", t/1000}')
else
  tokens_fmt="$tokens_total"
fi
tokens_colored="${BOLD}${YELLOW}${tokens_fmt}${RESET}"
# Git branch (skip optional locks to avoid blocking) — magenta
git_branch=$(git -C "$(echo "$input" | jq -r '.workspace.current_dir // "."')" \
  --no-optional-locks branch --show-current 2>/dev/null || echo "")
branch_colored="${MAGENTA}${git_branch}${RESET}"
# Worktree info — green (fall back to project directory name)
worktree_name=$(echo "$input" | jq -r '.worktree.name // empty')
if [ -z "$worktree_name" ]; then
  work_dir=$(echo "$input" | jq -r '.workspace.current_dir // empty')
  worktree_name=$(basename "${work_dir:-$(pwd)}")
fi
# Dim separator
SEP="${DIM} | ${RESET}"
# Context field: percentage and token count combined — "Context: <pct> - <tokens>"
context_block="${context_colored} ${DIM}-${RESET} ${tokens_colored}"
# Build line 1: <model> | Context: <pct> - <tokens> | <cost> | <timer>
printf '%b\n' "${model_colored}${SEP}${context_block}${SEP}${cost_colored}${SEP}${clock_colored}"
# Build line 2: <branch> | <workspace>  (branch omitted when not in a git repo)
worktree_colored="${GREEN}${worktree_name}${RESET}"
if [ -n "$git_branch" ]; then
  printf '%b\n' "${branch_colored}${SEP}${worktree_colored}"
else
  printf '%b\n' "${worktree_colored}"
fi
