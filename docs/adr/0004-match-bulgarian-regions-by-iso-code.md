# 0004. Match Bulgarian regions by ISO 3166-2 code

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

Magento requires a region for Bulgarian addresses and knows the 28 oblasts by ISO 3166-2 code and English name only (`BG-22` "Sofia City", region id 661). The test data generator [bg-test-data](https://github.com/Nikolay-Chillev/bg-test-data) produced Bulgarian names only ("София-град").

Matching by name would need a hand-written translation table and breaks on details: "София" is Sofia **Province** (`BG-23`), while the capital is the separate oblast "София-град" (`BG-22`).

## Decision

Match regions by ISO 3166-2 code:

1. bg-test-data 0.2.0 adds `oblast_code` to every generated address (contributed for this project).
2. The suite reads Magento's regions once per session from the anonymous directory API (`/rest/V1/directory/countries/BG`) and maps code → region id.
3. The address factory sets `region_id` and `region_code` from that map.

## Consequences

- No translation table to maintain; the code is the shared key between the two systems.
- If Magento's region ids differ between stores, the suite still works, because ids are looked up at runtime.
- The suite depends on `bg-test-data>=0.2.0`.
