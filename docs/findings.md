# Findings

Defects and risks found while testing the store and its environment. Each finding is a GitHub issue labelled [`finding`](https://github.com/Nikolay-Chillev/magento-qa/issues?q=label%3Afinding) with steps to reproduce; this page is the summary.

**Source** separates what Magento itself does (*product*) from how this Docker image is configured (*environment*) and from the sample catalog (*test data*). Environment findings would be configuration tickets on a real project, not Magento bugs, but they are exactly what a pre-production review should catch.

| # | Finding | Severity | Source | Status |
|---|---|---|---|---|
| [#14](https://github.com/Nikolay-Chillev/magento-qa/issues/14) | Every response allows cross-origin access from any site | Major | Environment | Open |
| [#15](https://github.com/Nikolay-Chillev/magento-qa/issues/15) | API error responses expose stack traces | Major | Environment | Accepted for testing |
| [#16](https://github.com/Nikolay-Chillev/magento-qa/issues/16) | `/health_check.php` returns 500 while the store is healthy | Major | Environment + product | Open, worked around |
| [#17](https://github.com/Nikolay-Chillev/magento-qa/issues/17) | Server header discloses the nginx version and OS | Minor | Environment | Open |
| [#18](https://github.com/Nikolay-Chillev/magento-qa/issues/18) | Elasticsearch crashes on the first start of a fresh container | Minor | Environment | Open, worked around |
| [#19](https://github.com/Nikolay-Chillev/magento-qa/issues/19) | Missing oblast is only rejected when the order is placed | Minor | Product | Open, covered by a test |
| [#20](https://github.com/Nikolay-Chillev/magento-qa/issues/20) | Product names in API responses contain HTML entities | Minor | Test data | Open |
| [#29](https://github.com/Nikolay-Chillev/magento-qa/issues/29) | REST cart API turns zero and negative quantities into 1 | Major | Product | Open, covered by `xfail` tests |

## Details

### #14 Every response allows cross-origin access from any site

Storefront, REST and GraphQL responses send `Access-Control-Allow-Origin: *` with all methods and headers allowed. On a production store any website could call the store's APIs from a visitor's browser and read the answers. The headers come from the image's nginx configuration. **Recommendation:** no CORS headers, or an allow-list of the store's own frontends.

### #15 API error responses expose stack traces

REST errors include a `trace` field with server paths and class names, because the image runs Magento in developer mode. Acceptable in a test environment and useful for debugging, so it is accepted here; on a production store it is information disclosure. **Recommendation:** production mode on any public environment.

### #16 `/health_check.php` returns 500 while the store is healthy

The cache configuration in `app/etc/env.php` defines `backend_options` (igbinary serializer) without a `backend`. Magento falls back to the file cache at runtime, but `pub/health_check.php` treats such a frontend as misconfigured and answers 500. A load balancer or uptime monitor using this endpoint would take a healthy store out of service. **Workaround:** the suite's readiness check uses a GraphQL catalog search instead. **Recommendation:** declare the cache `backend` explicitly.

### #17 Server header discloses the nginx version and OS

`Server: nginx/1.18.0 (Ubuntu)` on every response helps match the server to known vulnerabilities. **Recommendation:** `server_tokens off`.

### #18 Elasticsearch crashes on the first start of a fresh container

A `write.lock` file created when the image was built makes Elasticsearch fail its first start (`AlreadyClosedException`); supervisord restarts it. Search is unavailable for longer after start. **Workaround:** the container healthcheck waits for a successful catalog search ([ADR 0003](adr/0003-apply-test-configuration-inside-the-container.md)).

### #19 Missing oblast is only rejected when the order is placed

For a Bulgarian address without `region_id`, the shipping-information step succeeds and returns totals; only the order placement fails with `"regionId" is required`. The Luma form prevents this for shoppers, but headless and mobile clients using the API learn about the invalid address one step late. Covered by `test_address_without_region_is_rejected`.

### #20 Product names in API responses contain HTML entities

`Minerva LumaTech&trade; V-Tee` instead of `Minerva LumaTech™ V-Tee`, in GraphQL search results and in order items. The Luma theme renders it as HTML, but a client that treats names as text would show `&trade;` literally. A sample-data quality issue rather than a Magento defect.

### #29 REST cart API turns zero and negative quantities into 1

Adding an item with `qty` 0 or negative, or updating an item to 0, answers 200 and leaves one unit in the cart. GraphQL rejects the same input with *The product quantity should be greater than 0*. **Root cause:** `Magento\Quote\Model\Quote\Item::_prepareQty()` replaces any non-positive quantity with 1 while the REST payload is deserialised, so the `qty <= 0` check in `CartItemPersister` never sees the original value. A headless client that sends 0 to remove an item keeps one unit instead. The expected behaviour is pinned by strict `xfail` tests in `tests/api/test_cart.py`: they fail today and will turn red as soon as Magento fixes it, prompting the marker's removal.

## To investigate

- **Coupon usage limits without queue consumers.** Usage is counted by a consumer that does not run in this image, so a "one use per customer" limit is probably not enforced. To be confirmed by the coupon tests ([ADR 0005](adr/0005-trigger-cron-and-queue-consumers-explicitly.md)).
