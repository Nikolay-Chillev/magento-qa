// Allure 3 report settings, used by `npx allure generate`.
// No import from "allure": the CLI runs through npx, without a local package.
export default {
  name: "magento-qa",
  output: "./allure-report",
  // CI restores this file from the published report before generating,
  // so trends and flaky-test detection span runs.
  historyPath: "./allure-history/history.jsonl",
  plugins: {
    awesome: {
      options: {
        reportLanguage: "en",
      },
    },
  },
};
