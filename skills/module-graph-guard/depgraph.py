#!/usr/bin/env python3
"""depgraph: who names whom between the modules of a repo, and the rules that must keep holding.

An edge a -> b means a non-test file in module a names something module b declares (a path
it points at, or a symbol b declares). Text views are for agents, the html page is for people.
Per-repo choices (what a module is, which languages, layer rules, hubs, page groups) live in
depgraph.toml at the repo root, or --config. Python 3.11+, stdlib only.
"""

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
import tomllib
import webbrowser
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- globs


@lru_cache(maxsize=None)
def glob_re(pattern):
    """`**` any depth (also none), `*` one segment's chars, `{module}` one named segment."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("/**", i) and i + 3 == len(pattern):
            out, i = out + "(?:/.*)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        elif pattern[i] == "{":
            j = pattern.index("}", i)
            out, i = out + f"(?P<{pattern[i + 1:j]}>[^/]+?)", j + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def matches(path, patterns):
    return any(glob_re(p).match(path) for p in patterns)


# ---------------------------------------------------------------- comment / string stripping


def stripper(line=("//",), block=(("/*", "*/"),), strings=(r'"(?:\\.|[^"\\])*"',), keep_strings=False):
    """Drop comments (keeping their newlines) and, unless keep_strings, string contents too.
    Strings are always matched so a `//` inside one is not a comment."""
    alts = [re.escape(t) + r"[^\n]*" for t in line]
    alts += [re.escape(a) + r"[\s\S]*?(?:" + re.escape(b) + r"|\Z)" for a, b in block]
    n_comments = len(alts)
    alts += strings
    rx = re.compile("|".join(f"({a})" for a in alts))

    def sub(m):
        if m.lastindex <= n_comments or not keep_strings:
            return "\n" * m.group(0).count("\n")
        return m.group(0)

    return lambda text: rx.sub(sub, text)


DQ, SQ = r'"(?:\\[\s\S]|[^"\\])*"', r"'(?:\\[\s\S]|[^'\\])*'"
# r#"..."# raw strings; a char literal is one char or one escape, so a lifetime `'a` is code.
RUST_RAW, RUST_CHAR = r'r(?P<hashes>#*)"[\s\S]*?"(?P=hashes)', r"'(?:\\[^']{1,10}|[^'\\])'"
TRIPLE = (r'"""[\s\S]*?"""', r"'''[\s\S]*?'''")
BACKTICK = r"`[^`]*`"
C_STYLE = stripper(strings=(DQ, SQ, BACKTICK), keep_strings=True)

# ---------------------------------------------------------------- rust (use-trees under crate::)


def is_ident_start(c):
    return c.isascii() and (c.isalpha() or c == "_")


def is_ident(c):
    return is_ident_start(c) or (c.isascii() and c.isdigit())


def rust_crate_refs(src):
    """Every `crate::` path as module -> names: `crate::a::B`, `crate::a::{B, c::D}`,
    `crate::{a::B, c}`, `crate::a::*`; `Type::method` names `Type`.
    ponytail: `use crate::a;` then `a::B` records only `a`; follow aliases if agents need them."""
    out = {}
    i = 0
    while True:
        i = src.find("crate::", i)
        if i < 0:
            return out
        if i > 0 and is_ident(src[i - 1]):
            i += 1
            continue
        i = _path_tree(src, i + 7, [], out)


def _path_tree(src, i, prefix, out):
    n = len(src)
    if i < n and src[i] == "{":
        i += 1
        while True:
            while i < n and not is_ident_start(src[i]) and src[i] not in "}*":
                i += 1
            if i >= n or src[i] == "}":
                return i + 1
            i = _path_tree(src, i, prefix, out)
            while i < n and src[i] == " ":
                i += 1
            if src.startswith("as ", i):  # `as alias` names nothing new
                i += 3
                while i < n and (src[i] == " " or is_ident(src[i])):
                    i += 1
    segs = list(prefix)
    if i < n and src[i] == "*":
        _record(segs + ["*"], out)
        return i + 1
    while i < n and is_ident_start(src[i]):
        start = i
        while i < n and is_ident(src[i]):
            i += 1
        segs.append(src[start:i])
        if src.startswith("::", i):
            i += 2
            if i < n and src[i] in "{*":
                return _path_tree(src, i, segs, out)
        else:
            break
    _record(segs, out)
    return i


def _record(segs, out):
    if not segs or segs[0] in ("self", "super", "crate"):
        return
    rest = [s for s in segs[1:] if s != "self"]
    for t, s in enumerate(rest):
        if s[:1].isupper():
            rest = rest[: t + 1]
            break
    out.setdefault(segs[0], set()).add("::".join(rest) if rest else segs[0])


CFG_TEST = "#[cfg(test)]"


def _skip_balanced(s, i, open_c, close_c):
    depth = 0
    while i < len(s):
        if s[i] == open_c:
            depth += 1
        elif s[i] == close_c:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def rust_test_files(rel, code):
    """Files named by `#[cfg(test)] mod name;` (a declaration, not an inline `mod name {`)."""
    base = rel[: -len("/mod.rs")] if rel.endswith("/mod.rs") else rel[: -len(".rs")]
    out = []
    for m in re.finditer(re.escape(CFG_TEST), code):
        if m.start() and is_ident(code[m.start() - 1]):
            continue
        i = m.end()
        while True:  # more attributes
            while i < len(code) and code[i].isspace():
                i += 1
            if code.startswith("#", i):
                i = _skip_balanced(code, i, "[", "]")
            else:
                break
        d = re.compile(r"(?:pub\s*(?:\([^)]*\))?\s*)?mod\s+([A-Za-z_]\w*)\s*;").match(code, i)
        if d:
            out += [f"{base}/{d.group(1)}.rs", f"{base}/{d.group(1)}/mod.rs"]
    return out


def rust_without_cfg_test(code):
    """Drop items marked `#[cfg(test)]` (through the matching `}` of a body, or a bodiless `;`)."""
    out, i = [], 0
    while True:
        j = code.find(CFG_TEST, i)
        if j < 0:
            out.append(code[i:])
            return "".join(out)
        if j and is_ident(code[j - 1]):
            out.append(code[i : j + 1])
            i = j + 1
            continue
        out.append(code[i:j])
        k, depth, opened = j + len(CFG_TEST), 0, False
        while k < len(code):
            c = code[k]
            if c == "{":
                depth, opened = depth + 1, True
            elif c == "}":
                depth -= 1
                if opened and depth == 0:
                    k += 1
                    break
            elif c == ";" and depth == 0:
                k += 1
                break
            k += 1
        i = k


def crate_dir(rel):
    parts = rel.split("/")
    return "/".join(parts[: parts.index("src")]) if "src" in parts else ""


def rust_refs(rel, code, ctx):
    code = rust_without_cfg_test(code)
    cd = crate_dir(rel)
    return [("symbol", f"{cd}|crate::{m}", n) for m, names in rust_crate_refs(code).items() for n in names]


def rust_declares(rel, text, ctx):
    parts = rel.split("/")
    if "src" not in parts or parts.index("src") + 1 >= len(parts):
        return []
    seg = parts[parts.index("src") + 1]
    return [f"{crate_dir(rel)}|crate::{seg.removesuffix('.rs')}"]


# ---------------------------------------------------------------- other languages


def python_refs(rel, code, ctx):
    out = []
    for m in re.finditer(r"^[ \t]*from[ \t]+(\.*)([\w.]*)[ \t]+import[ \t]+(\([^)]*\)|[^\n]+)", code, re.M):
        dots, mod = m.group(1), m.group(2)
        names = [n.split()[0] for n in m.group(3).strip("()").replace("\n", " ").split(",") if n.strip()]
        for n in names:
            if dots:
                up = "/".join([".."] * (len(dots) - 1)) or "."
                out.append(("path", posixpath.join(up, *mod.split(".")) if mod else up, n))
            else:
                out.append(("symbol", f"{mod}.{n}", n))
    for m in re.finditer(r"^[ \t]*import[ \t]+([^\n]+)", code, re.M):
        for part in m.group(1).split(","):
            if part.strip():
                out.append(("symbol", part.split()[0], None))
    return out


def python_declares(rel, text, ctx):
    parts = rel.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    top = len(parts) - 1  # walk up while the parent dir is a package
    while top > 0 and "/".join(parts[:top]) + "/__init__.py" in ctx.sources:
        top -= 1
    return [".".join(parts[top:])] if parts[top:] else []


def js_clause_names(clause):
    clause = clause.strip()
    if not clause or clause == "type":
        return [None]
    names = []
    if "{" in clause:
        inner = clause[clause.index("{") + 1 : clause.rindex("}")]
        names += [p.split()[-1] if p.split()[0] == "type" else p.split()[0] for p in inner.split(",") if p.strip()]
        clause = clause[: clause.index("{")] + clause[clause.rindex("}") + 1 :]
    for p in clause.split(","):
        p = p.strip()
        if p.startswith("*"):
            names.append("*")
        elif p and p != "type":
            names.append("default")
    return names or [None]


def js_refs(rel, code, ctx):
    found = []
    for m in re.finditer(r"\b(?:import|export)\s+(?:type\s+)?([\w\s{},*$]*?)\s*\bfrom\s*['\"]([^'\"]+)['\"]", code):
        found += [(m.group(2), n) for n in js_clause_names(m.group(1))]
    for m in re.finditer(r"\bimport\s*['\"]([^'\"]+)['\"]|\b(?:require|import)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", code):
        found.append((m.group(1) or m.group(2), None))
    return [("path" if t.startswith(".") else "symbol", t, n) for t, n in found]


def nearest(ctx, rel, name):
    d = posixpath.dirname(rel)
    while True:
        p = posixpath.join(d, name) if d else name
        if p in ctx.sources:
            return p
        if not d:
            return None
        d = posixpath.dirname(d)


def js_declares(rel, text, ctx):
    pkg = nearest(ctx, rel, "package.json")
    if not pkg:
        return []
    try:
        name = json.loads(ctx.sources[pkg]).get("name")
    except (ValueError, AttributeError):
        return []
    return [name] if name else []


def java_refs(rel, code, ctx):
    out = []
    for m in re.finditer(r"^[ \t]*import[ \t]+(?:static[ \t]+)?([\w.]+?)(\.\*)?[ \t]*(?:as[ \t]+\w+)?[ \t]*;?[ \t]*$", code, re.M):
        out.append(("symbol", m.group(1), "*" if m.group(2) else None))
    return out


def java_declares(rel, text, ctx):
    m = re.search(r"^[ \t]*package[ \t]+([\w.]+)", text, re.M)
    return [m.group(1)] if m else []


def go_refs(rel, code, ctx):
    specs = re.findall(r'\bimport\s+(?:(\w+|\.|_)\s+)?"([^"]+)"', code)
    for block in re.findall(r"\bimport\s*\(([^)]*)\)", code):
        specs += re.findall(r'(?:(\w+|\.|_)\s+)?"([^"]+)"', block)
    out = []
    for alias, path in specs:
        local = alias or path.rsplit("/", 1)[-1]
        used = sorted(set(re.findall(rf"\b{re.escape(local)}\.([A-Z]\w*)", code))) if local.isidentifier() else []
        out += [("symbol", path, f"{local}.{n}") for n in used] or [("symbol", path, local)]
    return out


def go_declares(rel, text, ctx):
    gomod = nearest(ctx, rel, "go.mod")
    m = gomod and re.search(r"^module\s+(\S+)", ctx.sources[gomod], re.M)
    if not m:
        return []
    sub = posixpath.relpath(posixpath.dirname(rel) or ".", posixpath.dirname(gomod) or ".")
    return [m.group(1) if sub == "." else f"{m.group(1)}/{sub}"]


def csharp_refs(rel, code, ctx):
    rx = r"^[ \t]*(?:global[ \t]+)?using[ \t]+(?:static[ \t]+)?(?:\w+[ \t]*=[ \t]*)?([\w.]+)[ \t]*;"
    return [("symbol", m.group(1), None) for m in re.finditer(rx, code, re.M)]


def csharp_declares(rel, text, ctx):
    return re.findall(r"\bnamespace\s+([\w.]+)", text)


def terraform_refs(rel, code, ctx):
    out = []
    for m in re.finditer(r'\bmodule\s+"([^"]+)"\s*\{', code):
        s = re.compile(r'\bsource\s*=\s*"([^"]+)"').search(code, m.end())
        if s and s.group(1).startswith("."):
            out.append(("path", s.group(1), m.group(1)))
    for line in code.splitlines():
        for t in re.findall(r"\$\{path\.module\}/([^\"\s$]+)", line):
            out.append(("path", t, (re.match(r"\s*(\w+)", line) or [None, None])[1]))
    return out


def k8s_refs(rel, code, ctx):
    out = [("path", t, "chart") for t in re.findall(r"file://([^\"'\s]+)", code)]
    if posixpath.basename(rel).startswith("kustomization"):
        out += [("path", t, "kustomize") for t in re.findall(r"^\s*-\s*(\.\.?/[^\s#]+)", code, re.M)]
    return out


def no_declares(rel, text, ctx):
    return []


# name -> (file globs, stripper, refs, declares, separator used when a name is derived)
PRESETS = {
    "rust": (["**/*.rs"], stripper(strings=(RUST_RAW, DQ, RUST_CHAR)), rust_refs, rust_declares, "::"),
    "python": (["**/*.py"], stripper(line=("#",), block=(), strings=TRIPLE + (DQ, SQ)), python_refs, python_declares, "."),
    "js": (["**/*.js", "**/*.jsx", "**/*.mjs", "**/*.cjs", "**/*.ts", "**/*.tsx", "**/*.mts", "**/*.cts"], C_STYLE, js_refs, js_declares, "/"),
    "java": (["**/*.java", "**/*.kt", "**/*.kts"], stripper(strings=(r'"""[\s\S]*?"""', DQ, SQ), keep_strings=True), java_refs, java_declares, "."),
    "go": (["**/*.go"], C_STYLE, go_refs, go_declares, "."),
    "csharp": (["**/*.cs"], stripper(strings=(r'@"(?:""|[^"])*"', DQ, SQ), keep_strings=True), csharp_refs, csharp_declares, "."),
    "terraform": (["**/*.tf"], stripper(line=("#", "//"), strings=(DQ,), keep_strings=True), terraform_refs, no_declares, "/"),
    "k8s": (["**/Chart.yaml", "**/kustomization.yaml", "**/kustomization.yml"], stripper(line=("#",), block=(), strings=(), keep_strings=True), k8s_refs, no_declares, "/"),
}
MANIFESTS = {"package.json", "go.mod", "__init__.py"}
DEFAULT_TESTS = [
    "**/test/**", "**/tests/**", "**/__tests__/**", "**/testdata/**", "**/*_test.*", "**/*_tests.rs",
    "**/test_*.py", "**/*.test.*", "**/*.spec.*", "**/*Test.java", "**/*Tests.java", "**/*Test.kt", "**/*Tests.cs",
]

# ---------------------------------------------------------------- config


class Config:
    def __init__(self, data, root):
        self.root = root
        self.title = data.get("title", "Modules")
        self.command = data.get("command", "depgraph")
        self.presets = data.get("presets", [])
        unknown = [p for p in self.presets if p not in PRESETS]
        if unknown:
            sys.exit(f"depgraph: unknown preset(s) {unknown}; have {sorted(PRESETS)}")
        self.extract = data.get("extract", [])
        self.declare = data.get("declare", [])
        for e in self.extract:
            e["_rx"] = re.compile(e["regex"], re.M)
        for d in self.declare:
            d["_rx"] = re.compile(d["regex"], re.M)
        handled = [g for p in self.presets for g in PRESETS[p][0]] + [g for e in self.extract for g in as_list(e["files"])]
        self.include = data.get("include", handled)
        self.exclude = data.get("exclude", []) + ["**/.*/**", "**/node_modules/**"]
        self.tests = data.get("tests", DEFAULT_TESTS)
        self.modules = data.get("modules") or [{"match": "{module}/**"}]
        self.hubs = data.get("hubs", [])
        self.baseline = data.get("baseline", "depgraph-baseline.txt")
        self.html = data.get("html", ".depgraph/modules.html")
        self.legend = data.get("legend")
        self.rules = data.get("rules", {})
        page = data.get("page", {})
        self.groups = page.get("groups", [])
        self.shared = page.get("shared", [])

    @lru_cache(maxsize=None)
    def module_of(self, path):
        for m in self.modules:
            hit = glob_re(m["match"]).match(path)
            if hit:
                # `src/{module}/**` on `src/billing.rs` names `billing`, same as the dir would
                parts = {k: posixpath.splitext(v)[0] if path.endswith("/" + v) or path == v else v
                         for k, v in hit.groupdict().items()}
                return m.get("name", "{module}").format(**parts)
        return None

    def path(self, p):
        return Path(p) if os.path.isabs(p) else self.root / p


def as_list(x):
    return [x] if isinstance(x, str) else list(x)


def load_config(args):
    root = Path(args.root).resolve()
    path = Path(args.config) if args.config else root / "depgraph.toml"
    if not path.is_file():
        sys.exit(f"depgraph: no config at {path} (write depgraph.toml or pass --config)")
    with open(path, "rb") as f:
        cfg = Config(tomllib.load(f), root)
    if args.html:
        cfg.html = os.path.abspath(args.html)
    return cfg


# ---------------------------------------------------------------- sources and the graph


def worktree_sources(cfg):
    root = cfg.root
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, check=True).stdout.decode()
        names = [n for n in out.split("\0") if n]
    except (OSError, subprocess.CalledProcessError):
        names = [str(p.relative_to(root)).replace(os.sep, "/") for p in root.rglob("*") if p.is_file()]
    names = wanted(cfg, names)
    sources = {}
    for n in names:
        try:
            sources[n] = (root / n).read_text(errors="replace")
        except (FileNotFoundError, IsADirectoryError):
            pass  # deleted but still in the index
    return sources


def wanted(cfg, names):
    return sorted(n for n in names if not matches(n, cfg.exclude)
                  and (matches(n, cfg.include) or posixpath.basename(n) in MANIFESTS))


def git(cfg, *args, data=None):
    r = subprocess.run(["git", "-C", str(cfg.root), *args], input=data, capture_output=True)
    if r.returncode:
        sys.exit(f"depgraph: git {' '.join(args)}: {r.stderr.decode().strip()}")
    return r.stdout


def git_sources(cfg, rev):
    """The wanted files at a revision, read in one `git cat-file --batch` (no checkout)."""
    names = wanted(cfg, [n for n in git(cfg, "ls-tree", "-r", "-z", "--name-only", "--full-tree", rev).decode().split("\0") if n])
    out = git(cfg, "cat-file", "--batch", data="".join(f"{rev}:{n}\n" for n in names).encode())
    sources, pos = {}, 0
    for n in names:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].split()
        if header[-1] == b"missing":  # a submodule entry
            pos = nl + 1
            continue
        size = int(header[2])
        sources[n] = out[nl + 1 : nl + 1 + size].decode(errors="replace")
        pos = nl + 1 + size + 1
    return sources


class Ctx:
    def __init__(self, sources):
        self.sources = sources


def tokens(symbol):
    return tuple(t for t in re.split(r"::|[./|]", symbol) if t)


class Graph:
    def __init__(self, modules, edges):
        self.modules = modules  # sorted list
        self.edges = edges  # {(from, to): {file: set(names)}}

    def files(self, a, b):
        return sorted(self.edges.get((a, b), {}))

    def out_edges(self, m):
        return sorted((k for k in self.edges if k[0] == m), key=lambda k: (-len(self.edges[k]), k[1]))

    def in_edges(self, m):
        return sorted((k for k in self.edges if k[1] == m), key=lambda k: (-len(self.edges[k]), k[0]))

    def indegree(self, m):
        return sum(1 for k in self.edges if k[1] == m)

    def both_ways(self):
        return sorted((a, b) for a, b in self.edges if a < b and (b, a) in self.edges)


def file_presets(cfg, rel):
    return [PRESETS[p] for p in cfg.presets if matches(rel, PRESETS[p][0])]


def build(cfg, sources):
    ctx = Ctx(sources)
    files = [f for f in sources if matches(f, cfg.include) and cfg.module_of(f)]
    module_set = {cfg.module_of(f) for f in files}
    stripped = {}
    index = {}  # symbol tokens -> {module}
    test_files = {f for f in files if matches(f, cfg.tests)}
    for f in files:
        text = sources[f]
        for globs, strip, _refs, declares, _sep in file_presets(cfg, f):
            code = stripped.setdefault((f, strip), strip(text))
            if declares is rust_declares:
                test_files.update(rust_test_files(f, code))
            for sym in declares(f, text, ctx):
                index.setdefault(tokens(sym), set()).add(cfg.module_of(f))
        for d in cfg.declare:
            if matches(f, as_list(d["files"])):
                for m in d["_rx"].finditer(text):
                    index.setdefault(tokens(m.group("symbol")), set()).add(cfg.module_of(f))
    edges = {}
    for f in files:
        if f in test_files:
            continue  # tests may name anything; the graph and the rules are production code
        src = cfg.module_of(f)
        refs = []
        for globs, strip, refs_fn, _d, sep in file_presets(cfg, f):
            refs += [(k, t, n, sep) for k, t, n in refs_fn(f, stripped[(f, strip)], ctx)]
        for e in cfg.extract:
            if matches(f, as_list(e["files"])):
                for m in e["_rx"].finditer(sources[f]):
                    g = m.groupdict()
                    kind = "path" if g.get("path") else "symbol"
                    target = g.get("path") or g.get("symbol")
                    if kind == "path" and e.get("relative_to") == "root":
                        target = "/" + target
                    refs.append((kind, target, g.get("name"), e.get("sep", "/")))
        for kind, target, name, sep in refs:
            for to, nm in resolve(cfg, index, f, kind, target, name, sep):
                if to != src and to in module_set:
                    edges.setdefault((src, to), {}).setdefault(f, set()).add(nm)
    return Graph(sorted(module_set), edges)


def resolve(cfg, index, rel, kind, target, name, sep):
    if not target:
        return []
    if kind == "path":
        p = posixpath.normpath(target[1:] if target.startswith("/") else posixpath.join(posixpath.dirname(rel), target))
        if p == ".." or p.startswith("../"):
            return []
        m = cfg.module_of(p) or cfg.module_of(p + "/")
        return [(m, name or posixpath.basename(p))] if m else []
    toks = tokens(target)
    for i in range(len(toks), 0, -1):
        hits = index.get(toks[:i])
        if hits:
            if cfg.module_of(rel) in hits:
                return []  # the file's own module declares it
            rest = list(toks[i:])
            for t, s in enumerate(rest):
                if s[:1].isupper():
                    rest = rest[: t + 1]
                    break
            # ponytail: a symbol two modules declare edges to both; scope the index if that misleads
            return [(m, name or (sep.join(rest) if rest else toks[-1])) for m in sorted(hits)]
    return []


# ---------------------------------------------------------------- views


def capped(items, n, sep):
    items = list(items)
    text = sep.join(items[:n])
    return text + (f" +{len(items) - n}" if len(items) > n else "")


def brief(g, a, b):
    names = sorted({n for ns in g.edges[(a, b)].values() for n in ns})
    return f"{capped(names, 6, ', ')}  in {capped(g.files(a, b), 3, ' ')}"


def read_baseline(cfg):
    p = cfg.path(cfg.baseline)
    return p.read_text() if p.is_file() else ""


def parse_line(t):
    body, _, note = t.partition("#")
    if "<->" not in body:
        return None
    a, b = (x.strip() for x in body.split("<->", 1))
    return (min(a, b), max(a, b)), note.strip()


def pair_status(baseline, a, b):
    for line in baseline.splitlines():
        t = line.strip()
        if t.startswith("#"):
            continue
        parsed = parse_line(t)
        if parsed and parsed[0] == (min(a, b), max(a, b)):
            return parsed[1] if parsed[1].startswith("allowed:") else "to clear"
    return "not in baseline: --check fails"


def summary(cfg, g, baseline):
    both = g.both_ways()
    legend = cfg.legend or (f"edge a -> b: a non-test file in module a names something module b declares; "
                            f"`{cfg.command} a b` lists each file and the names it uses; `{cfg.command} --check` holds the rules")
    lines = [legend, f"{len(g.modules)} modules, {len(g.edges)} edges, {len(both)} both ways", "hubs (named by the most modules)"]
    hubs = sorted(((m, g.indegree(m)) for m in g.modules), key=lambda x: (-x[1], x[0]))
    lines += [f"  {n:3}  {m}" for m, n in hubs[:12]]
    lines.append("both ways")
    lines += [f"  {a} <-> {b}  ({pair_status(baseline, a, b)})" for a, b in both] or ["  none"]
    return "\n".join(lines) + "\n"


def neighborhood(g, name):
    outs, ins = g.out_edges(name), g.in_edges(name)
    lines = [f"{name}    out {len(outs)}    in {len(ins)}    (each row: module, names used, files)", "out"]
    lines += [f"  {b:<16} {brief(g, a, b)}" for a, b in outs] or ["  none"]
    lines.append("in")
    lines += [f"  {a:<16} {brief(g, a, b)}" for a, b in ins] or ["  none"]
    return "\n".join(lines) + "\n"


def pair(g, baseline, a, b):
    ab, ba = (a, b) in g.edges, (b, a) in g.edges
    status = (f"both ways ({pair_status(baseline, a, b)})" if ab and ba else f"one way: {a} -> {b}" if ab
              else f"one way: {b} -> {a}" if ba else "no edge")
    lines = [f"{a} <-> {b}: {status}"]
    for x, y in ((a, b), (b, a)):
        if (x, y) in g.edges:
            files = g.edges[(x, y)]
            lines.append(f"{x} -> {y}  {len(files)} file(s)")
            lines += [f"  {f}  {', '.join(sorted(files[f]))}" for f in sorted(files)]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- check


def ratchet(cfg, baseline, g):
    """Two-way pairs only go down: a pair missing from the baseline fails, a listed pair that went
    away is reported for deletion, `# allowed: why` pairs stay for good."""
    both = set(g.both_ways())
    problems, gone, known, clear, allowed = [], [], set(), 0, 0
    for n, line in enumerate(baseline.splitlines(), 1):
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        parsed = parse_line(t)
        if not parsed:
            problems.append(f"{cfg.baseline}:{n}: not 'a <-> b': {t}")
            continue
        p, note = parsed
        if note.startswith("allowed:"):
            allowed += 1
        elif p in both:
            clear += 1
        else:
            gone.append(line)
            continue
        known.add(p)
    for a, b in sorted(both - known):
        problems.append(f"new two-way pair {a} <-> {b} ({cfg.command} {a} {b}): "
                        f"{a} -> {b} uses {brief(g, a, b)}; {b} -> {a} uses {brief(g, b, a)}")
    return problems, gone, clear, allowed


def rule_problems(cfg, g, sources):
    problems = []
    for rule in cfg.rules.get("layer", []):
        for (a, b), files in g.edges.items():
            if a == rule["module"] and b not in rule["may_use"]:
                problems.append(f"{min(files)}: {a} names {b} ({a} may name only {', '.join(rule['may_use']) or 'nothing'})")
    for rule in cfg.rules.get("pattern", []):
        rx = re.compile(rule["forbid"])
        allow = as_list(rule.get("allow_under", []))
        for f, text in sources.items():
            if not matches(f, as_list(rule.get("files", "**"))) or any(f.startswith(p) for p in allow):
                continue
            strip = next((p[1] for p in file_presets(cfg, f)), None)
            code = strip(text) if strip else text
            for n, line in enumerate(code.splitlines(), 1):
                if rx.search(line):
                    problems.append(f"{f}:{n}: {rule['message']}")
    return sorted(problems)


def check(cfg, g, sources, update):
    bp = cfg.path(cfg.baseline)
    if not bp.is_file():
        print(f"depgraph: {cfg.baseline}: missing (create it once with --init)", file=sys.stderr)
        return 2
    baseline = bp.read_text()
    problems = rule_problems(cfg, g, sources)
    rp, gone, clear, allowed = ratchet(cfg, baseline, g)
    problems += rp
    if gone and update:
        bp.write_text("".join(l + "\n" for l in baseline.splitlines() if l not in gone))
        for l in gone:
            print(f"dropped from {cfg.baseline}: {l}")
    elif gone:
        problems += [f"{cfg.baseline}: '{l}' no longer names both ways; delete the line (or {cfg.command} --check --update)" for l in gone]
    if problems:
        print("\n".join(problems))
        return 1
    print(f"ok graph: {clear} to clear, {allowed} allowed")
    return 0


def init_baseline(cfg, g):
    bp = cfg.path(cfg.baseline)
    if bp.exists():
        sys.exit(f"depgraph: {cfg.baseline} exists; the ratchet only shrinks (--check --update)")
    head = ("# Module pairs that name each other both ways (depgraph --check ratchet).\n"
            "# A pair not listed fails the check; a listed pair that stopped is deleted (--check --update),\n"
            "# so the list only shrinks. Never add a line to get green: break the cycle.\n"
            "# `# allowed: why` keeps a pair for good.\n")
    bp.write_text(head + "".join(f"{a} <-> {b}\n" for a, b in g.both_ways()))
    print(f"wrote {cfg.baseline}: {len(g.both_ways())} pair(s)")


# ---------------------------------------------------------------- diff


def diff(cfg, rng):
    if "..." in rng:
        a, b = rng.split("...", 1)
        before = a and b and git(cfg, "merge-base", a, b).decode().strip()
    elif ".." in rng:
        a, b = rng.split("..", 1)
        before = a
    else:
        sys.exit(f"depgraph: --diff wants <a>..<b> or <a>...<b>, got '{rng}'")
    if not before or not b:
        sys.exit(f"depgraph: --diff wants both sides, got '{rng}'")
    old, new = build(cfg, git_sources(cfg, before)), build(cfg, git_sources(cfg, b))
    lines = []
    for a2, b2 in sorted(new.edges):
        if (a2, b2) not in old.edges:
            hub = "  (into a hub: the report says why)" if b2 in cfg.hubs else ""
            lines.append(f"+ {a2} -> {b2}  {brief(new, a2, b2)}{hub}")
    lines += [f"- {a2} -> {b2}" for a2, b2 in sorted(set(old.edges) - set(new.edges))]
    if not lines:
        return "edges: no change\n"
    added = sum(1 for l in lines if l.startswith("+"))
    return f"edges: +{added} -{len(lines) - added}\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------- html


def page(cfg, g, focus):
    data = {
        "title": cfg.title,
        "focus": focus or "",
        "modules": [{"name": m, "in": g.indegree(m), "out": sum(1 for k in g.edges if k[0] == m)} for m in g.modules],
        "edges": [{"from": a, "to": b, "files": g.files(a, b)} for a, b in sorted(g.edges)],
        "both": g.both_ways(),
        "groups": cfg.groups,
        "shared": cfg.shared,
    }
    blob = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    return (HERE / "page.html").read_text().replace("/*DATA*/null", blob, 1)


def write_page(cfg, g, focus, no_open):
    path = cfg.path(cfg.html)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page(cfg, g, focus))
    print(f"html {cfg.html}")
    # Only a person at a terminal gets a window; agents and pipes never do.
    if not no_open and sys.stdout.isatty() and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or sys.platform == "darwin"):
        webbrowser.open(path.resolve().as_uri())


# ---------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="depgraph",
        description="Who names whom between a repo's modules. No args: summary + html page. "
                    "One module: its in/out edges. Two modules: the pair, file by file.",
        epilog="Edges skip test files and comments. The page is for people, the text is for agents.")
    ap.add_argument("modules", nargs="*", help="none (summary), <module>, or <a> <b>")
    ap.add_argument("--check", action="store_true", help="layer and pattern rules plus the two-way ratchet; exit 1 on a break")
    ap.add_argument("--update", action="store_true", help="with --check: delete baseline lines that stopped (never adds)")
    ap.add_argument("--init", action="store_true", help="write the baseline with every current two-way pair (only if missing)")
    ap.add_argument("--diff", metavar="A..B", help="edges a git range adds and removes (a...b: since the merge base)")
    ap.add_argument("--no-open", action="store_true", help="never open a browser (it opens only when stdout is a terminal)")
    ap.add_argument("--config", help="config file (default <root>/depgraph.toml)")
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--html", help="where to write the page (overrides config)")
    args = ap.parse_args(argv)
    cfg = load_config(args)
    if args.diff:
        sys.stdout.write(diff(cfg, args.diff))
        return 0
    sources = worktree_sources(cfg)
    g = build(cfg, sources)
    if args.init:
        init_baseline(cfg, g)
        return 0
    if args.check:
        return check(cfg, g, sources, args.update)
    for m in args.modules:
        if m not in g.modules:
            print(f"depgraph: no module '{m}'", file=sys.stderr)
            return 2
    if len(args.modules) == 2:
        sys.stdout.write(pair(g, read_baseline(cfg), *args.modules))
        return 0
    if len(args.modules) > 2:
        ap.error("one module, two modules, --check [--update], --init or --diff <a>..<b>")
    focus = args.modules[0] if args.modules else None
    sys.stdout.write(neighborhood(g, focus) if focus else summary(cfg, g, read_baseline(cfg)))
    write_page(cfg, g, focus, args.no_open)
    return 0


if __name__ == "__main__":
    sys.exit(main())
