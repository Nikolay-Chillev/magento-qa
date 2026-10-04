# Magento QA

[![CI](https://github.com/Nikolay-Chillev/magento-qa/actions/workflows/ci.yml/badge.svg)](https://github.com/Nikolay-Chillev/magento-qa/actions/workflows/ci.yml)
[![Allure report](https://img.shields.io/badge/Allure-report-orange)](https://nikolay-chillev.github.io/magento-qa/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Test automation for a Magento 2 e-commerce store, built the way a retail QA team would approach it: API, UI, transactional emails, accessibility and performance, all running against a disposable Docker environment and in CI.

Magento (Adobe Commerce Open Source) powers many large European online shops, so the scenarios here mirror real retail flows: catalog, cart, checkout, customer accounts and order emails.

## Environment

| Service | Image | URL |
|---|---|---|
| Magento 2.4.9 + Luma sample data | [magento2-in-a-box](https://github.com/controlaltdelete-nl/magento2-in-a-box) | http://localhost:8080 |
| Magento admin | | http://localhost:8080/admin |
| Mailpit (catches all outgoing email) | [axllent/mailpit](https://github.com/axllent/mailpit) | http://localhost:8025 |

Admin credentials are the defaults documented in the [magento2-in-a-box README](https://github.com/controlaltdelete-nl/magento2-in-a-box#readme).

## Quick start

Requirements: Docker and a Bash shell (Git Bash on Windows).

```bash
./scripts/start.sh
```

The script starts the containers and waits until the store is ready for tests: the test configuration is applied and catalog search answers. A fresh start takes about 45 seconds.

To reset the store to its initial sample data:

```bash
docker compose down
```

All state (orders, customers, configuration) lives inside the container, so every run starts from a clean store.

## Test environment

The Magento image is pinned by digest, so every run uses exactly the same build. On each start, [`docker/magento/custom-entrypoint.sh`](docker/magento/custom-entrypoint.sh) applies a few settings that deviate from Magento defaults on purpose:

| Setting | Default | Here | Why |
|---|---|---|---|
| `system/smtp/*` | sendmail | SMTP to `mailpit:1025` | Every outgoing email lands in Mailpit, where tests can assert on it |
| `admin/security/password_lifetime` | 90 days | 0 (never expires) | The image's admin password would otherwise force a change 90 days after the image was built |
| `customer/password/password_reset_protection_type` | By IP and email | By email | All test traffic comes from one IP, so IP-based throttling would allow one reset per 10 minutes for the whole suite |

The container reports healthy only after these settings are active and catalog search returns results, so `docker compose up --wait` is enough to know the store is ready.

## Development

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # create .venv with all dependencies
uv run python -m pytest -m smoke         # check that the environment works
uv run python -m pytest                  # run all tests
uv run python -m pre_commit install      # lint, format and type-check on every commit
```

Settings default to the local Docker environment. Override them with `QA_*` environment variables or a `.env` file, see [`.env.example`](.env.example).

Commands go through `python -m` so they also work where Windows Smart App Control blocks unsigned executables inside the virtual environment. For the same reason mypy is installed from source (`no-binary-package` in `pyproject.toml`).

## Documentation

- [Test strategy](docs/test-strategy.md): scope, risks and priorities, test levels, data, merge criteria
- [Architecture decisions](docs/adr/): why Magento in a pinned image, why Python for API and UI, how the environment is configured
- [Findings](docs/findings.md): defects and risks found in the store and its environment

## Roadmap

- [x] Dockerised Magento + Mailpit environment, pinned by digest
- [x] CI on GitHub Actions: lint, type checks, tests in parallel, Allure results
- [x] API: guest checkout with a Bulgarian address, order record and confirmation email
- [ ] API: cart, coupons and promotions, all 28 oblasts, VAT
- [ ] API: customer accounts and security, GraphQL
- [ ] UI (Playwright for Python): checkout, catalog, accounts, mobile
- [x] Allure report on GitHub Pages, with history across runs
- [ ] Nightly cross-browser run
- [ ] Accessibility (axe-core), performance smoke (k6)

## Notes

- Windows reserves several TCP port ranges for Hyper-V. If a port is refused, list the reserved ranges with `netsh interface ipv4 show excludedportrange protocol=tcp` and pick another one. This project uses 8080 and 8025.
- The image runs Magento in developer mode, so API errors include full stack traces; expected here, a finding on a production store ([#15](https://github.com/Nikolay-Chillev/magento-qa/issues/15)).

## License

[MIT](LICENSE)
