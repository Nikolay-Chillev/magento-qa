# 0002. Python for both API and UI tests

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

API tests are a natural fit for Python (pytest, requests, Pydantic). For the UI, Playwright is available both for Python (via pytest-playwright) and for TypeScript (Playwright Test). The TypeScript runner has more features out of the box, most notably screenshot comparison (`toHaveScreenshot`), sharding and its own HTML report.

A UI test usually needs the same building blocks as an API test: settings, API clients to prepare data, test data factories, the Mailpit client and Allure reporting.

## Decision

Write API and UI tests in Python, in one pytest suite, sharing models, clients, factories and fixtures.

If visual regression testing is added, it will be a small, separate Playwright Test (TypeScript) project, because Playwright for Python has no screenshot assertion.

## Consequences

- One language, one test runner, one dependency lock and one Allure report for the whole suite.
- UI tests prepare data with the same API clients the API tests use, instead of duplicating them in a second language.
- Parallel runs use pytest-xdist rather than Playwright's built-in sharding.
- Visual regression, if needed, adds a second toolchain in a clearly separated directory.
