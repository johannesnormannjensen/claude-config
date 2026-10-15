#!/usr/bin/env python3
"""Crew run statistics from Claude Code's workflow records (stdlib only).

Reads ~/.claude/projects/<current git repo>/*/workflows/wf_*.json (one record per workflow run)
and the journal.jsonl beside each run's agents, keeps the crew and preview runs, groups them by
slug and prints wall time, agent-time per phase, review outcomes, empty implementer reports and
stopped runs. Run it from inside the repo.

    crew-stats.py            summary + one line per slug
    crew-stats.py --csv      one CSV row per run on stdout
    crew-stats.py --since 2026-10-11

Wall time (durationMs) is the headline. Phase numbers are agent-time: parallel research
agents overlap, so they can add up to more than the wall time. The workflow `tokens` field
leaves out cache reads, so this script reports no cost.
"""

import argparse
import csv
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

CREW = ("crew", "crew-continue", "crew-resume", "preview")  # older names of the resume script
PHASES = ("Research", "Plan", "Implement", "Review", "Wrap-up")
IMPL_LABEL = re.compile(r"(^|· )((implement|fix|continue):|preview$)")
# Previews are one agent with no review or landing; they get their own summary line.
PREVIEW = "preview"


def project_key(path):
    """Claude Code names a project's folder after its path with every non-alphanumeric made '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def project_dir():
    git = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         capture_output=True, text=True)
    if git.returncode:
        sys.exit("crew-stats: run it from inside the git repo whose crews you want to see")
    repo = os.path.dirname(git.stdout.strip())  # the main checkout, also from inside a worktree
    return os.path.expanduser("~/.claude/projects/" + project_key(repo))


def slug_of(rec):
    """The goal log line 'slug: goal' when the run had one, else the branch in the prompt."""
    logs = rec.get("logs") or []
    for a in rec.get("workflowProgress") or []:
        m = re.search(r"on branch (\S+?)\.", a.get("promptPreview", ""))
        if m:
            return m.group(1)
    if logs and ":" in logs[0]:
        return logs[0].split(":", 1)[0]
    return "?"


def ticket_of(rec):
    for line in rec.get("logs") or []:
        m = re.search(r"(?:\bT|#)(\d+)\b", line)
        if m:
            return int(m.group(1))
    return None


def empty_impl_reports(rec, path):
    """Implement/fix agents that finished with an empty result string.

    The journal keeps the full result; workflowProgress only a preview, used when the journal
    is gone."""
    journal = os.path.join(os.path.dirname(os.path.dirname(path)), "subagents", "workflows",
                           rec["runId"], "journal.jsonl")
    if os.path.exists(journal):
        labels, empty, total = {}, 0, 0
        with open(journal) as f:
            for line in f:
                e = json.loads(line)
                if e.get("type") == "started":
                    labels[e["key"]] = e.get("label", "")
                elif e.get("type") == "result" and IMPL_LABEL.search(labels.get(e["key"], "")):
                    total += 1
                    empty += not str(e.get("result") or "").strip()
        return empty, total
    agents = [a for a in rec.get("workflowProgress") or []
              if a.get("type") == "workflow_agent" and IMPL_LABEL.search(a.get("label", ""))
              and a.get("state") == "done"]
    return sum(not a.get("resultPreview", "").strip() for a in agents), len(agents)


def reviews(result):
    """(first-try passes, fix rounds, passed after fix) over the slice reviews."""
    first = fixed = fixed_ok = 0
    for r in (result or {}).get("results") or []:
        rv = r.get("review") if isinstance(r, dict) else None
        if not isinstance(rv, dict):
            continue
        if "final" in rv:
            fixed += 1
            fixed_ok += bool((rv.get("final") or {}).get("pass"))
        elif rv.get("pass"):
            first += 1
        else:
            fixed += 1  # rejected with no re-review on record
    return first, fixed, fixed_ok


def load(since):
    runs = []
    for path in glob.glob(os.path.join(glob.escape(project_dir()), "*", "workflows", "wf_*.json")):
        with open(path) as f:
            rec = json.load(f)
        if rec.get("workflowName") not in CREW:
            continue
        start = datetime.fromtimestamp((rec.get("startTime") or 0) / 1000, timezone.utc)
        if since and start.date() < since:
            continue
        result = rec.get("result") if isinstance(rec.get("result"), dict) else {}
        phase_ms, models = Counter(), Counter()
        for a in rec.get("workflowProgress") or []:
            if a.get("type") == "workflow_agent":
                phase_ms[a.get("phaseTitle", "?")] += a.get("durationMs") or 0
                models[(a.get("phaseTitle", "?"), a.get("model", "?"))] += 1
        first, fixed, fixed_ok = reviews(result)
        empty, impls = empty_impl_reports(rec, path)
        branch = result.get("branchReview")
        runs.append({
            "run": rec["runId"], "kind": rec["workflowName"], "slug": slug_of(rec),
            "ticket": ticket_of(rec), "start": start, "status": rec.get("status"),
            "wall_min": (rec.get("durationMs") or 0) / 60000,
            "phase_min": {p: phase_ms[p] / 60000 for p in phase_ms}, "models": models,
            "first_pass": first, "fix_rounds": fixed, "fix_pass": fixed_ok,
            "empty_impl": empty, "impls": impls,
            "stopped_at": result.get("stoppedAt"),
            "branch_pass": None if not isinstance(branch, dict) else bool(branch.get("pass")),
        })
    return sorted(runs, key=lambda r: r["start"])



def median(xs):
    xs = sorted(xs)
    if not xs:
        return 0
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2


def summary(runs):
    previews = [r for r in runs if r["kind"] == PREVIEW]
    runs = [r for r in runs if r["kind"] != PREVIEW]
    if previews:
        print(f"previews: {len(previews)}, median {median([r['wall_min'] for r in previews]):.0f} min, "
              f"empty notes {sum(r['empty_impl'] for r in previews)}")
    status = Counter(r["status"] for r in runs)
    print(f"crew runs: {len(runs)} ({', '.join(f'{n} {s}' for s, n in status.most_common())}), "
          f"{len({r['slug'] for r in runs})} slugs, "
          f"{runs[0]['start']:%Y-%m-%d} .. {runs[-1]['start']:%Y-%m-%d}" if runs else "crew runs: 0")
    if not runs:
        return
    done = [r["wall_min"] for r in runs if r["status"] == "completed"]
    print(f"wall time (completed): median {median(done):.0f} min, longest {max(done, default=0) / 60:.1f} h")
    phase = Counter()
    for r in runs:
        phase.update(r["phase_min"])
    total = sum(phase.values()) or 1
    print("agent-time: " + ", ".join(f"{p} {phase[p] / 60:.1f} h ({phase[p] / total:.0%})"
                                     for p in PHASES + tuple(sorted(set(phase) - set(PHASES)))
                                     if phase[p]))
    models = Counter()
    for r in runs:
        models.update(r["models"])
    by_model = defaultdict(list)
    for (p, m), n in sorted(models.items()):
        by_model[m.replace("claude-", "")].append(f"{p} {n}")
    print("agents by model: " + "; ".join(f"{m}: {', '.join(v)}" for m, v in by_model.items()))
    first = sum(r["first_pass"] for r in runs)
    fixed = sum(r["fix_rounds"] for r in runs)
    fixed_ok = sum(r["fix_pass"] for r in runs)
    print(f"slice reviews: {first + fixed}, passed first try {first} ({first / ((first + fixed) or 1):.0%}), "
          f"fix round {fixed}: {fixed_ok} passed, {fixed - fixed_ok} still failed")
    empty = sum(r["empty_impl"] for r in runs)
    impls = sum(r["impls"] for r in runs)
    print(f"empty implement/fix/continue reports: {empty} of {impls} ({empty / (impls or 1):.0%})")
    stopped = [r for r in runs if r["stopped_at"]]
    print(f"stopped at a failed slice: {len(stopped)} runs; branch review failed: "
          f"{sum(r['branch_pass'] is False for r in runs)}")
    print()
    print(f"{'slug':<22}{'T':>4} {'runs':>4} {'wall':>6} {'impl':>6} {'review':>7}  {'reviews':<10}{'empty':>6}")
    groups = defaultdict(list)
    for r in runs:
        groups[r["slug"]].append(r)
    for slug, rs in groups.items():
        f = sum(r["first_pass"] for r in rs)
        x = sum(r["fix_rounds"] for r in rs)
        ok = sum(r["fix_pass"] for r in rs)
        t = next((r["ticket"] for r in rs if r["ticket"]), None)
        state = "" if rs[-1]["status"] == "completed" else f" [{rs[-1]['status']}]"
        print(f"{slug[:21]:<22}{t or '':>4} {len(rs):>4} {sum(r['wall_min'] for r in rs):>5.0f}m "
              f"{sum(r['phase_min'].get('Implement', 0) for r in rs):>5.0f}m "
              f"{sum(r['phase_min'].get('Review', 0) for r in rs):>6.0f}m  "
              f"{f}+{x}({ok}ok){'':<3}{sum(r['empty_impl'] for r in rs):>5}{state}")


def write_csv(runs):
    w = csv.writer(sys.stdout)
    w.writerow(["run", "kind", "slug", "ticket", "start", "status", "wall_min", *[p.lower() + "_min" for p in PHASES],
                "first_pass", "fix_rounds", "fix_pass", "empty_impl", "impls", "stopped_at", "branch_pass"])
    for r in runs:
        w.writerow([r["run"], r["kind"], r["slug"], r["ticket"] or "", f"{r['start']:%Y-%m-%dT%H:%M}", r["status"],
                    f"{r['wall_min']:.1f}", *[f"{r['phase_min'].get(p, 0):.1f}" for p in PHASES],
                    r["first_pass"], r["fix_rounds"], r["fix_pass"], r["empty_impl"], r["impls"],
                    r["stopped_at"] or "", "" if r["branch_pass"] is None else int(r["branch_pass"])])


def self_check():
    rv = {"results": [{"review": {"pass": True}}, {"review": {"first": {"pass": False}, "final": {"pass": True}}},
                      {"review": {"first": {"pass": False}, "final": {"pass": False}}}]}
    assert reviews(rv) == (1, 2, 1)
    assert project_key("/home/a/repo/.claude/worktrees/x_y") == "-home-a-repo--claude-worktrees-x-y"
    assert median([3, 1, 2]) == 2 and median([1, 2]) == 1.5
    print("self-check ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--csv", action="store_true", help="one CSV row per run on stdout")
    ap.add_argument("--since", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), help="YYYY-MM-DD")
    ap.add_argument("--self-check", action="store_true", help="run the built-in asserts")
    a = ap.parse_args()
    if a.self_check:
        self_check()
    elif a.csv:
        write_csv(load(a.since))
    else:
        summary(load(a.since))
