"""Summaries of a test run for the GitHub Actions job page.

Usage: ``uv run python -m magento_qa.reporting junit.xml Firefox >> "$GITHUB_STEP_SUMMARY"``
"""

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunSummary:
    passed: int = 0
    xfailed: int = 0
    skipped: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)  # (test, first message line)
    seconds: float = 0.0

    def markdown(self, label: str) -> str:
        status = "passed" if not self.failed else "failed"
        lines = [
            f"### {label}: {status}",
            "",
            f"{self.passed} passed, {len(self.failed)} failed, {self.xfailed} xfailed, "
            f"{self.skipped} skipped in {self.seconds:.0f} s",
        ]
        if self.failed:
            lines += ["", "| Failed test | Message |", "|---|---|"]
            lines += [
                f"| `{name}` | {message.replace('|', '/')} |" for name, message in self.failed
            ]
        return "\n".join(lines) + "\n"


def summarise(junit_xml: str) -> RunSummary:
    """Count the results in a JUnit XML report written by ``pytest --junitxml``."""
    root = ET.fromstring(junit_xml)
    summary = RunSummary()
    for suite in root.iter("testsuite"):
        summary.seconds += float(suite.get("time", "0"))
    for case in root.iter("testcase"):
        name = f"{case.get('classname', '')}::{case.get('name', '')}"
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        skipped = case.find("skipped")
        if problem is not None:
            message = (problem.get("message") or problem.text or "").strip()
            summary.failed.append((name, message.splitlines()[0] if message else ""))
        elif skipped is not None and skipped.get("type") == "pytest.xfail":
            summary.xfailed += 1
        elif skipped is not None:
            summary.skipped += 1
        else:
            summary.passed += 1
    return summary


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m magento_qa.reporting JUNIT_XML LABEL", file=sys.stderr)
        return 2
    path, label = argv
    report = Path(path)
    if not report.exists():
        print(f"### {label}: no results\n\nThe tests did not produce {path}.")
        return 0
    print(summarise(report.read_text(encoding="utf-8")).markdown(label), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
