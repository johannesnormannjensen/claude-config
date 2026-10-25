"""Fixture repos in a temp dir, one per preset, plus the ratchet, the pair view and a git diff.
Run: python3 -m unittest test_depgraph.py"""

import contextlib
import io
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import depgraph


def repo(files, config):
    d = Path(tempfile.mkdtemp())
    for rel, text in {**files, "depgraph.toml": config}.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(textwrap.dedent(text))
    return d


def run(d, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = depgraph.main(["--root", str(d), "--no-open", *args])
    return code, out.getvalue()


def graph(d):
    cfg = depgraph.load_config(depgraph_args(d))
    return depgraph.build(cfg, depgraph.worktree_sources(cfg))


def depgraph_args(d):
    class A:
        root, config, html = str(d), None, None
    return A


def names(g, a, b):
    return sorted({n for ns in g.edges[(a, b)].values() for n in ns})


RUST_CFG = 'presets = ["rust"]\nmodules = [{ match = "src/{module}.rs" }, { match = "src/{module}/**" }]\ntests = []\n'


class Presets(unittest.TestCase):
    def test_rust_use_trees_comments_and_tests(self):
        d = repo({
            "src/api.rs": """\
                use crate::{billing::{Invoice, events::Paid}, storage as s};
                use crate::audit::*;
                // use crate::search::Index;
                fn f<'a>(x: &'a str) { let _ = "crate::search::Index"; crate::billing::Ledger::new(); }
                fn g() { crate::metrics::count(); }
                #[cfg(test)]
                mod tests { use crate::fixtures::Seed; }
                #[cfg(test)]
                mod api_tests;
                """,
            "src/api/api_tests.rs": "use crate::fixtures::More;\n",
            "src/billing/mod.rs": "pub struct Invoice; pub struct Ledger;\n",
            "src/billing/events.rs": "use crate::api::Handle;\n",
            "src/storage.rs": "", "src/audit.rs": "", "src/search.rs": "", "src/fixtures.rs": "", "src/metrics.rs": "",
        }, RUST_CFG)
        g = graph(d)
        self.assertEqual(names(g, "api", "billing"), ["Invoice", "Ledger", "events::Paid"])
        self.assertEqual(names(g, "api", "storage"), ["storage"])
        self.assertEqual(names(g, "api", "audit"), ["*"])
        self.assertIn(("api", "metrics"), g.edges, "a lifetime must not swallow the code after it")
        self.assertNotIn(("api", "search"), g.edges, "comments and strings are not edges")
        self.assertNotIn(("api", "fixtures"), g.edges, "cfg(test) code is not an edge")
        self.assertEqual(g.both_ways(), [("api", "billing")])

    def test_python_absolute_and_relative(self):
        d = repo({
            "shop/__init__.py": "", "shop/billing/__init__.py": "",
            "shop/billing/invoice.py": "from shop.storage.blob import Blob, put\nfrom ..search import index\n",
            "shop/storage/__init__.py": "", "shop/storage/blob.py": "import shop.audit.log as log\n# import shop.search\n",
            "shop/search.py": "", "shop/audit/__init__.py": "", "shop/audit/log.py": "",
            "shop/billing/test_invoice.py": "import shop.audit\n",
        }, 'presets = ["python"]\nmodules = [{ match = "shop/{module}/**" }, { match = "shop/{module}.py" }]\n')
        g = graph(d)
        self.assertEqual(names(g, "billing", "storage"), ["Blob", "put"])
        self.assertEqual(names(g, "billing", "search"), ["index"])
        self.assertEqual(names(g, "storage", "audit"), ["log"])
        self.assertNotIn(("billing", "audit"), g.edges, "test files are not edges")

    def test_js_workspace_packages_and_relative(self):
        d = repo({
            "packages/api/package.json": '{"name": "@acme/api"}',
            "packages/api/src/index.ts": "export const client = 1;\n",
            "packages/web/package.json": '{"name": "@acme/web"}',
            "packages/web/src/app.tsx": "import { Client, type Opts } from '@acme/api';\nimport React from 'react';\nimport * as ui from '../../ui/src/button';\n",
            "packages/web/src/app.test.tsx": "import { Seed } from '@acme/fixtures';\n",
            "packages/ui/src/button.ts": "const x = require('@acme/api/sub');\n",
        }, 'presets = ["js"]\nmodules = [{ match = "packages/{module}/**" }]\n')
        g = graph(d)
        self.assertEqual(names(g, "web", "api"), ["Client", "Opts"])
        self.assertEqual(names(g, "web", "ui"), ["*"])
        self.assertIn(("ui", "api"), g.edges)

    def test_java_and_kotlin_packages(self):
        d = repo({
            "billing/src/com/acme/billing/Invoice.java": "package com.acme.billing;\nimport com.acme.storage.Blob;\nimport static com.acme.storage.Blob.put;\nimport com.acme.audit.*;\nimport java.util.List;\n",
            "storage/src/com/acme/storage/Blob.java": "package com.acme.storage;\n",
            "audit/src/com/acme/audit/Log.kt": "package com.acme.audit\nimport com.acme.billing.Invoice\n",
        }, 'presets = ["java"]\n')
        g = graph(d)
        self.assertEqual(names(g, "billing", "storage"), ["Blob"])
        self.assertEqual(names(g, "billing", "audit"), ["*"])
        self.assertEqual(g.both_ways(), [("audit", "billing")])

    def test_go_module_paths_and_used_names(self):
        d = repo({
            "go.mod": "module example.com/shop\n",
            "billing/invoice.go": 'package billing\nimport (\n  "fmt"\n  st "example.com/shop/storage"\n)\nfunc f() { st.Put(); st.Get(); fmt.Println() }\n',
            "storage/blob.go": "package storage\n",
            "storage/blob_test.go": 'package storage\nimport "example.com/shop/billing"\n',
        }, 'presets = ["go"]\n')
        g = graph(d)
        self.assertEqual(names(g, "billing", "storage"), ["st.Get", "st.Put"])
        self.assertNotIn(("storage", "billing"), g.edges)

    def test_csharp_namespaces(self):
        d = repo({
            "Billing/Invoice.cs": "using System;\nusing Acme.Storage;\nusing Blobs = Acme.Storage.Blob;\nnamespace Acme.Billing { }\n",
            "Storage/Blob.cs": "namespace Acme.Storage;\n",
        }, 'presets = ["csharp"]\n')
        g = graph(d)
        self.assertEqual(names(g, "Billing", "Storage"), ["Blob", "Storage"])

    def test_terraform_helm_and_regex_extractor(self):
        d = repo({
            "modules/network/main.tf": "",
            "modules/db/main.tf": 'module "net" {\n  source = "../network"\n}\n# module "x" { source = "../cache" }\n',
            "modules/cache/main.tf": "",
            "envs/prod/main.tf": 'module "db" {\n  source = "../../modules/db"\n}\nmodule "ext" { source = "hashicorp/x/aws" }\n',
            "charts/site/Chart.yaml": "dependencies:\n  - name: base\n    repository: file://../base\n",
            "charts/base/Chart.yaml": "",
            "scripts/deploy.sh": 'source "$DIR/../charts/base/lib.sh"\n',
        }, textwrap.dedent('''\
            presets = ["terraform", "k8s"]
            modules = [{ match = "modules/{module}/**" }, { match = "envs/{module}/**", name = "env-{module}" }, { match = "charts/{module}/**", name = "chart-{module}" }, { match = "scripts/**", name = "scripts" }]
            [[extract]]
            files = "**/*.sh"
            regex = '^source "\\$DIR/(?P<path>[^"]+)"'
            '''))
        g = graph(d)
        self.assertEqual(names(g, "env-prod", "db"), ["db"])
        self.assertEqual(names(g, "db", "network"), ["net"])
        self.assertNotIn(("db", "cache"), g.edges)
        self.assertIn(("chart-site", "chart-base"), g.edges)
        self.assertEqual(names(g, "scripts", "chart-base"), ["lib.sh"])


TWO_WAY = {
    "src/api.rs": "use crate::billing::Invoice;\nuse crate::storage::Blob;\n",
    "src/billing.rs": "use crate::api::Handle;\n",
    "src/storage.rs": "use crate::api::Handle;\n",
    "src/audit.rs": "use crate::api::Handle;\nuse crate::billing::Invoice;\n",
}


class Ratchet(unittest.TestCase):
    def check(self, baseline, *extra):
        d = repo({**TWO_WAY, "depgraph-baseline.txt": baseline}, RUST_CFG + 'command = "dg"\n'
                 '[[rules.layer]]\nmodule = "audit"\nmay_use = ["api"]\n')
        return d, run(d, "--check", *extra)

    def test_new_pair_fails_naming_both_sides(self):
        _, (code, out) = self.check("api <-> billing\n")
        self.assertEqual(code, 1)
        self.assertIn("new two-way pair api <-> storage (dg api storage): api -> storage uses Blob  in src/api.rs; "
                      "storage -> api uses Handle  in src/storage.rs", out)
        self.assertIn("src/audit.rs: audit names billing (audit may name only api)", out)

    def test_gone_pair_fails_until_deleted_and_update_only_deletes(self):
        d, (code, out) = self.check("api <-> billing\napi <-> storage\naudit <-> api\n")
        self.assertEqual(code, 1)
        self.assertIn("depgraph-baseline.txt: 'audit <-> api' no longer names both ways", out)
        code, out = run(d, "--check", "--update")
        self.assertIn("dropped from depgraph-baseline.txt: audit <-> api", out)
        self.assertEqual((d / "depgraph-baseline.txt").read_text(), "api <-> billing\napi <-> storage\n")

    def test_allowed_stays_and_summary_marks_status(self):
        d, (code, out) = self.check("api <-> billing  # allowed: shared session type\napi <-> storage\naudit <-> api  # allowed: legacy\n")
        self.assertIn("audit names billing", out)  # only the layer rule fails
        self.assertNotIn("no longer", out)
        code, out = run(d)
        self.assertIn("4 modules, 6 edges, 2 both ways", out)
        self.assertIn("  api <-> billing  (allowed: shared session type)", out)
        self.assertIn("  api <-> storage  (to clear)", out)

    def test_ok_line_and_init(self):
        d = repo(TWO_WAY, RUST_CFG)
        self.assertEqual(run(d, "--init")[1], "wrote depgraph-baseline.txt: 2 pair(s)\n")
        self.assertEqual(run(d, "--check"), (0, "ok graph: 2 to clear, 0 allowed\n"))

    def test_pattern_rule(self):
        d = repo({**TWO_WAY, "src/api.rs": "fn f() { db.raw_sql(); }\n// db.raw_sql()\n", "src/storage.rs": "fn g() { db.raw_sql(); }\n",
                  "depgraph-baseline.txt": ""},
                 RUST_CFG + '[[rules.pattern]]\nforbid = "raw_sql\\\\("\nallow_under = ["src/storage"]\nmessage = "raw sql stays in storage"\n')
        self.assertEqual(run(d, "--check"), (1, "src/api.rs:1: raw sql stays in storage\n"))


class Views(unittest.TestCase):
    def test_pair_and_module_views(self):
        d = repo({**TWO_WAY, "depgraph-baseline.txt": "api <-> billing\n"}, RUST_CFG)
        self.assertEqual(run(d, "api", "billing")[1],
                         "api <-> billing: both ways (to clear)\napi -> billing  1 file(s)\n  src/api.rs  Invoice\n"
                         "billing -> api  1 file(s)\n  src/billing.rs  Handle\n")
        self.assertEqual(run(d, "audit", "storage")[1], "audit <-> storage: no edge\n")
        out = run(d, "api", "--html", str(d / "out.html"))[1]
        self.assertIn("api    out 2    in 3", out)
        self.assertIn("  billing          Invoice  in src/api.rs", out)
        html = (d / "out.html").read_text()
        self.assertIn('"focus":"api"', html)
        self.assertNotIn("/*DATA*/", html)
        self.assertNotRegex(html, r"<script[^>]+src=|<link[^>]+href=", "the page loads nothing from outside")

    def test_diff_reads_git_without_checkout(self):
        d = repo(TWO_WAY, RUST_CFG + 'hubs = ["api"]\n')
        git = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)
        git("init", "-q", "-b", "main")
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "one", "--allow-empty")
        git("add", "-A")
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "two")
        (d / "src/billing.rs").write_text("use crate::storage::Blob;\n")
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "three")
        out = run(d, "--diff", "HEAD~1..HEAD")[1]
        self.assertEqual(out, "edges: +1 -1\n+ billing -> storage  Blob  in src/billing.rs\n- billing -> api\n")
        out = run(d, "--diff", "HEAD~1...HEAD~1")[1]
        self.assertEqual(out, "edges: no change\n")
        (d / "src/storage.rs").write_text("")  # the work tree does not matter to --diff
        self.assertEqual(run(d, "--diff", "HEAD~2..HEAD~1")[1].splitlines()[0], "edges: +6 -0")
        self.assertIn("+ audit -> api  Handle  in src/audit.rs  (into a hub: the report says why)", run(d, "--diff", "HEAD~2..HEAD~1")[1])


if __name__ == "__main__":
    unittest.main()
