# 0001. Pipelines — chain commands into a saved workflow

- **Status:** Ready to build
- **Owner:** open — anyone can take a phase
- **Related:** auto-release after upload (`jobs._release_auto_chain_configured`), [ADR 0004](../adr/0004-per-request-project.md)

---

## 1. Summary

A **pipeline** is a named, ordered list of steps saved for an app and flavor, e.g.

> **QA Android release** = Pub Get → Build & Upload AAB (QA) → Bump Patch → Full Release

The user runs it with one click and one confirmation. Steps run one after another in the Live Terminal, the run stops at the first failure, and History records one pipeline run with the result of every step.

## 2. Problem

Releasing an app today means clicking 3–5 commands in the right order and waiting in between. People forget a step (uploading without tagging, tagging without pushing) or run them in the wrong order. The only built-in chaining is "Auto-run Release after successful Deploy/Upload" in Configure → Release, which supports exactly one follow-up release action.

## 3. Goals and non-goals

**Goals**

- Define, save, edit, reorder and delete pipelines per app (optionally per flavor).
- Steps are the commands that already exist (build, upload, release, utility).
- Run sequentially, stop on first failure, one confirmation up front.
- Clear progress in the UI and one History entry per run with per-step results.
- Shared with the team through `deploy_config.json`.
- Replace the single-action auto-release with a "pipeline" that does the same.

**Non-goals (first version)**

- Parallel steps, branches/conditions, loops, schedules or triggers on git push.
- Pipelines spanning several apps (each pipeline belongs to one app).
- Retrying individual failed steps automatically.

## 4. User stories

1. *As a developer* I create "QA Android release" for `gyo_business` with four steps and save it.
2. I click **Run pipeline**, see the list of steps and the commands they run, confirm once, and watch each step's log.
3. When step 2 (upload) fails, steps 3–4 do not run; the run is marked failed and shows which step failed.
4. In History I see one entry "QA Android release — failed at step 2/4" and can open each step's log.
5. A teammate pulls the repo and sees the same pipeline (it lives in `deploy_config.json`).
6. *(Phase 3)* I add a custom step `flutter test` before the build; the confirmation shows that exact command.

## 5. Design

### 5.1 UI

**Home screen**

- New command group **Pipelines** above the other groups, one card per pipeline of the selected app (filtered by the selected flavor if the pipeline has one). Card shows name and step count, e.g. "QA Android release · 4 steps".
- Selecting a card shows the steps under *Ready to execute* (numbered list: step name + exact command line) and a **Run pipeline** button.
- Running shows a step list with states: pending · running · ✔ success · ✖ failed · ⊘ skipped. The Live Terminal shows each step under a header line:

  ```text
  ════ Step 2/4 · Build & Upload AAB (QA) ════
  ```

- **Stop** stops the current step and skips the rest (run status `stopped`).

**Configure → new tab "Pipelines"**

- List of the app's pipelines with **New**, **Edit**, **Duplicate**, **Delete**.
- Editor: name, optional flavor, steps. **Add step** opens a picker listing the app's existing command cards (same names as on the home screen). Steps can be reordered (up/down buttons; drag-and-drop optional) and removed.
- Option *Continue on failure* per step (default off) — for steps like "Clean".
- Validation messages inline (see 5.2).

### 5.2 Data model

Stored in `<project>/.dev-dashboard/deploy_config.json` under each app:

```json
{
  "apps": {
    "gyo_business": {
      "pipelines": [
        {
          "id": "qa-android-release",
          "name": "QA Android release",
          "flavor": "qa",
          "steps": [
            { "templateId": "pub_get" },
            { "templateId": "deploy_aab" },
            { "templateId": "release_bump_patch" },
            { "templateId": "release_push" }
          ]
        }
      ]
    }
  }
}
```

