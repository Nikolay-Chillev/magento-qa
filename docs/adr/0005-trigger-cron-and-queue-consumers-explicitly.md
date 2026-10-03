# 0005. Trigger cron jobs and queue consumers explicitly in tests

- **Status:** Proposed
- **Date:** 2026-10-03

## Context

On a production Magento store, cron runs every minute and message-queue consumers process background work. The test image runs neither: `cron_schedule` is empty, all indexers are on "Update by Schedule", and messages stay in their queues.

Two kinds of tests depend on that background work:

- Catalog changes made through the admin API (new products, prices, stock) only reach category pages, search and the price index after the indexers run.
- Coupon usage is counted by the `sales.rule.update.coupon.usage` consumer, so a "one use per customer" limit cannot be enforced without it.

Running cron permanently in the container would make the suite timing-dependent: a test would pass or fail depending on whether a cron run happened in time.

## Decision

Add a small `env_control` module that runs the needed work on demand through `docker exec`: `bin/magento cron:run --group=index` and `bin/magento queue:consumers:start <name> --max-messages=N`. Only tests marked `env_control` use it, and they call it at the point where a real store would have done the work.

Catalog tests keep using the sample data read-only, so most tests never need it.

## Consequences

- Tests that depend on background processing become deterministic.
- The `env_control` tests need access to the Docker container, so they can only run where the suite controls the environment (locally and in CI), not against a remote store.
- To be implemented with the first test that needs it (coupon usage limits).
