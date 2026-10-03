# 0001. Test Magento 2 with sample data from a ready image, pinned by digest

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

The project needs a realistic online store to test: a catalog with product variants, promotions, checkout, customer accounts and transactional email, the way a retail QA team would test it. Testing a real public shop is not an option: bot protection blocks automation, terms of service forbid it, test orders would be real orders, and load tests would amount to an attack.

Candidates were open-source platforms that run in Docker:

| | Magento 2 | Saleor | PrestaShop | Spree |
|---|---|---|---|---|
| Used by large European retailers | Yes | Some | Mostly small shops | Few |
| Ready image with sample data | Yes (magento2-in-a-box) | No storefront in compose | Yes | Yes |
| APIs | REST and GraphQL | GraphQL | Legacy webservice | REST |
| Offline payment for tests | Yes | Needs a payment app | Yes | Yes |
| Weight | Heavy | Medium | Light | Medium |

Building a Magento image ourselves (PHP, MySQL, OpenSearch, Redis, sample data) takes 10–20 minutes per build and is a project of its own.

## Decision

Use Magento 2.4.9 with the Luma sample data from the community image [magento2-in-a-box](https://github.com/controlaltdelete-nl/magento2-in-a-box), which bundles all services in one container and is used by payment providers to run their own end-to-end tests in CI.

Pin the image by tag **and** digest in `docker-compose.yml`, so every local and CI run uses the same build. Mailpit is pinned the same way. Dependabot proposes digest updates, and CI proves the suite still passes before one is merged.

## Consequences

- A fresh store with sample data starts in about 45 seconds, locally and in CI; every run starts from a clean state.
- Tests target the same platform as many real European shops, with both REST and GraphQL.
- The image is maintained by a third party. If it disappears, the fallback is to build an equivalent image from Mage-OS; the digest pin protects against silent changes meanwhile.
- The image runs in developer mode and without cron or queue consumers, which the tests have to account for ([0005](0005-trigger-cron-and-queue-consumers-explicitly.md)).
- The theme is Luma, not Hyvä as on some production stores; Hyvä can be added later as a separate step.
