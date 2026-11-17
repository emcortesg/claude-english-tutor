# Learner memory: the learner's Claude project

This is a self-study course: one learner, one Claude project. Everything the tutor remembers between classes lives in that project, written with the **Projects** tool. All file names and contents are in English.

## Structure (paths inside the project)

```
english-course/
  state/profile.json  progress.json  attempts.json  resources.json  vocabulary.json  errors.json  preferences.json
  state/placement.json                 (only during placement and its reinforcement)
  notes/YYYY-MM-DD_<event>.md
  notes/unit-<unit>.md                 (summary of a finished unit; written before its session notes move to the archive)
  voice-sessions/S0001/brief.json  report.json   (the last 6 sessions; older ones move to the Drive archive)
  partial-evidence/EXIT-A1.json        (only when a level exit is split over 2 sessions)
```

Locally, `STATE` mirrors `english-course/state/` (plus `notes/` and `voice-sessions/` when you need them). Computed data (progress, attempts, resources, vocabulary, errors, preferences, placement) come **only** from `engine.py`; never edit them by hand.

## No project attached

If the Projects tool is not available, or `project_info` fails, the session has no project:

1. Tell the learner, in simple English with one Spanish sentence: *create a project in Claude called "English course" and always start your English class from inside that project.* Their memory will then be kept automatically.
2. If they cannot or do not want to: use the **backup file**. At the end of every session run `engine.py export --state STATE --out english-course-backup.json` and send it with SendUserFile; ask them to keep it and attach it at the start of the next class. At the start: `engine.py import --file <attached backup> --state STATE`.

## Reading (project → STATE)

1. `project_info` → list of docs. Take the paths under `english-course/`.
2. `project_read` each state file, the last 3 notes (sorted by name: they start with the date) and, when needed, briefs/reports. Small files come back inline; large ones as a local path. Save each one under `STATE` with the same relative path (`state/progress.json` → `STATE/progress.json`, `notes/…` → `STATE/notes/…`).
3. No `english-course/state/profile.json` → new learner (see below).

## Writing (STATE → project)

1. `project_write` with `path` = `english-course/state/<file>` (or `notes/…`, `voice-sessions/…`) and `local_path` = the local file. Writing an existing path replaces it.
2. Save in the order the engine gives (`progress.json` last). Never end a session with a state file not saved.
3. Temporary files (`placement.json` after reinforcement, `partial-evidence/…` after the exit is scored): `project_delete`.
4. Notes are new files (never replaced).

## Archive (keeping the project small)

A course has hundreds of sessions, and every doc in the project is listed at each session start. Old voice sessions and old session notes move to the learner's Google Drive; the state files, the last 6 voice sessions, the last 3 notes and the notes of the current unit always stay in the project.

Do this at the end of a session, **only** when the Google Drive connector is available and the learner's Drive has the voice folder (`config.json` › `voice_drive_folder`, the same one used for the conversations: `references/voice-delivery.md`). Without it, skip this section: nothing is moved and nothing is deleted.

1. Write the paths of the project docs (from `project_info`) as a JSON list in `docs.json` and run `engine.py archive-plan --state STATE --docs docs.json`.
2. `summaries_needed`: for each unit, read its notes and write `notes/unit-<unit>.md` in the project (max. 15 lines, in English: what the learner can do now, errors that keep coming back with examples, interests, what worked). Do this before moving the notes.
3. `archive` (at most 20 docs per session; the rest wait for the next one): for each doc, `project_read` it, save it in Drive in the subfolder `archive` of the voice folder (create that folder the first time) with `create_file` — `title` = its `drive_name`, the content unchanged, as plain text. **Only after Drive confirms the file**, `project_delete` the doc. If a Drive call fails, stop and leave the rest in the project.
4. To look at an archived session later (e.g. a learner asks about an old conversation): `search_files` in `archive` by its `drive_name`.

## New learner

1. Ask the learner's first name.
2. `engine.py init --state STATE --student student-0001 --name "Name"` and save the files it lists.
3. Ask for consent (SKILL.md › Session start) and save `profile.json`.
4. Tell the learner once, in simple English with one Spanish sentence, that the course works best with the **Claude Sonnet** model, chosen in the app's model menu (Opus also works but uses more of their plan; Haiku is not recommended for the tutor).
5. Today's session is the placement test (`references/flows.md` › Placement).
