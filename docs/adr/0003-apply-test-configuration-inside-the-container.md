# 0003. Apply test configuration inside the container on start

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

A few Magento defaults get in the way of automated tests:

- Outgoing email uses sendmail, so tests cannot read it.
- The admin password expires 90 days after the image build and then forces a change.
- Password-reset requests are throttled by IP; all test traffic comes from one IP.

The first approach applied these settings after start with `docker exec ... bin/magento config:set`. That raced the container: the image warms Magento's config cache at build time, so for a short time after the store looked ready it still used the old values, and an email sent in that window was lost. The container healthcheck also passed before Elasticsearch was ready.

## Decision

Apply the settings inside the container on every start, through the `custom-entrypoint.sh` hook the image runs before its final cache flush. The script writes the settings to `core_config_data`, cleans the config cache and creates a marker file.

The healthcheck reports healthy only when the marker exists **and** a GraphQL catalog search returns products. Every deviation from Magento defaults is listed in the README.

## Consequences

- `docker compose up --wait` means "ready for tests"; no separate setup step, locally or in CI.
- No window where the store runs with stale configuration.
- Search readiness is part of health, so the first tests never meet a half-started store.
- The deviations are explicit and reviewable in one script; they would not be acceptable on a production store and are documented as test-only.
