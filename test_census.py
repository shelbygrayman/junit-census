import contextlib
import io
import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from junit_census import main


class CensusTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.base = self.root / "base.xml"
        self.head = self.root / "head.xml"
        self.xml = '<testsuite name="orders"><testcase name="refund"/></testsuite>'
        self.base.write_text(self.xml)
        self.head.write_text(self.xml)

    def check(self, expected, head=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--base", str(self.base), "--head", str(head or self.head), "--json"])
        self.assertEqual(code, expected, err.getvalue())
        if code == 2:
            self.assertFalse(out.getvalue())
            return err.getvalue()
        return json.loads(out.getvalue())

    def test_identical(self):
        self.assertEqual(self.check(0)["missing"], [])

    def test_full_replacement_equal_count(self):
        self.head.write_text(self.xml.replace("refund", "coupon"))
        report = self.check(1)
        self.assertEqual(report["missing"], [["orders", "refund"]])
        self.assertEqual(report["added"], [["orders", "coupon"]])

    def test_skip_transition(self):
        self.head.write_text(self.xml.replace('name="refund"/>', 'name="refund"><skipped/></testcase>'))
        self.assertEqual(self.check(1)["newly_skipped"], [["orders", "refund"]])
        self.base.write_bytes(self.head.read_bytes())
        self.check(0)

    def test_failures_still_executed(self):
        self.head.write_text(self.xml.replace('name="refund"/>', 'name="refund"><failure/></testcase>'))
        self.check(0)

    def test_report_directory_and_namespaces(self):
        folder = self.root / "shards"
        folder.mkdir()
        (folder / "a.xml").write_text(self.xml.replace("<testsuite ", '<testsuite xmlns="urn:test" '))
        (folder / "b.xml").write_text(self.xml.replace("refund", "coupon"))
        self.assertEqual(self.check(0, folder)["added"], [["orders", "coupon"]])

    def test_different_suite_same_class(self):
        self.base.write_text(self.xml.replace("<testcase ", '<testcase classname="Cart" '))
        self.head.write_text(self.base.read_text().replace("orders", "shard2"))
        self.check(0)

    def test_duplicate(self):
        self.head.write_text("<testsuites>" + self.xml * 2 + "</testsuites>")
        self.assertIn("duplicate", self.check(2))

    def test_complete_disappearance(self):
        self.head.write_text("<testsuites/>")
        self.assertEqual(len(self.check(1)["missing"]), 1)

    def test_empty_baseline(self):
        self.base.write_text("<testsuites/>")
        self.assertIn("baseline", self.check(2))

    def test_malformed_inputs(self):
        for xml in ('<testsuite>', '<unrelated/>', '<testsuite tests="4"/>', '<testsuites tests="4"/>',
                    '<!DOCTYPE testsuite><testsuite/>', '<testsuite><testcase/></testsuite>'):
            with self.subTest(xml=xml):
                self.head.write_text(xml)
                self.check(2)

    def test_missing_file_and_empty_directory(self):
        self.head.unlink()
        self.check(2)
        self.head.mkdir()
        self.check(2)

    @unittest.skipUnless(shutil.which("node"), "optional real Node.js JUnit reporter test")
    def test_node_reporter(self):
        script = self.root / "checkout.cjs"
        for target, source in (
            (self.base, "test('refund', () => {}); test('receipt', () => {});"),
            (self.head, "test('coupon', () => {}); test.skip('receipt', () => {});"),
        ):
            script.write_text("const { test } = require('node:test'); " + source)
            with target.open("wb") as output:
                subprocess.run(["node", "--test", "--test-reporter=junit", str(script)],
                               check=True, stdout=output)
        report = self.check(1)
        for key, name in (("missing", "refund"), ("newly_skipped", "receipt"), ("added", "coupon")):
            self.assertEqual([row[1] for row in report[key]], [name])

    def test_direct_node_cases_and_distinct_parameters(self):
        self.head.write_text('<testsuites><testcase classname="orders" name="refund"/>'
                             '<testcase classname="orders" name="refund[USD]"/></testsuites>')
        self.assertEqual(self.check(0)["added"], [["orders", "refund[USD]"]])


if __name__ == "__main__":
    unittest.main()
