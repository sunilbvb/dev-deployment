# Proposals

Designed features that are ready to be built. Each proposal explains the problem, the agreed design, the work broken into tasks with the files to touch, and how to know it is done — so anyone can pick it up.

| # | Proposal | Status | Good first step |
|---|---|---|---|
| [0001](0001-pipelines.md) | Pipelines — chain commands into a saved workflow | Ready to build | Phase 1, task 1.1 (data model + validation) |

## How to work on a proposal

1. Comment on (or open) the GitHub issue for the proposal and say which phase/task you take.
2. Build one phase per pull request; keep the acceptance criteria and tests from the proposal.
3. If the design needs to change, update the proposal in the same PR and explain why.
4. When a proposal is fully built, set its status to *Done* and add the change to [CHANGELOG.md](../../CHANGELOG.md).

## Writing a new proposal

Copy the structure of 0001: **Summary → Problem → Goals / Non-goals → User stories → Design (UI, data, API, execution) → Security → Plan (phases & tasks) → Acceptance criteria → Testing → Open questions.** Keep decisions concrete (field names, endpoints, files). Discuss in an issue first.
