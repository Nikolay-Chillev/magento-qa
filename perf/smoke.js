// Performance smoke test: a shopper's path through the store with two virtual users
// for one minute, far below the four PHP workers of the container. It watches for
// changes that make key pages or API calls much slower; it is not a load test.
//
//   docker compose run --rm k6
//
// k6 runs in the Magento container's network, so requests go to port 80 inside it
// with the Host header of the store's base URL.

import http from "k6/http";
import { check } from "k6";

const ORIGIN = __ENV.ORIGIN || "http://127.0.0.1";
const HOST = __ENV.STORE_HOST || "127.0.0.1:8080";
const JSON_HEADERS = { Host: HOST, "Content-Type": "application/json" };
const PRODUCT_SKU = "24-MB01"; // Joust Duffle Bag

const PAGES = {
  home: "/",
  category: "/women/tops-women/jackets-women.html",
  search: "/catalogsearch/result/?q=bag",
  product: "/joust-duffle-bag.html",
};
const SEARCH_QUERY = `{ products(search: "bag", pageSize: 12) {
  total_count items { sku name price_range { minimum_price { final_price { value } } } } } }`;

// Limits for the 95th percentile, in milliseconds: about five times what GitHub's
// runners measured in October 2026 (pages ~60, GraphQL search ~180, cart ~120-190).
// Runner noise stays well below them; a real slowdown, such as pages no longer
// served from the full-page cache, does not.
const P95 = {
  home: 300,
  category: 300,
  search: 300,
  product: 300,
  graphql_search: 900,
  create_cart: 600,
  add_to_cart: 900,
};

export const options = {
  scenarios: { shopper: { executor: "constant-vus", vus: 2, duration: "1m" } },
  thresholds: Object.assign(
    { http_req_failed: ["rate<0.01"], checks: ["rate==1"] },
    ...Object.entries(P95).map(([name, ms]) => ({
      [`http_req_duration{name:${name}}`]: [`p(95)<${ms}`],
    })),
  ),
};

// The first request of each kind builds caches; it is tagged "warmup" so it does not
// count towards the thresholds.
export function setup() {
  for (const path of Object.values(PAGES)) {
    http.get(ORIGIN + path, { headers: { Host: HOST }, tags: { name: "warmup" } });
  }
  http.post(`${ORIGIN}/graphql`, JSON.stringify({ query: SEARCH_QUERY }), {
    headers: JSON_HEADERS,
    tags: { name: "warmup" },
  });
}

function page(name) {
  const response = http.get(ORIGIN + PAGES[name], { headers: { Host: HOST }, tags: { name } });
  check(response, { [`${name}: 200`]: (r) => r.status === 200 });
}

export default function () {
  for (const name of Object.keys(PAGES)) {
    page(name);
  }

  const search = http.post(`${ORIGIN}/graphql`, JSON.stringify({ query: SEARCH_QUERY }), {
    headers: JSON_HEADERS,
    tags: { name: "graphql_search" },
  });
  check(search, {
    "graphql_search: products found": (r) =>
      r.status === 200 && r.json("data.products.total_count") > 0,
  });

  const cart = http.post(`${ORIGIN}/rest/V1/guest-carts`, null, {
    headers: JSON_HEADERS,
    tags: { name: "create_cart" },
  });
  check(cart, { "create_cart: 200": (r) => r.status === 200 });
  const cartId = cart.json();
  const item = http.post(
    `${ORIGIN}/rest/V1/guest-carts/${cartId}/items`,
    JSON.stringify({ cartItem: { sku: PRODUCT_SKU, qty: 1, quote_id: cartId } }),
    { headers: JSON_HEADERS, tags: { name: "add_to_cart" } },
  );
  check(item, { "add_to_cart: 200": (r) => r.status === 200 });
}

// A Markdown table for the GitHub job page, and the same on the console.
export function handleSummary(data) {
  const rows = Object.keys(P95).map((name) => {
    const metric = data.metrics[`http_req_duration{name:${name}}`];
    const values = metric ? metric.values : {};
    const passed = metric && metric.thresholds ? Object.values(metric.thresholds).every((t) => t.ok) : false;
    const ms = (value) => (value === undefined ? "-" : `${Math.round(value)} ms`);
    return `| ${name} | ${ms(values.med)} | ${ms(values["p(95)"])} | ${P95[name]} ms | ${passed ? "✅" : "❌"} |`;
  });
  const failed = data.metrics.http_req_failed ? data.metrics.http_req_failed.values.rate : 0;
  const markdown = [
    "### Performance smoke (k6)",
    "",
    "| Request | Median | 95th percentile | Limit | |",
    "|---|---|---|---|---|",
    ...rows,
    "",
    `Failed requests: ${(failed * 100).toFixed(2)} %, iterations: ${data.metrics.iterations.values.count}`,
    "",
  ].join("\n");
  return { stdout: markdown, "summary.md": markdown };
}