| Field | Rule |
|---|---|
| `id` | `[a-z0-9-]+`, unique per app; generated from the name |
| `name` | 1–60 characters |
| `flavor` | optional; one of the app's flavors, or omitted for flavorless apps / "use the selected flavor" |
| `steps` | 1–20 entries |
| `steps[].templateId` | must be a template that exists for this app (`commands.get_commands`) |
| `steps[].continueOnFailure` | optional bool, default `false` |
| `steps[].flavor` | optional override per step (e.g. a release step with `any`) |
| `steps[].command` | *Phase 3 only* — custom shell step, see §6 |

Validation lives in `config.save_deploy_config` (reject unknown templates, bad IDs, too many steps).

### 5.3 API

| Method | Endpoint | Body | Result |
|---|---|---|---|
| GET | `/api/deployment/pipelines?app=` | – | `pipelines[]` with each step resolved to `{templateId, name, command, flavor}` |
| POST | `/api/deployment/pipelines/run` | `{app, pipelineId, flavor?, confirmed?}` | `{runId}` · or `needsConfirmation` with the full list of resolved commands |
| GET | `/api/deployment/pipelines/run?id=` | – | `{status, currentStep, steps: [{name, status, jobId, startedAt, finishedAt}]}` |
| POST | `/api/deployment/pipelines/stop` | `{runId}` | stops the current job, marks the rest skipped |

Saving/editing pipelines uses the existing `deploy-config/save`.

### 5.4 Execution

New module `features/deployment/backend/pipelines.py`:

```text
run_pipeline(app, pipeline_id, flavor, confirmed)
  1. load pipeline, resolve every step to a command card (fail fast if one is missing)
  2. if any step is a production store upload or pushes to git and not confirmed
       → return needsConfirmation + resolved commands (one confirmation for the run)
  3. take the app lock once for the whole run (other jobs for this app get APP_BUSY)
  4. start a run thread with jobs._start_in_context (keeps the request's project)
  5. for each step:
        job = jobs.execute_command(..., confirmed=True, _assume_app_lock_held=True,
                                   chained_parent_id=run_id)
        wait for job end (poll _JOBS or use a threading.Event set by finish_job)
        success → next step
        failure → if continueOnFailure: next step, else mark remaining "skipped", stop
        stop requested → stop job, mark remaining "skipped"
  6. release the lock, write one history entry (type "pipeline") with per-step results
```

Key points:

- **Reuse `execute_command`** for each step so credentials, logging, history excerpts and safety stay identical. It must not release the app lock between steps (existing `_assume_app_lock_held` flag) and must not trigger the old auto-release chain inside a pipeline.
- **Ordering advice** shown in the editor: put git/release steps after uploads, so a failed upload is never tagged.
- **Live Terminal:** the UI polls the run, then polls the current step's job as today; it prints the step header line when the step changes.
- **History entry** (`deployment_history.jsonl`): `{"type": "pipeline", "id": runId, "app", "pipelineId", "name", "status", "failedStep", "steps": [{name, templateId, jobId, status, durationSeconds}], startedAt, finishedAt}`. Step jobs keep their own entries with `chainedJobId = runId`.
- **Run state** lives in memory like jobs (`_PIPELINE_RUNS`), pruned the same way.

### 5.5 Auto-release migration

"Auto-run Release after successful Deploy/Upload" becomes a shortcut that creates a two-step pipeline (upload → release action). Existing settings (`auto_release_on_success`, `auto_release_action`, `auto_release_flavors`) keep working unchanged until Phase 4 converts them; no user action is required.

## 6. Security

- Template steps run only commands the app already offers; nothing new can be executed.
- The confirmation lists every resolved command line of the run, not just the pipeline name.
- **Custom shell steps (Phase 3)** run arbitrary commands, so:
  - they are visibly marked "custom" in the editor, the confirmation and the log;
  - every run that contains one requires confirmation, even without production uploads;
  - commands are stored as a single string, executed with `bash -c` in the app folder, never interpolated with user input at run time;
  - `deploy_config.json` may be committed by a team — reviewers must treat changes to custom steps like code changes (note this in the README).
