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
  context_colored="${DIM}Context:${RESET} ${BOLD}${ctx_color}${used_pct_int}%%${RESET}"
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

# Build line 1
printf '%b\n' "${model_colored}${SEP}${context_colored}${SEP}${clock_colored}"

# Build line 2
worktree_colored="${GREEN}${worktree_name}${RESET}"
if [ -n "$git_branch" ]; then
  printf '%b\n' "${branch_colored}${SEP}${worktree_colored}"
else
  printf '%b\n' "${worktree_colored}"
fi
