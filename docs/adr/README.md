# Architecture Decision Records

Short records of decisions that shape the project — *why* it is built this way. Read them before proposing a change that goes against one; to change a decision, add a new ADR that supersedes it.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-python-standard-library-only.md) | Backend uses the Python standard library only, no database | Accepted |
| [0002](0002-credentials-outside-the-project.md) | Keys are stored per user outside the project | Accepted |
| [0003](0003-folder-names-as-app-ids.md) | App IDs are folder names | Accepted |
| [0004](0004-per-request-project.md) | The project is chosen per request, not globally | Accepted |

## Writing a new ADR

Copy this into `NNNN-short-title.md` (next free number):

```markdown
# NNNN. Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
What problem or force makes a decision necessary?

## Decision
What we do.

## Consequences
What becomes easier, what becomes harder, what we must keep doing.
```
