# 0002. After-build power action — turn the screen off (or sleep) when a long job finishes

- **Status:** Ready to build
- **Owner:** open — anyone can take a phase
- **Related:** `jobs._start_in_context`, job finish handling in `backend/jobs.py`, [ADR 0004](../adr/0004-per-request-project.md)

---

## 1. Summary

Release builds take 15–30 minutes (the last prod iOS run profiled at 1757 s). People start one and walk away, but the laptop screen stays on until someone comes back. This proposal adds an opt-in **"When finished"** choice for a job: do nothing (default), **turn the screen off**, or **put the Mac to sleep**. A short countdown lets the user cancel it.

## 2. Problem

- The screen stays lit for the whole run and after it, wasting battery and showing the app/console to anyone nearby.
- The opposite problem is just as real: if the Mac sleeps *during* a build, the build stalls or a store upload hangs. Users avoid this by disabling sleep globally and then forget to restore it.

## 3. Goals and non-goals

**Goals**

- Per-run, opt-in "When finished: Nothing / Screen off / Sleep".
- Keep the Mac awake **while a job runs**, release the hold when it ends (no global setting changes).
- Run the action after the job reaches a final state (success, error or stopped), with a visible countdown that can be cancelled.
- Everything shown in the Live Terminal and History, per the "visible operations" rule.

**Non-goals (first version)**

- **Shutdown or restart.** These need elevated rights, kill the user's other work, and cannot be undone. Not offered.
- Windows/Linux support (macOS only; the option is hidden elsewhere).
- Running it for jobs started from another browser tab's workspace (see §6).

## 4. User stories

1. *As a developer* I tick "Turn screen off when finished" before a deploy, leave, and the screen goes dark after the job ends.
2. *As a developer* the Mac does not fall asleep halfway through a 30-minute build.
3. *As a developer* I return during the countdown and click Cancel, so my screen stays on.

## 5. Design

### 5.1 Actions (fixed list, never free text)

| Choice | Command run by the backend (macOS) |
|---|---|
| `none` (default) | — |
| `screen_off` | `pmset displaysleepnow` |
| `sleep` | `pmset sleepnow` |

Both commands run without `sudo`. The backend maps the choice to the command through a fixed table; command text from a request is never executed (CLAUDE.md rule 4).

### 5.2 Keep awake during the job

When a job starts, spawn `caffeinate -i -w <job pid>` (idle-sleep prevention that ends by itself when the build process exits). Log: `☕ Keeping the Mac awake while this job runs`. Failure to start it is logged and ignored.

### 5.3 Execution

1. The run request may include `after_finish: "none" | "screen_off" | "sleep"` (validated against the table; unknown value → 400).
2. On the job's final state, if the choice is not `none`: log `🌙 Screen turns off in 60 s — Cancel to stop`, wait, then run the command and log it.
3. A new endpoint cancels the pending action: `POST /api/jobs/<id>/cancel-after-finish`.
4. If a new job starts in the same window, the pending action is cancelled automatically.
5. Use `jobs._start_in_context(...)` for the countdown thread (CLAUDE.md rule 2).

### 5.4 UI

- In the run-confirmation dialog: a "When finished" select with the three choices; remember the last choice with `try/catch`-wrapped `localStorage`.
- During the countdown the Live Terminal header shows a banner with **Cancel**.
- History records the chosen action and whether it ran or was cancelled.
- Use `developer-dashboard-ui` classes; local CSS goes in `frontend/styles.css`.

### 5.5 Config

`deploy_config.json` (optional): `"after_finish_default": "none"` and `"after_finish_delay_seconds": 60`. Not secret; per project.

## 6. Security

- Fixed command table, no request-supplied commands, no `sudo`.
- Only the job's own tab/workspace can schedule or cancel its action (per-request project).
- The action runs on the machine hosting the console, so the endpoint stays behind the existing auth/loopback checks.
- Shutdown/restart are deliberately excluded.

## 7. Plan

**Phase 1 — backend**

- 1.1 Action table + validation of `after_finish` in the run request (`commands.py` / `server.py`).
- 1.2 Keep-awake wrapper (`caffeinate -i -w`) started with the job; stopped on exit.
- 1.3 Post-job countdown + action in `jobs.py`; cancel endpoint; auto-cancel when a new job starts.
- 1.4 History fields: `after_finish`, `after_finish_result` (`ran` / `cancelled` / `failed`).

**Phase 2 — UI**

- 2.1 "When finished" select in the confirm dialog + remembered choice.
- 2.2 Countdown banner with Cancel.
- 2.3 Hide the option when the host is not macOS (expose `power_actions_supported` in the status API).

**Phase 3 — docs**

- 3.1 README, FAQ, `docs/API.md` (new field and endpoint), `ARCHITECTURE.md`, CHANGELOG under *Unreleased*.

## 8. Acceptance criteria

- With `none` nothing changes from today.
- With `screen_off` the display sleeps after the countdown once the job ends, on success and on failure.
- Cancel during the countdown prevents the action; the log says so.
- A build longer than the system idle-sleep time is not interrupted by sleep.
- An unknown `after_finish` value is rejected; no request text is ever executed.
- On non-macOS hosts the option is hidden and the field is ignored with a log line.

## 9. Testing

- Unit: validation of `after_finish`; the action table maps only known keys; cancel before/after the delay; auto-cancel when a new job starts (patch the command runner, never call `pmset`).
- Unit: keep-awake wrapper starts and stops (patch `subprocess`).
- UI: verify the dialog, countdown and Cancel in a browser.
- Never call real `pmset` in tests.

## 10. Open questions

- Default delay: 60 s, or shorter?
- Should "Sleep" also be allowed when a stop is requested, or only on natural completion?
- Add a "lock screen" choice (`pmset displaysleepnow` plus the system "require password" setting) for shared offices?
