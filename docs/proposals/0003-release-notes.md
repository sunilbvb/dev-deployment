# 0003. Release notes — optional, multi-language, per build, editable after upload

- **Status:** Mostly built — real-store verification and the follow-ups in §6 are pending
- **Owner:** open — anyone can take a follow-up
- **Related:** `backend/metadata/release_notes.py`, `backend/metadata/notes_updater.py`, `fastlane/Fastfile`, `frontend/modules/dashboard/app_release_notes.js`, [CHANGELOG.md](../../CHANGELOG.md)

---

## 1. Summary

Every deployment used to go out without "What's new" (Google Play) / "What to Test" (TestFlight), because the upload step never sent the notes the tool already stored. Release notes now ship with every upload when they exist, in every language the app supports, and can be added or corrected later from History. Notes are **always optional**: no notes never blocks a build or an upload.

## 2. What is done

| # | Capability | Where |
|---|---|---|
| 1 | Notes are sent with the upload: Play `release_notes` per language, TestFlight `localized_build_info` + `changelog` | `fastlane/Fastfile` (`upload_android`, `testflight_build`) |
| 2 | Never blocks: no notes → one info line, upload continues | `scripts/core/project_resolver.sh` (`exportReleaseNotes`) |
| 3 | Sources, in priority order: Run panel → `RELEASE_NOTES_JSON` → `RELEASE_NOTES` (plain text, first language) → per-build files → shared default files | `metadata/release_notes.py` (`resolve_notes_map`) |
| 4 | Run panel: inline, collapsible, **no confirmation**; autofilled from this build's, the default, or the last build's notes; editable or empty; "Use last build's notes" | `app_release_notes.js`, `index.html` (`#runNotesPanel`) |
| 5 | Notes ride along with `POST /api/deployment/execute` (`releaseNotes`) and reach the scripts as `RELEASE_NOTES_JSON` | `backend/jobs.py`, `backend/server.py` |
| 6 | Per-build files: `changelogs/<build>.txt` (Android), `release_notes_<build>.txt` (iOS); a build's file beats the default | `metadata/store_metadata.py` |
| 7 | Languages per app (`release_locales` in the deploy config); fallbacks: existing metadata folders, then `en-US` | `metadata/release_notes.py` (`get_app_locales`, `set_app_locales`) |
| 8 | Languages from the store listing (Play listings / App Store version localizations) | `list_locales` lanes, `GET /api/deployment/release-notes/store-locales` |
| 9 | History keeps `platform`, `buildNumber`, `version`, `releaseNotes` per run; a success saves the run's notes as that build's files | `backend/jobs.py` |
| 10 | History "Release notes" button: view / add / edit per language; **iOS** can "Save & publish" to the TestFlight build; **Android** is save-only | `app_release_notes.js`, `notes_updater.py`, `update_testflight_notes` lane |
| 11 | Store limits enforced (Play 500, App Store 4000) in the UI counter and on save/send | `store_metadata.METADATA_LIMITS` |

Decisions taken with the owner:

- Notes are **optional** (an earlier "fail without notes" gate was removed).
- Android uploads stay `release_status:completed`; **no draft mode**.
- No extra confirmation when clicking Run because of notes.

## 3. How a run flows

```
Run panel notes ──► /execute {releaseNotes} ──► job env RELEASE_NOTES_JSON
(or files / env)                                      │
                                       exportReleaseNotes (resolves per-language JSON, never fails)
                                                      │
                          fastlane: Play release_notes{locale} / TestFlight localized_build_info
                                                      │
                          job success ─► history entry (platform, buildNumber, releaseNotes)
                                       └► saved as per-build files
Later: History ► "Release notes" ► edit ► Save  (files)  ► Save & publish (iOS: update_testflight_notes lane)
```

## 4. API

See [docs/API.md](../API.md): `GET /api/deployment/release-notes`, `POST …/release-notes/save`, `…/publish`, `…/locales`, `GET …/store-locales`, `GET …/identifier`, `POST …/metadata/update-build`, and `releaseNotes` on `POST /api/deployment/execute`.

## 5. Limits that come from the stores (not fixable here)

- **Google Play** only edits notes of a *draft* release. Ours are `completed`, so Android notes cannot be changed after upload; History saves them for the next upload only.
- **TestFlight** attaches notes only after Apple has processed the build, so uploads *with* notes wait for processing (slower than before). Without notes the upload still returns immediately.
- TestFlight notes are "What to Test". The public App Store "What's New" of a store version is a different field and is not touched.

## 6. Pending / plans

Ordered by value.

1. **Verify against real stores.** The Spaceship/Supply calls (find build, create/update beta localization, list store languages, localized upload) were written from the fastlane API and are covered only by mocked tests. Run each once on a real app and fix any mismatch.
2. **Browser pass of the Run click and History button on a real entry.** The editor, autofill, language add/persist and History save were checked in a browser against a demo app; the full Run request and the History button on a real finished job were not.
3. **Pipelines** have no notes field; they use the saved files only. Add the same inline editor to pipeline runs.
4. **App Store "What's New"** (store version, not TestFlight) — optional extra publish target.
5. **Per-flavor notes and identifiers** (bundle id / package already resolve per flavor; the notes themselves are per app).
6. **Build number for non-Flutter stacks.** History reads the build from `pubspec.yaml`; other stacks need the build number typed in the dialog. Add a stack-aware reader (Gradle `versionCode`, Xcode `CURRENT_PROJECT_VERSION`).
7. **Generate notes into the editor** from conventional commits (the release tool already builds them) and an optional translate step, so German is not typed by hand.
8. **Tech debt:** `store_metadata.get_store_metadata` / `save_store_metadata` / `get_version_info` build `workspace/apps/<id>` instead of `_resolve_app_dir` — breaks the "generic only" rule for non-`apps/` layouts. `release_notes.py` already uses the resolver.
9. **Automated UI test** for the Run panel and History dialog (none exists in the repo).
10. Silent truncation at the store limit during upload (the UI counter turns red; the upload cuts to the limit).

## 7. Security

- Request values never become command text. The iOS update lane is fixed; values travel as environment variables only, after regex validation (bundle id, build number, locale, version token).
- Version tokens are checked (`^[A-Za-z0-9][A-Za-z0-9._+-]{0,39}$`, no `..`) before touching a file name.
- Apple key / Play service account come from `credentials.job_env`; nothing secret is returned by the API.

## 8. Testing

`tests/test_deployment.py`: `TestReleaseNotesForUploads`, `TestPerVersionReleaseNotes`, `TestUpdateTestflightNotes`, `TestMultiLocaleReleaseNotes`. Mocked: the fastlane subprocess and the credentials store. Never uploads to a store.

## 9. Open questions

- Should the Run panel remember the last typed notes per app between sessions (today: saved only after a successful run)?
- Should "Languages from store" also *remove* local languages the store does not have (today it only adds)?
