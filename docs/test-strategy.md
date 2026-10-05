# Test strategy

How this project decides what to test, at which level, and when a change is good enough to merge.

## System under test

A Magento 2.4.9 store with the Luma theme and sample data (about 2,000 products, cart price rules, one customer), running in Docker. Magento is the platform behind many large European online shops, so the scenarios follow a retail store: browse, cart, checkout, customer accounts, transactional email.

**In scope**
- Storefront journeys of guests and registered customers
- REST and GraphQL APIs used by the storefront and by headless clients
- Transactional emails (order confirmation, registration, password reset)
- Bulgarian specifics: addresses with oblasts, EUR prices
- Accessibility of key pages, basic performance

**Out of scope**
- The admin panel UI (the admin REST API is used to verify and set up data)
- Real payment providers: only Magento's offline methods (check / money order)
- Magento's own unit and integration tests
- Load testing: the container runs four PHP workers, so throughput numbers would mean nothing

## Risks and priorities

Each risk gets a priority from its business impact. Priority decides the order of work and the depth of coverage.

| Risk | Impact if it happens | Priority | Covered by |
|---|---|---|---|
| A customer cannot complete a purchase | Direct loss of revenue | **P1** | API: guest checkout ✅ · UI: guest checkout and form validation ✅ |
| Totals are wrong (price, shipping, tax, discounts) | Revenue loss or overcharged customers, legal exposure | **P1** | API: checkout, cart and promotion totals ✅ |
| Cart accepts what it should not (missing variant, quantity beyond stock or invalid) | Unfulfillable orders, wrong charges | **P1** | API: variants and quantity rules ✅ ([#29](https://github.com/Nikolay-Chillev/magento-qa/issues/29) open) |
| The order is not recorded, or recorded with wrong data | Order cannot be fulfilled | **P1** | API: order in the back office ✅ |
| The customer gets no confirmation | Support calls, lost trust | **P1** | Email: order confirmation ✅ |
| Bulgarian addresses are rejected or stored wrongly | Lost local customers, failed deliveries | **P2** | API: orders to all 28 oblasts, required address fields ✅ · UI: oblast dropdown ✅ |
| VAT missing or wrong | Under- or over-charged customers, tax compliance | **P1** | API: 20% Bulgarian VAT, no VAT outside Bulgaria, catalog tax-class audit ✅ ([#39](https://github.com/Nikolay-Chillev/magento-qa/issues/39) open) |
| Coupons and promotions misapplied | Margin loss or angry customers | **P2** | API: coupon codes, end dates, automatic promotions ✅ ([#34](https://github.com/Nikolay-Chillev/magento-qa/issues/34), [#35](https://github.com/Nikolay-Chillev/magento-qa/issues/35) open) · coupon usage limits ✅ · UI: coupon in the cart ✅ |
| Account security: lockout, password reset, access to other customers' data | Account takeover, data leak | **P2** | API + UI (planned) |
| Search and category browsing broken | Customers cannot find products | **P2** | UI: home page → product page smoke ✅ · search and filters (planned) |
| Accessibility barriers | Excluded customers; non-compliance with the European Accessibility Act | **P3** | axe checks (planned) |
| Slow pages or API under load | Lower conversion | **P3** | k6 smoke (planned) |

## Test levels

```
            UI journeys (Playwright)          few, slow, only what needs a browser
        Email checks (Mailpit)                each journey that sends mail
    API tests (REST + GraphQL)                most business rules
 Smoke tests                                  "is the environment usable?"
Unit tests of the framework                   fast, no environment
```

- **Unit**: the framework's own logic (settings, waits, error rendering, masking, factories). No environment, run in milliseconds.
- **Smoke**: storefront, REST, GraphQL search and Mailpit answer. A failure means the environment is broken, not the store.
- **API**: the bulk of the business rules. Fast, stable and precise about what failed.
- **Email**: the emails the store sends, read from Mailpit by recipient.
- **UI**: only journeys whose risk is in the browser (forms, validation messages, the region dropdown, mini-cart). Preconditions come from the API.
- **Non-functional**: accessibility scans with a baseline of known Luma violations; a performance smoke test that watches for regressions, not absolute numbers.

## Design principles

1. **Set up through the API, verify through the interface under test.** A UI test never clicks through steps it does not verify.
2. **Every test owns its data.** Unique customers (`qa+<random>@example.com`), carts and orders, so tests run in any order and in parallel.
3. **Sample data is read-only.** Tests never change shared products or global settings; changes that must be global happen in environment setup.
4. **No fixed sleeps.** Waits poll a condition with a timeout and a description of what was awaited.
5. **Responses are contracts.** API responses are parsed into Pydantic models, so a changed shape fails clearly.
6. **Failures explain themselves.** Each HTTP exchange is attached to the Allure report, with credentials masked.

## Test data

- Products, prices and promotions come from the Luma sample data and are only read.
- Customers and addresses are generated with [bg-test-data](https://github.com/Nikolay-Chillev/bg-test-data): Bulgarian names, mobile numbers and postal addresses. Oblasts are matched to Magento regions by ISO 3166-2 code ([ADR 0004](adr/0004-match-bulgarian-regions-by-iso-code.md)).
- No real personal data; every email goes to `example.com` and is caught by Mailpit.

## Environments

One environment definition for local runs and CI: Magento and Mailpit in Docker Compose, both images pinned by digest ([ADR 0001](adr/0001-magento-with-sample-data-in-a-pinned-image.md)). A few settings deviate from Magento defaults for testability; they are applied inside the container ([ADR 0003](adr/0003-apply-test-configuration-inside-the-container.md)) and listed in the [README](../README.md#test-environment).

Known limitations of the environment:
- Developer mode: API errors include stack traces ([#15](https://github.com/Nikolay-Chillev/magento-qa/issues/15)).
- No cron and no queue consumers: index updates and coupon usage counters do not happen on their own ([ADR 0005](adr/0005-trigger-cron-and-queue-consumers-explicitly.md), proposed).

## Execution

| When | What runs | Where |
|---|---|---|
| Every pull request and push to `main` | Lint, type checks, all tests with three parallel workers against a fresh store | GitHub Actions |
| Nightly (planned) | All tests, UI in Chromium, Firefox and WebKit | GitHub Actions |
| Locally | `./scripts/start.sh`, then `uv run python -m pytest` | Developer machine |

## Merge and release criteria

Every change reaches `main` through a pull request; a branch ruleset enforces this and requires the `CI passed` check, which fails if linting, type checks or any test fail. Documentation-only changes skip the test jobs but still report the check.

A pull request is merged when:
- CI is green: lint, types and all tests
- new tests are independent and have no fixed sleeps
- documentation is updated where behaviour or setup changed

v1.0 is released when the P1 and P2 risks above have API coverage, P1 journeys have UI coverage, and ten consecutive nightly runs pass without a flaky test.

## Reporting

- **[Allure report](https://nikolay-chillev.github.io/magento-qa/)** published after every push to `main`, with trends across runs; every CI run also keeps its raw results for 14 days
- **Findings** in the store or the environment: GitHub issues labelled `finding`, summarised in [findings.md](findings.md)
- **Decisions**: [architecture decision records](adr/)
