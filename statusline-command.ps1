#!/usr/bin/env pwsh
$jsonText = [Console]::In.ReadToEnd()
$data = $jsonText | ConvertFrom-Json

# ANSI color codes
$ESC = [char]27
$RESET = "$ESC[0m"
$BOLD = "$ESC[1m"
$CYAN = "$ESC[36m"
$YELLOW = "$ESC[33m"
$BLUE = "$ESC[34m"
$MAGENTA = "$ESC[35m"
$GREEN = "$ESC[32m"
$RED = "$ESC[31m"
$DIM = "$ESC[2m"

# Model display name — cyan
$model = if ($data.model.display_name) { $data.model.display_name } else { "Unknown Model" }
$modelColored = "${BOLD}${CYAN}${model}${RESET}"

# Context usage percentage — yellow, turning red when high
$usedPct = $data.context_window.used_percentage
if ($null -ne $usedPct) {
    $usedPctInt = [int][Math]::Round([double]$usedPct)
    if ($usedPctInt -ge 80) {
        $ctxColor = $RED
    } elseif ($usedPctInt -ge 50) {
        $ctxColor = $YELLOW
    } else {
        $ctxColor = $GREEN
    }
    $contextColored = "${DIM}Context:${RESET} ${BOLD}${ctxColor}${usedPctInt}%${RESET}"
} else {
    $contextColored = "${DIM}Context: -${RESET}"
}

# Session timer — blue (elapsed since session start)
$durationMs = if ($data.cost.total_duration_ms) { [long]$data.cost.total_duration_ms } else { [long]0 }
$durationS = [long]($durationMs / 1000)
$hours = [long]($durationS / 3600)
$mins = [long](($durationS % 3600) / 60)
$secs = $durationS % 60
$sessionClock = "{0:D2}:{1:D2}:{2:D2}" -f $hours, $mins, $secs
$clockColored = "${DIM}${BLUE}${sessionClock}${RESET}"

# Session cost (USD) — green
$costUsd = $data.cost.total_cost_usd
if ($null -ne $costUsd) {
    $costFmt = "`$" + ("{0:F2}" -f [double]$costUsd)
    $costColored = "${BOLD}${GREEN}${costFmt}${RESET}"
} else {
    $costColored = "${DIM}`$-${RESET}"
}

# Total tokens used — sum across all assistant turns in the transcript
$transcriptPath = $data.transcript_path
$tokensTotal = [long]0
if ($transcriptPath -and (Test-Path -LiteralPath $transcriptPath)) {
    Get-Content -LiteralPath $transcriptPath | ForEach-Object {
        if (-not $_) { return }
        try {
            $entry = $_ | ConvertFrom-Json -ErrorAction Stop
            $usage = $entry.message.usage
            if ($usage) {
                $inTok = if ($usage.input_tokens) { [long]$usage.input_tokens } else { [long]0 }
                $outTok = if ($usage.output_tokens) { [long]$usage.output_tokens } else { [long]0 }
                $cacheCreate = if ($usage.cache_creation_input_tokens) { [long]$usage.cache_creation_input_tokens } else { [long]0 }
                $cacheRead = if ($usage.cache_read_input_tokens) { [long]$usage.cache_read_input_tokens } else { [long]0 }
                $tokensTotal += $inTok + $outTok + $cacheCreate + $cacheRead
            }
        } catch {}
    }
}

if ($tokensTotal -ge 1000000) {
    $tokensFmt = "{0:F1}M" -f ($tokensTotal / 1000000.0)
} elseif ($tokensTotal -ge 1000) {
    $tokensFmt = "{0:F0}k" -f ($tokensTotal / 1000.0)
} else {
    $tokensFmt = "$tokensTotal"
}
$tokensColored = "${BOLD}${YELLOW}${tokensFmt}${RESET}"

# Git branch (skip optional locks to avoid blocking) — magenta
$workDir = if ($data.workspace.current_dir) { $data.workspace.current_dir } else { "." }
$gitBranch = ""
try {
    $branchOut = & git -C $workDir --no-optional-locks branch --show-current 2>$null
    if ($LASTEXITCODE -eq 0 -and $branchOut) {
        $gitBranch = ($branchOut | Select-Object -First 1).ToString().Trim()
    }
} catch {
    $gitBranch = ""
}
$branchColored = "${MAGENTA}${gitBranch}${RESET}"

# Worktree info — green (fall back to project directory name)
$worktreeName = $data.worktree.name
if (-not $worktreeName) {
    $wd = if ($data.workspace.current_dir) { $data.workspace.current_dir } else { (Get-Location).Path }
    $worktreeName = Split-Path -Leaf $wd
}

# Dim separator
$SEP = "${DIM} | ${RESET}"

# Context field: percentage and token count combined — "Context: <pct> - <tokens>"
$contextBlock = "${contextColored} ${DIM}-${RESET} ${tokensColored}"

# Line 1: <model> | Context: <pct> - <tokens> | <cost> | <timer>
[Console]::Out.WriteLine("${modelColored}${SEP}${contextBlock}${SEP}${costColored}${SEP}${clockColored}")

# Line 2: <branch> | <workspace>  (branch omitted when not in a git repo)
$worktreeColored = "${GREEN}${worktreeName}${RESET}"
if ($gitBranch) {
    [Console]::Out.WriteLine("${branchColored}${SEP}${worktreeColored}")
} else {
    [Console]::Out.WriteLine("${worktreeColored}")
}