- The pipeline API needs the same `X-API-Token` and `X-Workspace` handling as `/execute`.

## 7. Plan

Each phase is one pull request.

### Phase 1 — Backend (no UI)

- [ ] **1.1** Pipeline schema validation in `config.save_deploy_config` (fields and rules from §5.2). Tests: valid pipeline saved; unknown template, duplicate id, >20 steps rejected.
- [ ] **1.2** `pipelines.py`: resolve steps (`get_commands`), confirmation decision (reuse `commands._is_prod_store_deploy` + "contains `release_push`/`release_verify`").
- [ ] **1.3** Run engine (§5.4) with one app lock, stop handling, `continueOnFailure`, no auto-release inside runs.
- [ ] **1.4** Endpoints in `server.py` + exports in `router.py` (§5.3).
- [ ] **1.5** History entry of type `pipeline`; `get_deployment_history` returns it.
- [ ] **1.6** Tests in `tests/test_deployment.py`: happy path with three fast steps; failure stops later steps; continue-on-failure; stop mid-run; history entry; run keeps its project when another `X-Workspace` is active (use `set_request_workspace`). Use test templates with quick commands (e.g. `true`, `false`).

### Phase 2 — UI

- [ ] **2.1** Home screen: **Pipelines** group, card selection, step list in *Ready to execute*, **Run pipeline** with one confirmation dialog listing the commands (`app.js`, `index.html`, `styles.css`).
- [ ] **2.2** Run progress: per-step states, step header lines in the Live Terminal, Stop.
- [ ] **2.3** History: pipeline rows with expandable steps.
- [ ] **2.4** Configure → **Pipelines** tab: list, editor with step picker, reorder, delete, validation messages (`setup.js`, `index.html`).
- [ ] **2.5** Browser test on the test workspace (two apps, local bare git remote): create, run, fail, stop.

### Phase 3 — Custom shell steps

- [ ] **3.1** `steps[].command` support in schema, resolution and execution (§6).
- [ ] **3.2** Editor: "Add custom command" with a warning; confirmation always required; "custom" badge in log and history.
- [ ] **3.3** Tests: custom step runs in the app folder; confirmation is enforced.

### Phase 4 — Replace auto-release

- [ ] **4.1** Configure → Release creates/updates a pipeline instead of separate settings; convert existing `auto_release_*` settings once.
- [ ] **4.2** Remove `_trigger_chained_release` once nothing uses it.
- [ ] **4.3** Docs: README (Pipelines section), FAQ, ARCHITECTURE, docs/API.md, CHANGELOG.

## 8. Acceptance criteria

- A pipeline with 4 steps can be created in the UI, saved, reloaded, run, and appears for teammates after they pull.
- One confirmation for a run containing uploads or pushes; the dialog lists all commands.
- A failing step stops the run; later steps are shown as skipped; the run is failed with "failed at step N/M".
- Stop ends the current step and skips the rest.
- One History entry per run with per-step status and links to step logs.
- No other job can run for the app during the run (`APP_BUSY`).
- Switching tabs/projects during a run does not affect it.
- All existing tests pass; new tests from each phase pass.

## 9. Testing

- Unit tests per phase (listed in §7) using fast placeholder commands.
- Manual: the test workspace from CONTRIBUTING (two `flutter create` apps, a package, a local bare git remote as `origin`) — run "Build APK → Bump Patch → Full Release" end to end and check the tag on the bare remote.

## 10. Open questions

1. Should a pipeline be allowed without a flavor on a flavored app (use whatever flavor tab is selected)? *Proposed: yes.*
2. Should release steps inside a pipeline always use the pipeline's flavor for tag suffixes? *Proposed: use the step's `flavor` override if set, else `any` (current release behaviour).*
3. Notifications: one chat card per run instead of per step? *Proposed: per run, in a later PR.*
