# 0002. Keys are stored per user outside the project

- Status: Accepted
- Date: 2026-10-01

## Context

Uploads need a Google Play service-account JSON and an App Store Connect `.p8` key. Earlier versions stored the `.p8` contents (base64) in `<project>/.dev-dashboard/deploy_config.json`, and many teams keep keys in a `private_keys/` folder inside the repository. Some teams commit `.dev-dashboard/`, so a key could end up in git history, where it cannot be removed safely.

## Decision

- Imported keys are copied to private user folders with `chmod 600`: Play keys to `~/.config/dev-deployment/keys/`, `.p8` keys to `~/.appstoreconnect/private_keys/` (Apple's standard location).
- Which key belongs to which app is stored in `~/.config/dev-deployment/credentials.json`, keyed by project path, with an app scope and a workspace-wide scope.
- Project files keep identifiers and paths only (bundle IDs, Firebase file paths, Issuer ID).
- Jobs receive keys as environment variables (`SERVICE_ACCOUNT_JSON`, `APPLE_API_KEY`, `APPLE_API_ISSUER`, `APPLE_API_KEY_PATH`).
- APIs never return key contents. Inline `.p8` data found in old configs is migrated out on startup.
- Existing conventional locations (`private_keys/play-store-deployer.json`, `env/<flavor>.json`) remain fallbacks.

## Consequences

- Committing `.dev-dashboard/` is safe.
- Each teammate imports their own keys once; keys are not shared through the repo.
- Scripts must prefer the environment variables over their own lookups (they do).
