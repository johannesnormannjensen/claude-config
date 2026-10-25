---
name: module-graph-guard
description: Use when setting up a dependency, coupling or architecture guard for a repo, finding cycles or modules that depend on each other both ways, answering "who depends on what", or stopping agents from breaking layer boundaries.
---

# Module graph guard

`depgraph.py` (Python 3.11+, stdlib only, `page.html` beside it) maps which module names which, in any language: text views for agents, an offline html page for people, `--check` as the gate. Flags: `python3 depgraph.py --help`.

## Adopt it in a repo

1. Copy `depgraph.py` and `page.html` into the repo (e.g. `tools/depgraph/`).
2. Pick the module unit with the owner (`src/<name>`, `packages/*`, top-level dirs, `modules/*` plus `envs/*`). Too fine is noise, too coarse hides cycles.
3. Write `depgraph.toml` at the root from the nearest file in `configs/`. In module patterns `{module}` binds one path segment; first match wins.
4. Run the summary and open a few pairs; fix the config until the edges match the code.
5. `--init` writes the baseline with every current two-way pair. Mark intended ones `# allowed: why`; the rest is debt.
6. Seed `[[rules.layer]]` and `[[rules.pattern]]` from the repo's architecture docs; confirm each with the owner.
7. Wire `--check` into the existing gate (pre-commit, CI, landing script) and `--diff main...HEAD` into code review.
8. Tell agents in CLAUDE.md or AGENTS.md: `depgraph <module>` before reaching into one, `depgraph a b` before touching a pair, `--check` before done, never add a baseline line.

## Output contract (agents parse these)

- Summary: legend; `N modules, E edges, P both ways`; `hubs (...)` rows `  <count>  <module>`; `both ways` rows `  a <-> b  (to clear | allowed: why | not in baseline: --check fails)`; `html <path>`.
- Module: `m    out N    in M ...`, then `out`/`in` rows `  <other>  <names +k>  in <files +k>`.
- Pair: `a <-> b: both ways (...) | one way: a -> b | no edge`, then `a -> b  N file(s)` and `  <file>  <names>`.
- Check: `ok graph: N to clear, M allowed` (exit 0) or one problem per line (exit 1), each naming a file or a pair.
- Diff: `edges: +A -R` (or `no change`), `+ a -> b  <names>  in <files>` (hub edges marked), `- a -> b`.

A browser opens only when stdout is a terminal.

## Extend it

- A language: a `PRESETS` entry (globs, stripper, `refs` giving `(kind, target, name)` where kind is `path` or `symbol`, `declares` giving a file's symbols) plus a fixture test.
- One-off formats (shell, Dockerfile, YAML): an `[[extract]]` regex with groups `path` or `symbol` and optional `name`; `[[declare]]` adds symbols.

## Common mistakes

- Adding a baseline line to get green. The baseline only shrinks; break the cycle instead.
- Counting tests. Check the `tests` globs; the default drops any `test/` dir, even a real env of that name.
- Scanning vendored, generated or build output. Exclude it (gitignored files are skipped already).
- One git call per file in `--diff`. Each side is one `git cat-file --batch`.
- A CDN in the page. It must open offline.
