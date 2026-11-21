# JUnit Census

Catch tests that disappear from a green CI run. Compare two sets of JUnit XML reports and see exactly which tests went missing or became skipped, even when the total test count stays the same.

One Python file. Standard library only. Runs locally with Python 3.10+. Works on saved artifacts without a GitHub token, CI service, or network access.

## Try it

```sh
git clone https://github.com/shelbygrayman/junit-census.git
cd junit-census
python3 junit_census.py --demo
```

```text
JUnit Census | baseline 2 | current 2
missing: 1
  "checkout" / "refund"
newly skipped: 1
  "checkout" / "receipt"
added: 1
  "checkout" / "coupon"
```

Both reports contain two tests. A count-only check passes. Census exits with code 1 because the refund test disappeared and the receipt test stopped running.

## Use your own reports

Save a known-good run and the candidate run from the same job, platform, and test selection. Give Census either files or directories containing only JUnit XML reports. Directories include nested shards. You can also pass several paths per side.

```sh
python3 junit_census.py --base artifacts/main/ --head artifacts/pr/
python3 junit_census.py --base before.xml --head after.xml --json
```

For a pytest project, run the following once on each revision under the same environment. Save the first XML outside your checkout before switching revisions.

```sh
python -m pytest --junitxml=report.xml
```

In CI, keep the usual test command and its failure status. Download or restore your baseline artifact, generate the candidate report, then run Census as an additional step. An intentionally removed or renamed test needs review before promoting the candidate report to the next baseline.

| Exit | Meaning |
| --- | --- |
| 0 | Every baseline identity is present and no previously running test became skipped. Additions are allowed. |
| 1 | A baseline identity disappeared or became skipped. |
| 2 | Input could not be compared. Examples include duplicate identities, an empty baseline, malformed XML or a missing report. |

## Matching and limits

The identity is the exact pair of testcase classname and name, with the enclosing suite name as fallback when classname is empty. Shard filenames and test order can change. The JSON output keeps the two fields separate. For parameterized tests, stable names matter. A rename appears as one removal and one addition.

A direct JUnit `<skipped/>` child marks a skip. Failures and errors still count as present. Producer-specific skip attributes and retry histories are outside this check. Repeated identities are ambiguous, so run it per platform or matrix job. A valid empty current inventory flags every baseline test as missing. A report that contains only summary counts cannot identify individual tests. Census compares what the reporters emitted and cannot detect a test absent from both revisions.

## Evidence

The regression suite includes a real Node.js JUnit reporter run when Node 24 is installed. Two passing runner invocations emit two cases each. Census identifies the removed, skipped and added names. Other cases cover namespaced XML, directories of shards, duplicates, already-skipped tests and invalid input.

```sh
python3 -m unittest -v
python3 benchmark.py
```

Each synthetic benchmark starts a fresh CLI process and compares four shards per revision. The generator replaces one identity and skips another per 1,000 cases. Every timed run checks the exit code and the complete JSON result against the expected names. Median of seven runs on Linux x86_64, Python 3.12.14, warm filesystem. Input generation is outside the timer.

| Testcases per revision | Missing | Newly skipped | Added | Median |
| ---: | ---: | ---: | ---: | ---: |
| 1,000 | 1 | 1 | 1 | 43.32 ms |
| 10,000 | 10 | 10 | 10 | 57.71 ms |
| 50,000 | 50 | 50 | 50 | 172.92 ms |

All timings and platform details are in [benchmark.json](benchmark.json). A zero change in total test count occurred at every size. Runtime varies by machine and report contents.

## Related tools

GitLab compares test failures between pipelines. The publish-unit-test-result action can also annotate removed and newly skipped tests when configured. junitparser offers XML merging and failure verification. Census is for teams that want the missing-test check directly on local artifacts, with a portable exit code. [GitLab test reports](https://docs.gitlab.com/ci/testing/unit_test_reports/) · [publish-unit-test-result](https://github.com/EnricoMi/publish-unit-test-result-action) · [junitparser](https://junitparser.readthedocs.io/en/latest/)

If your runner handles skipped tests or testcase names differently, open an issue with the runner version, two small synthetic XML reports and the output you expected.

MIT licensed.
