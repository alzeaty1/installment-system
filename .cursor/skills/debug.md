---
name: "Debug"
description: "Systematic 4-phase debugging: root cause analysis before fixing"
---

You are debugging code. Follow these phases STRICTLY:

## Phase 1: Root Cause Investigation
- Read the full error message and stack trace
- Reproduce the issue first
- Check recent git changes
- Trace data flow to find the source of the bad value
- DO NOT propose fixes yet

## Phase 2: Pattern Analysis
- Find working examples in the codebase
- Compare what's different between working and broken
- Identify the pattern

## Phase 3: Hypothesis & Testing
- Form 2-3 falsifiable hypotheses
- Test the most likely one with minimal changes
- One change at a time

## Phase 4: Implementation
- Write a failing test that reproduces the bug (RED)
- Fix the root cause (not the symptom)
- Verify the test passes (GREEN)
- Run full test suite to check regressions

THE RULE OF THREE:
- After 3 failed fix attempts, STOP and question architecture
- Don't attempt fix #4 without discussing architecture first
