"""Accessibility scans with axe-core, against the WCAG 2.1 A and AA rules.

Version 2.1 AA is the level EN 301 549, and through it the European Accessibility
Act, refers to. The axe-core version is the one bundled with axe-playwright-python.
"""

import json
from dataclasses import dataclass
from typing import Any

import allure
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page

WCAG_21_AA = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]


@dataclass(frozen=True)
class Violation:
    rule: str
    impact: str
    help: str
    targets: list[str]

    def describe(self) -> str:
        return f"{self.rule} ({self.impact}): {self.help} at {', '.join(self.targets)}"


def scan(page: Page) -> dict[str, Violation]:
    """The violations on the current page, by axe rule id; the details go to the report."""
    with allure.step("Scan the page with axe-core (WCAG 2.1 A and AA)"):
        response: dict[str, Any] = (
            Axe().run(page, options={"runOnly": {"type": "tag", "values": WCAG_21_AA}}).response
        )
        violations = response["violations"]
        allure.attach(
            json.dumps(violations, indent=2),
            name="axe violations",
            attachment_type=allure.attachment_type.JSON,
        )
    return {
        violation["id"]: Violation(
            rule=violation["id"],
            impact=violation["impact"],
            help=violation["help"],
            targets=[" ".join(node["target"]) for node in violation["nodes"]],
        )
        for violation in violations
    }
