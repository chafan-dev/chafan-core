# Contributing

## Prod-first principle

When prod code and the test suite disagree, the default assumption is **prod is the spec, tests are not**.

In practice:

1. **Don't modify prod to fit the test suite.** Follow good practice in prod code. If a test depends on prod doing something it shouldn't (e.g. the test expects a free-coin grant that prod no longer issues), the test is wrong — fix the test, not prod.

2. **A prod change that breaks a test is not automatically a regression.** Analyze before reacting:
   - Does the test exercise behavior the spec actually requires?
   - Or was the test written against the old shape of prod code that no longer exists?

   If the latter, rewrite or delete the test. Old tests are not contracts.

This shapes how we land refactors: a refactor PR that rewrites or deletes affected tests is healthy. A refactor PR that leaves prod uglier to keep old tests green is not.
