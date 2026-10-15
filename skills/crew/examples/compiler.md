# Crew config — Quill

## Project
Quill, a compiler for a small typed scripting language, written in Rust, emitting WebAssembly.
Output must be deterministic: the same source always gives byte-identical `.wasm`.

## Rules
- Every new diagnostic has an error code (`Q0123`) and a test in `tests/ui/`.
- No `unsafe` outside `src/runtime/`.
- Language changes need a section in `docs/spec.md` before the code.
- Never run `cargo publish`. Conventional Commits; versions follow semver from the merged
  changes (a new diagnostic is minor, a changed one is major).

## Gates
- gate: `cargo fmt --check && cargo clippy --all-targets -- -D warnings`
- test: `cargo test -q`
- evidence: `cargo insta test` (snapshot tests of diagnostics and IR) when output changes;
  `cargo bench -- --save-baseline crew` when the optimizer changes; `cargo fuzz run parse -- -max_total_time=120`
  when the parser changes.
- evidence record: omit

## Show it
- a new or changed diagnostic: compile the sample in `tests/ui/` and save stderr to a file.
- a codegen change: `quill build --emit wat <sample>` before and after, as a diff.
- an optimizer change: the benchmark comparison table against the default branch.
- internal refactors: none.

## Implement
- Skills to invoke: superpowers:test-driven-development
- Implementer agent: omit
- Kept-in-sync docs: `docs/spec.md` for language rules, `docs/diagnostics.md` for error codes.

## References
- rustc's diagnostic guidelines, Elm's compiler error messages, the WebAssembly spec.

## Tickets
- Tracker: omit

## Verify before merge
- `cargo test -q && cargo insta test --check && cargo build --release`
