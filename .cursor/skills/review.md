---
name: "Review"
description: "Security-focused code review before commit"
---

Perform a code review with these checks:

## Security (Priority 1)
- Hardcoded secrets, API keys, passwords?
- SQL injection risks (use parameterized queries)?
- XSS in templates (use `|safe` only when needed)?
- CSRF protection enabled?
- Authentication bypasses?
- Django: `DEBUG=True` in production?

## Django-Specific
- Use `get_object_or_404` instead of `try/except DoesNotExist`
- Use `@login_required` or `LoginRequiredMixin`
- Use `QuerySet` lazy evaluation correctly
- Avoid N+1 queries (use `select_related`, `prefetch_related`)
- Use Django forms for validation, not manual parsing
- Use `{% url %}` tag, not hardcoded paths

## Quality
- Clear function/variable names?
- Functions do one thing (single responsibility)?
- Error handling with meaningful messages?
- Type hints for function signatures?
- Tests exist for new/changed code?
- No dead code or commented-out code
