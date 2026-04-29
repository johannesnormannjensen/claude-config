#!/usr/bin/env pwsh

$raw = [Console]::In.ReadToEnd()
$data = $raw | ConvertFrom-Json

# ANSI escape sequences
$ESC    = "`e"
$RESET   = "$ESC[0m"
$BOLD    = "$ESC[1m"
$DIM     = "$ESC[2m"
$CYAN    = "$ESC[36m"
$YELLOW  = "$ESC[33m"
$BLUE    = "$ESC[34m"
$MAGENTA = "$ESC[35m"
$GREEN   = "$ESC[32m"
$RED     = "$ESC[31m"

# Model display name — cyan
$model = if ($data.model.display_name) { $data.model.display_name } else { "Unknown Model" }
$model_colored = "${BOLD}${CYAN}${model}${RESET}"

# Context usage percentage — color scales green → yellow → red
$used_pct = $data.context_window.used_percentage
if ($null -ne $used_pct) {
    $used_pct_int = [int][Math]::Round([double]$used_pct)
    $ctx_color = if ($used_pct_int -ge 80) { $RED } elseif ($used_pct_int -ge 50) { $YELLOW } else { $GREEN }
    $context_colored = "${DIM}Context:${RESET} ${BOLD}${ctx_color}${used_pct_int}%${RESET}"
} else {
    $context_colored = "${DIM}Context: -${RESET}"
}

# Session timer — blue
$duration_ms = if ($data.cost.total_duration_ms) { [long]$data.cost.total_duration_ms } else { 0 }
$duration_s = [int]($duration_ms / 1000)
$session_clock = "{0:D2}:{1:D2}:{2:D2}" -f ([int]($duration_s / 3600)), ([int](($duration_s % 3600) / 60)), ([int]($duration_s % 60))
$clock_colored = "${DIM}${BLUE}${session_clock}${RESET}"

# Git branch — magenta
$current_dir = if ($data.workspace.current_dir) { $data.workspace.current_dir } else { "." }
$git_branch = ""
try {
    $git_branch = (git -C $current_dir --no-optional-locks branch --show-current 2>$null) -join ""
    if ($LASTEXITCODE -ne 0) { $git_branch = "" }
} catch { $git_branch = "" }
$branch_colored = "${MAGENTA}${git_branch}${RESET}"

# Worktree/directory name — green, falls back to basename of cwd
$worktree_name = $data.worktree.name
if (-not $worktree_name) {
    $work_dir = $data.workspace.current_dir
    $worktree_name = if ($work_dir) { Split-Path -Leaf $work_dir } else { Split-Path -Leaf (Get-Location).Path }
}
$worktree_colored = "${GREEN}${worktree_name}${RESET}"

$SEP = "${DIM} | ${RESET}"

# Line 1: model | context | time
[Console]::WriteLine("${model_colored}${SEP}${context_colored}${SEP}${clock_colored}")

# Line 2: branch | directory (branch omitted if not in a git repo)
if ($git_branch) {
    [Console]::WriteLine("${branch_colored}${SEP}${worktree_colored}")
} else {
    [Console]::WriteLine("${worktree_colored}")
}
