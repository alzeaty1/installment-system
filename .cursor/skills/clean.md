---
name: "Clean"
description: "Simplify and clean up code - KISS/DRY"
---

Clean up the code changes. Follow these principles:

## KISS (Keep It Simple)
- Remove unnecessary complexity
- Short functions, clear logic
- No clever one-liners that sacrifice readability

## DRY (Don't Repeat Yourself)
- Extract repeated patterns into functions/utilities
- Use loops instead of copy-paste
- Use Django template inheritance instead of repeated HTML

## Style
- Remove dead code, commented-out blocks, debug print/log statements
- Add missing type hints
- Python: follow PEP 8
- Django: follow Django best practices
- Ensure consistent naming conventions

## Verification
- Before/after: code should be functionally identical
- Run tests after cleanup to verify nothing broke

## DO NOT:
- Add new features during cleanup
- Refactor working code unnecessarily
- Change behavior, interfaces, or APIs
