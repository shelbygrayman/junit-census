"""Time the shipped CLI and verify every reported identity against the input generator."""
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from junit_census import __file__ as cli


def write_shards(folder, size, changed):
    folder.mkdir()
    for shard in range(4):
        with (folder / f"{shard}.xml").open("w") as report:
            report.write('<testsuite name="cart">')
            for i in range(shard, size, 4):
                name = f"replacement_{i}" if changed and i % 1000 == 0 else f"test_{i}"
                status = "<skipped/>" if changed and i % 1000 == 1 else ""
                report.write(f'<testcase name="{name}">{status}</testcase>')
            report.write('</testsuite>')


def measure(size):
    with tempfile.TemporaryDirectory() as tmp:
        base, head = Path(tmp) / "base", Path(tmp) / "head"
        write_shards(base, size, False)
        write_shards(head, size, True)
        expected = {
            "baseline": size, "current": size,
            "missing": sorted([ "cart", f"test_{i}"] for i in range(0, size, 1000)),
            "added": sorted(["cart", f"replacement_{i}"] for i in range(0, size, 1000)),
            "newly_skipped": sorted(["cart", f"test_{i}"] for i in range(1, size, 1000)),
        }
        times = []
        for _ in range(7):
            start = time.perf_counter()
            proc = subprocess.run([sys.executable, cli, "--base", base, "--head", head, "--json"],
                                  capture_output=True, text=True)
            times.append(round((time.perf_counter() - start) * 1000, 2))
            if proc.returncode != 1 or json.loads(proc.stdout) != expected:
                raise RuntimeError(f"incorrect CLI result: {proc.stderr}")
        return {"cases_per_revision": size, "shards_per_revision": 4, "runs_ms": times,
                "median_ms": statistics.median(times), "missing": len(expected["missing"]),
                "newly_skipped": len(expected["newly_skipped"]), "added": len(expected["added"])}


if __name__ == "__main__":
    print(json.dumps({"python": platform.python_version(), "platform": platform.platform(),
                      "processor": platform.machine(), "timing": "fresh process, warm filesystem",
                      "measurements": [measure(size) for size in (1000, 10000, 50000)]}, indent=2))
