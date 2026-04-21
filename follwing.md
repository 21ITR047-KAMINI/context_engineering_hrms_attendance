# FOLLOWING.md

This file tracks operating conventions followed for this repository.

## Development Conventions

1. Keep business logic separated by domain folders (`agents`, `sql`, `rag`, `ui`).
2. Keep UI-specific changes under `ui/` and orchestration changes in `app.py`.
3. Avoid embedding secrets in code; only use `.env` or host secrets.
4. Prefer small, reviewable commits.
5. Add/update documentation whenever behavior changes.

## Commit Message Pattern

Use concise, imperative commit titles:

- `Add ...`
- `Update ...`
- `Fix ...`
- `Refactor ...`

## Quality Checks Before Commit

- Python syntax check:
  ```bash
  python -m py_compile app.py ui/layout.py ui/chat.py ui/styles.py
  ```
- Validate no secret values were committed.
- Verify app starts without import errors.

## PR Checklist

- [ ] Scope and motivation clearly described.
- [ ] Risk and rollback notes included.
- [ ] Validation commands listed.
- [ ] Screenshots provided for major UI changes (when tooling available).
