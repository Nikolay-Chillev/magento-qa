# Findings

Defects and risks found while testing the store and its environment. Each finding is a GitHub issue labelled [`finding`](https://github.com/Nikolay-Chillev/magento-qa/issues?q=label%3Afinding) with steps to reproduce; this page is the summary.

**Source** separates what Magento itself does (*product*) from how this Docker image is configured (*environment*), from how the store is set up (*configuration*) and from the sample catalog (*test data*). Environment findings would be configuration tickets on a real project, not Magento bugs, but they are exactly what a pre-production review should catch.

| # | Finding | Severity | Source | Status |
|---|---|---|---|---|
| [#14](https://github.com/Nikolay-Chillev/magento-qa/issues/14) | Every response allows cross-origin access from any site | Major | Environment | Closed: by design in the test image |
| [#15](https://github.com/Nikolay-Chillev/magento-qa/issues/15) | API error responses expose stack traces | Major | Environment | Closed: accepted for a test environment |
| [#16](https://github.com/Nikolay-Chillev/magento-qa/issues/16) | `/health_check.php` returns 500 while the store is healthy | Major | Environment + product | Closed: known Magento bug, [fixed upstream](https://github.com/magento/magento2/issues/40876) |
| [#17](https://github.com/Nikolay-Chillev/magento-qa/issues/17) | Server header discloses the nginx version and OS | Minor | Environment | Closed: accepted for a test environment |
| [#18](https://github.com/Nikolay-Chillev/magento-qa/issues/18) | Elasticsearch crashes on the first start of a fresh container | Minor | Environment | Fixed upstream |
| [#19](https://github.com/Nikolay-Chillev/magento-qa/issues/19) | Missing oblast is only rejected when the order is placed | Minor | Product | Open, covered by a test |
| [#20](https://github.com/Nikolay-Chillev/magento-qa/issues/20) | Product names in API responses contain HTML entities | Minor | Test data | Open |
| [#29](https://github.com/Nikolay-Chillev/magento-qa/issues/29) | REST cart API turns zero and negative quantities into 1 | Major | Product | Open, reported as [magento/magento2#41429](https://github.com/magento/magento2/issues/41429) |
| [#34](https://github.com/Nikolay-Chillev/magento-qa/issues/34) | Free-shipping promotion is applied but Flat Rate still charges shipping | Major | Product | Open, reported as [magento/magento2#41431](https://github.com/magento/magento2/issues/41431) |
| [#35](https://github.com/Nikolay-Chillev/magento-qa/issues/35) | "Buy 3 tees, get the 4th free" gives away any product, not only tees | Major | Configuration | Open, covered by an `xfail` test |
| [#39](https://github.com/Nikolay-Chillev/magento-qa/issues/39) | Five products have no tax class and are sold without VAT | Major | Configuration | Open, covered by an `xfail` audit |
| [#53](https://github.com/Nikolay-Chillev/magento-qa/issues/53) | Signing in before the page finishes loading leaves the header showing a guest | Minor | Product | Open, reported as [magento/magento2#41461](https://github.com/magento/magento2/issues/41461) |
| [#57](https://github.com/Nikolay-Chillev/magento-qa/issues/57) | Password reset requests reveal which emails have an account | Minor | Product | Open, known upstream as [magento/magento2#37886](https://github.com/magento/magento2/issues/37886); the REST case [added there](https://github.com/magento/magento2/issues/37886#issuecomment-6095909420). Covered by an `xfail` test |
| [#58](https://github.com/Nikolay-Chillev/magento-qa/issues/58) | API tokens stay valid after a password reset | Major | Product | Open, covered by an `xfail` test |
| [#59](https://github.com/Nikolay-Chillev/magento-qa/issues/59) | A browser signed in before a password reset gets an error page | Minor | Product | Open, known upstream as [magento/magento2#41439](https://github.com/magento/magento2/issues/41439), covered by an `xfail` test |
| [#65](https://github.com/Nikolay-Chillev/magento-qa/issues/65) | GraphQL calls with a token also sign in a cookie session | Minor | Configuration | Open |

## Details

### #14 Every response allows cross-origin access from any site

**Closed, by design:** CORS is enabled on purpose in magento2-in-a-box (`ENABLE_CORS=true`) so headless frontends can be tested, and the image tests it itself (`tests/cors.spec.ts`). Kept here because it would be a real issue on a production store.


Storefront, REST and GraphQL responses send `Access-Control-Allow-Origin: *` with all methods and headers allowed. On a production store any website could call the store's APIs from a visitor's browser and read the answers. The headers come from the image's nginx configuration. **Recommendation:** no CORS headers, or an allow-list of the store's own frontends.

### #15 API error responses expose stack traces

REST errors include a `trace` field with server paths and class names, because the image runs Magento in developer mode. Acceptable in a test environment and useful for debugging, so it is accepted here; on a production store it is information disclosure. **Recommendation:** production mode on any public environment.

### #16 `/health_check.php` returns 500 while the store is healthy

**Closed, known upstream:** the igbinary serializer is written by Magento 2.4.9's own `setup:install` for the default file cache, which `health_check.php` rejects. Already reported as [magento/magento2#40876](https://github.com/magento/magento2/issues/40876) and fixed by Adobe (AC-17400) after the 2.4.9 release; this analysis reached the same cause independently.


The cache configuration in `app/etc/env.php` defines `backend_options` (igbinary serializer) without a `backend`. Magento falls back to the file cache at runtime, but `pub/health_check.php` treats such a frontend as misconfigured and answers 500. A load balancer or uptime monitor using this endpoint would take a healthy store out of service. **Workaround:** the suite's readiness check uses a GraphQL catalog search instead. **Recommendation:** declare the cache `backend` explicitly.

### #17 Server header discloses the nginx version and OS

`Server: nginx/1.18.0 (Ubuntu)` on every response helps match the server to known vulnerabilities. **Recommendation:** `server_tokens off`.

### #18 Elasticsearch crashes on the first start of a fresh container

A `write.lock` file created when the image was built makes Elasticsearch fail its first start (`AlreadyClosedException`); supervisord restarts it. Search is unavailable for longer after start. The healthcheck waits for a successful catalog search ([ADR 0003](adr/0003-apply-test-configuration-inside-the-container.md)), so tests were never affected, only startup time. **Fixed upstream:** reported with measurements in [magento2-in-a-box#50](https://github.com/controlaltdelete-nl/magento2-in-a-box/pull/50); the maintainer moved the fix to the base image ([magento2-docker-base-images#6](https://github.com/controlaltdelete-nl/magento2-docker-base-images/pull/6)), whose `stop-services` now removes the lock files. With the rebuilt image the store is ready in about 27 seconds instead of 44, without the crash.

### #19 Missing oblast is only rejected when the order is placed

For a Bulgarian address without `region_id`, the shipping-information step succeeds and returns totals; only the order placement fails with `"regionId" is required`. The Luma form prevents this for shoppers, but headless and mobile clients using the API learn about the invalid address one step late. Covered by `test_address_without_region_is_rejected`.

### #20 Product names in API responses contain HTML entities

`Minerva LumaTech&trade; V-Tee` instead of `Minerva LumaTech™ V-Tee`, in GraphQL search results and in order items. The Luma theme renders it as HTML, but a client that treats names as text would show `&trade;` literally. A sample-data quality issue rather than a Magento defect.

### #29 REST cart API turns zero and negative quantities into 1

Adding an item with `qty` 0 or negative, or updating an item to 0, answers 200 and leaves one unit in the cart. GraphQL rejects the same input with *The product quantity should be greater than 0*. **Root cause:** `Magento\Quote\Model\Quote\Item::_prepareQty()` replaces any non-positive quantity with 1 while the REST payload is deserialised, so the `qty <= 0` check in `CartItemPersister` never sees the original value. A headless client that sends 0 to remove an item keeps one unit instead. The expected behaviour is pinned by strict `xfail` tests in `tests/api/test_cart.py`: they fail today and will turn red as soon as Magento fixes it, prompting the marker's removal.

### #34 Free-shipping promotion is applied but Flat Rate still charges shipping

*Spend $50 or more - shipping is free!* is applied to a €68 cart (`applied_rule_ids = 2`, `free_shipping = 1` on the shipping address), yet Flat Rate charges €10. **Root cause:** the rule grants free shipping *for the shipment*, which flags the address; `Flatrate::getFreeBoxesCount()` only counts items whose own free-shipping flag is set, while `Tablerate` also reads the address flag. Flat Rate is the only method for Bulgaria, so the advertised promotion never reaches Bulgarian shoppers.

### #35 "Buy 3 tees, get the 4th free" gives away any product, not only tees

The rule's condition requires a tee in the cart, but its action applies to all items: one €22 tee plus four €34 bags gets a bag for free. Four bags without a tee get nothing, which confirms the tee only unlocks the discount. **Recommendation:** restrict the action ("Apply to") to the Tees categories, as the rule's name promises. A configuration mistake rather than a Magento defect, and a classic way promotions leak revenue.

### #39 Five products have no tax class and are sold without VAT

With the 20% Bulgarian VAT rule in place, a Radiant Tee is charged €4.40 VAT on €22, but a Joust Duffle Bag is charged nothing: `24-MB01`, `24-UG06`, `24-WG081-gray`, `24-WG085` and `24-WG085_Group` have no tax class at all, so no tax rule can match them. On a live store this under-collects VAT. Found through the admin API (`tax_class_id` is null) and pinned by a catalog audit test; the VAT tests use a taxable product.

### #53 Signing in before the page finishes loading leaves the header showing a guest

A customer who sends the sign-in form before the page's scripts have loaded is signed in, but the header keeps "Default welcome msg!" and an empty mini-cart on every page, even when their cart has items. **Root cause:** Luma refreshes the customer data only when its script sees the form being submitted (`customer-data.js` marks the affected sections as stale in the `section_data_ids` cookie). Without that mark, the next page finds nothing to reload, and the data never expires on its own. Reproduced 12 out of 12 times when the form is sent right after `DOMContentLoaded`. In production mode the window is shorter, but a password manager filling the form on a slow mobile connection can still hit it. The UI tests wait for Luma's scripts before they interact with a page; before that, the sign-in tests failed intermittently with three parallel workers. Reported upstream with a suggested fix: set the `section_data_clean` cookie on a successful sign-in, as the store switcher already does.

### #57 Password reset requests reveal which emails have an account

`PUT /V1/customers/password` answers `200 true` for a registered email and `404 No such entity with email = …` for an unknown one; the GraphQL mutation `requestPasswordResetEmail` answers `true` or "Cannot reset the customer's password". Magento hides account existence everywhere else (one message for every failed sign-in, `isEmailAvailable` always `true` by default, a neutral message on the "Forgot Your Password?" form), so these two endpoints are the gap that lets anyone check a list of emails for accounts. The GraphQL side is reported upstream as a feature request; the REST case, which has the same cause, is added to that report.

### #58 API tokens stay valid after a password reset

A password reset, or a password change while signed in, ends the customer's browser sessions (`SessionCleaner::clearFor`) but not their API tokens: those are revoked only when the customer is deactivated or deleted. A token stolen before the reset keeps working until it expires (one hour by default). **Recommendation:** revoke the customer's tokens wherever the sessions are cleared.

### #59 A browser signed in before a password reset gets an error page

The next request from a browser that was signed in before the reset fails with HTTP 500 (`SessionException: The session has expired, please login again.`) instead of redirecting to the sign-in page; the request after that works. Thrown by `CutoffValidator` while the session starts. Reported upstream with a fix proposed in [magento/magento2#41440](https://github.com/magento/magento2/pull/41440). The cutoff is compared in whole seconds, so a session from the same second as the reset survives it; the test waits for the next second before resetting.

### #65 GraphQL calls with a token also sign in a cookie session

A GraphQL request with a customer token returns a `PHPSESSID` cookie whose session is signed in as that customer; later GraphQL requests that send only the cookie act as the customer too. REST does not accept the cookie. Magento keeps GraphQL sessions by default for storefronts that mix Luma pages and GraphQL. **Recommendation:** for a headless storefront that uses tokens only, set `graphql/session/disable` to 1, so the token is the only way in. Noticed when the tests' shared HTTP client started keeping cookies; customer GraphQL clients now have their own cookie jar.

## To investigate

- **Password label on the sign-in page.** In 2.4.9 the label says `for="pass"` while the field's id is `password`, so clicking the label does not focus the field and the field's accessible name comes only from its `title`. Already fixed in Magento's `2.4-develop` branch; the accessibility checks will show whether 2.4.9 needs a note.
- **CAPTCHA field on the sign-in page.** The hidden sign-in pop-up repeats the field's id (`captcha_user_login`), so the visible field's label points to the pop-up's copy and the field has no accessible name. The wrapper also carries `role="user_login"`, which is not an ARIA role. To be confirmed with the accessibility checks.
- **CAPTCHA count per IP address.** Besides three failures per email, Magento asks for a CAPTCHA after 1,000 failures from one IP address, which is meant to catch attacks spread over many emails. Any successful storefront sign-in deletes that IP's count (`Captcha\Model\ResourceModel\Log::deleteUserAttempts`), so an attacker who signs in to an account of their own from time to time keeps the count low. Read in the code, not reproduced: it takes 1,000 failed sign-ins.
- **Filters on category pages.** Each filter title's accessible name ends with a glyph from Luma's icon font, so screen readers may announce an unknown character after "Size" or "Price". The size and colour swatches are links of 0×0 pixels wrapped around the visible swatch, so a keyboard user's focus outline may not show. To be confirmed with the accessibility checks.
- **Discount code section on the cart page.** The "Apply Discount Code" title expands the form, but its open state is only a CSS class: the title has no `aria-expanded` and is not exposed as a button. Screen-reader users may not know the section opened. To be confirmed with the accessibility checks.

## Checked, not a finding

- **GraphQL paging far past the end.** A page after the last one is refused ("currentPage value 3 specified is greater than the 2 page(s) available."), but a page that starts beyond the 10,000th result returns no items and `total_count: 0` instead. That is the search engine's result window (`index.max_result_window`), not something a shopper can reach in this catalog.
- **Another customer's address through the profile.** Saving your profile (`PUT /V1/customers/me`) with another customer's address id is refused and their address stays as it was, but the error says "A customer with the same email address already exists in an associated website.", which points API clients in the wrong direction. Covered by `tests/api/test_access_control.py`.
- **API lockout and the storefront.** After six wrong passwords the REST token endpoint refuses even the right password for 30 minutes, but the same customer can still sign in on the storefront. Each channel has its own protection (lockout for the API, CAPTCHA after three failures on the storefront), so this is by design; covered by `tests/api/test_account_lockout.py` and `tests/ui/test_login_captcha.py`.
- **Coupon usage limits without queue consumers.** The hypothesis was that a single-use coupon could be redeemed repeatedly because usage counting looked asynchronous. Verified on 2.4.9: `times_used` is incremented when the order is placed, a spent coupon is refused, and when two carts hold the same single-use code only one order gets the discount. If the second shopper sets their address after the first order, the spent coupon is dropped from their totals without a message and they pay full price; correct for revenue, but they are not told why the discount disappeared. Covered by `TestCouponUsageLimits` in `tests/api/test_promotions.py`.
