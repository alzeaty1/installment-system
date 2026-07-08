---
name: "TDD"
description: "Test-Driven Development: RED-GREEN-REFACTOR cycle"
---

Follow strict TDD cycle. NO production code without a failing test first.

## RED — Write Failing Test
- Write ONE minimal test for desired behavior
- One behavior per test
- Clear descriptive name
- Use real code, avoid mocks

## Verify RED — Watch It Fail
- Run the specific test
- Confirm it fails because feature is missing (not a typo)
- If test passes immediately, you're testing existing behavior — fix the test

## GREEN — Minimal Code
- Write simplest code to pass the test
- No extra features, no refactoring, no logging
- Cheating is OK: hardcode values, copy-paste, skip edge cases

## Verify GREEN — Watch It Pass
- Run the specific test
- Run ALL tests to check regressions

## REFACTOR — Clean Up
- Remove duplication, improve names, simplify
- Keep tests green throughout
- Don't add new behavior

## TDD Iron Law
```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```
Write code before the test? Delete it and start over.
