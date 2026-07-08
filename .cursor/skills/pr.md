---
name: "PR"
description: "Create a proper GitHub Pull Request"
---

## Steps:
1. Ensure you're on a clean `master`/`main` branch
2. Create a feature branch: `git checkout -b feat/description` or `fix/description`
3. Make changes (commit with conventional commits)
4. Push: `git push -u origin HEAD`
5. Create PR via `gh`:
```
gh pr create --title "type: description" --body "## Summary\nWhat changed\n\n## Test Plan\n- [ ] Tests pass"
```

## Branch naming:
- `feat/` — new features
- `fix/` — bug fixes
- `refactor/` — code restructuring
- `docs/` — documentation

## Commit format:
```
type(scope): short description

Longer explanation if needed.
```
Types: feat, fix, refactor, docs, test, ci, chore

## After PR:
- Monitor CI status with `gh pr checks`
- If CI fails, fix and push again
- Merge with `gh pr merge --squash --delete-branch`
