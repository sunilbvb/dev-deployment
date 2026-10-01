# 0003. App IDs are folder names

- Status: Accepted
- Date: 2026-10-01

## Context

Settings, commands, credentials, history, locks and release tags are all keyed by an app ID. IDs were first derived from the `name:` in `pubspec.yaml` (e.g. `tyrios_pim_mobile_app`). Package names are long and get renamed; when one changed, every saved setting stopped matching.

## Decision

The app ID is the folder name, normalised to `[a-z0-9_-]` (`apps/pim` → `pim`). The `pubspec.yaml` name is only the default display name. When two apps share a folder name, the parent folder is appended (`core_packages`).

## Consequences

- IDs are short, readable and stable, and match how people talk about their apps.
- Renaming the folder of an app is a breaking change for its saved settings (rare, and visible).
- Release tags use the release tool's own target name (`<app>-v<version>`), unaffected by this decision.
