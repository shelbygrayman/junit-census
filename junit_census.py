#!/usr/bin/env python3
"""Find tests that disappeared or stopped running between two JUnit XML reports."""
import argparse
import json
import sys
from io import BytesIO
from pathlib import Path
from xml.parsers import expat


class ReportError(ValueError):
    """The report does not provide an unambiguous inventory."""


def read_report(stream, cases, source):
    """Read testcase identities without retaining log output or building an XML tree."""
    stack = []
    suites = []
    active = None
    count = 0

    def reject(reason):
        raise ReportError(f"{source}: {reason}")

    def start(tag, attrs):
        nonlocal active, count
        tag = tag.rsplit("}", 1)[-1]
        parent = stack[-1] if stack else None
        if parent is None and tag not in ("testsuite", "testsuites"):
            reject("expected a JUnit testsuite or testsuites root")
        if tag in ("testsuite", "testsuites"):
            if parent not in (None, "testsuites", "testsuite"):
                reject("unexpected testsuite location")
            suites.append((attrs.get("name", ""), count, attrs.get("tests")))
        if tag == "testcase":
            if parent not in ("testsuite", "testsuites") or active is not None:
                reject("unexpected testcase location")
            name = attrs.get("name", "")
            if not name.strip():
                reject("testcase has no name")
            group = attrs.get("classname") or (suites[-1][0] if suites else "")
            active = ((group, name), False)
            count += 1
        if parent == "testcase" and tag == "skipped":
            active = (active[0], True)
        stack.append(tag)

    def end(tag):
        nonlocal active
        tag = stack.pop()
        if tag == "testcase":
            identity, skipped = active
            if identity in cases:
                reject(f"duplicate identity {json.dumps(identity)}; compare each matrix job separately")
            cases[identity] = skipped
            active = None
        if tag in ("testsuite", "testsuites"):
            _, initial, declared = suites.pop()
            if declared is not None and count == initial:
                try:
                    expected = int(declared)
                except ValueError:
                    reject("invalid suite test count")
                if expected > 0:
                    reject("summary-only suite has no testcase identities")

    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = lambda *_: reject("DOCTYPE is unsupported")
    try:
        parser.ParseFile(stream)
    except expat.ExpatError as err:
        reject(str(err))


def inventory(paths):
    cases = {}
    for path in paths:
        files = sorted(path.rglob("*.xml")) if path.is_dir() else [path]
        if not files:
            raise ReportError(f"{path}: no XML reports found")
        for file in files:
            with file.open("rb") as stream:
                read_report(stream, cases, file)
    return cases


def compare(base, head):
    return {
        "baseline": len(base),
        "current": len(head),
        "missing": sorted(base.keys() - head.keys()),
        "newly_skipped": sorted(key for key in base.keys() & head.keys() if head[key] and not base[key]),
        "added": sorted(head.keys() - base.keys()),
    }


def render(result, as_json):
    if as_json:
        print(json.dumps(result, indent=2))
        return
    print(f"JUnit Census | baseline {result['baseline']} | current {result['current']}")
    for key in ("missing", "newly_skipped", "added"):
        items = result[key]
        print(f"{key.replace('_', ' ')}: {len(items)}")
        for item in items[:15]:
            print("  " + " / ".join(json.dumps(part, ensure_ascii=True) for part in item))
        if len(items) > 15:
            print(f"  ... {len(items) - 15} more (see --json)")


def demo():
    base = b'<testsuite name="checkout"><testcase name="refund"/><testcase name="receipt"/></testsuite>'
    head = b'<testsuite name="checkout"><testcase name="receipt"><skipped/></testcase><testcase name="coupon"/></testsuite>'
    inventories = []
    for xml in (base, head):
        items = {}
        read_report(BytesIO(xml), items, "demo")
        inventories.append(items)
    return compare(*inventories)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, nargs="+", help="known-good XML files or report directories")
    parser.add_argument("--head", type=Path, nargs="+", help="current XML files or report directories")
    parser.add_argument("--demo", action="store_true", help="run a built-in example with intentional drift")
    parser.add_argument("--json", action="store_true", help="write complete machine-readable results")
    args = parser.parse_args(argv)
    if args.demo:
        if args.base or args.head:
            parser.error("--demo takes no reports")
        result = demo()
    else:
        if not (args.base and args.head):
            parser.error("supply both --base and --head, or use --demo")
        try:
            base = inventory(args.base)
            if not base:
                raise ReportError("baseline contains no testcases")
            result = compare(base, inventory(args.head))
        except (OSError, ReportError) as err:
            print(f"junit-census: {err}", file=sys.stderr)
            return 2
    render(result, args.json)
    return int(bool(result["missing"] or result["newly_skipped"]))


if __name__ == "__main__":
    sys.exit(main())
