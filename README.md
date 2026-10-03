# Magento QA

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

The script starts the containers, waits until Magento is healthy and routes Magento's outgoing email to Mailpit.

To reset the store to its initial sample data:

```bash
docker compose down
```

All state (orders, customers, configuration) lives inside the container, so every run starts from a clean store.

## Roadmap

- [x] Dockerised Magento + Mailpit environment
- [ ] API tests (Pytest + Requests): guest checkout, cart, Bulgarian addresses
- [ ] UI tests (Playwright for Python): critical customer journeys
- [ ] Email assertions through the Mailpit API
- [ ] CI on GitHub Actions with Allure report
- [ ] Accessibility (axe-core), performance (k6), visual regression

## Notes

- Windows reserves several TCP port ranges for Hyper-V. If a port is refused, list the reserved ranges with `netsh interface ipv4 show excludedportrange protocol=tcp` and pick another one. This project uses 8080 and 8025.
- The image runs Magento in developer mode, so API errors include full stack traces. That is expected here, but it would be a security finding on a production store.

## License

[MIT](LICENSE)
