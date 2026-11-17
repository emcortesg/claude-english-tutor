# Changelog — english-course plugin

## 0.17.2 — 2026-11-13 (voice page v42)
- Exam S0029 ended after 6 of 8 learner turns: Gemini read TWO_TURNS_LEFT as "finish now" and said "That's all for today", and the page accepted its own goodbye. Now the page does not accept a goodbye before the target turns: it sends NOT_FINISHED and Gemini asks one more question (at most twice; practice too). TWO_TURNS_LEFT now says plainly that the conversation is not over and that only FINISH_NOW ends it.

## 0.17.1 — 2026-11-11 (voice page v41)
- Most pictures are drawings (owner decision): voice.md › Pictures puts `drawing` first, drawn templates second, and the `board` of notes last; a board needs `notes_reason` (why drawing it would be very complex), or `picture.py` rejects it.

## 0.17.0 — 2026-11-11 (voice page v41)
- Pictures: new `drawing` form in `scripts/picture.py`. The tutor draws any picture itself in simple SVG (a map, a floor plan, a street, a scene, objects on a table) with a required `description`; the templates stay for photos of people, homes, timetables, menus, icons and notes. Drawings are checked: only basic shapes and text, no scripts, images or links, key words only (same rule as the templates).
- voice.md › Pictures: when to use a template and when to draw; never turn a map or a place into a board of notes.

## 0.16.0 — 2026-11-11 (voice page v41, Drive bridge version 2)

From the audit of 0.15.0 (project doc `claude/auditoria-plugin-0.15.0.md`).

Scoring
- The engine counts every item itself from `key` and `learner_answer` (closed items: exact match; open items: exact match or the scoring agent's verdict in `item_results`). What an agent reports as totals is ignored.
- New `engine.py mark`: counts a package and says which scoring agent it needs. Listening checks and placement probes with closed items need none.
- Writing and Speaking need one band per rubric row of the level; a bare `score_pct` is rejected. Pronunciation may be missing only in text mode (`speaking.channel`).
- The package level must be the level of the event; a key that is not one of its options is rejected.
- `score` refuses a level exit whose lessons are still to be repeated, a listening check before its listening session, and a package that was already scored.
- State files are validated before any is written (a failed command leaves the state untouched).
- Agents: `evaluator` and `item-checker` prompts show the exact JSON; `item-checker` only judges open items.

Placement
- Probes are counted from the evidence (`engine.py placement --evidence`), with the minimum number of items of the specification.
- Short Speaking: `event_id` `PLACEMENT` → 6 learner turns, max. 6 min, text of 60–100 words. The test may continue in a second session.

Voice page and Google Drive
- The tutor's link ends in the session number (`drive_link`, `…#S0022`): the page asks the bridge for that conversation. The tutor no longer moves or trashes files in the learner's Drive.
- Bridge version 2: `action=get&id=…`; `next` picks the newest file by date, not the highest number. An old bridge keeps working (the page never opens a different conversation by mistake).
- Page: folder and file names are escaped before they are shown.

Learner memory
- New `engine.py practice-log`: errors of the practice (voice report, guided practice) and failed words reach `errors.json` and `vocabulary.json`.
- New `engine.py archive-plan` and `storage.md` › Archive: the project keeps the last 6 voice sessions and the notes of the current unit; older ones move to the Drive `archive` folder, with a summary note per unit. Without Drive nothing moves.
- Preferences: the keyword list is gone; the tutor states what a suggestion affects (`--affects formative|assessment|content`) and only `formative` is stored.

Other
- `curriculum.py policy [P06]` and `curriculum.py subpoints 4.1`.
- Dates use the timezone of `config.json`.
- `voice.md` split in two: `voice.md` (writing the conversation) and `voice-delivery.md` (running it), with a table of the delivery ways. README and SKILL.md updated; Spanish triggers in the skill description.
- `plugin/build.py`: tests, page copy, version checks and package in one command.

## 0.15.0 — 2026-11-05 (voice page v40)
- Gemini voice chosen by `character_gender` (required in the brief).

## 0.14.1 — 2026-11-05
- Drive is checked first; the page is never copied when `voice_page_url` is set.

## 0.14.0 — 2026-11-05 (voice page v39)
- Direct corrections in practice ("We say: …"); unclear learner questions; invitation to ask only once; A1 practice 18 turns / 14 min.

## 0.13.0 — 2026-11-05 (voice page v38)
- Every voice session is text + conversation; text lengths and turns per level; rules I1–I4.

## 0.12.0 — 2026-11-05 (voice page v37)
- Practice rules D–H (no grammar names, opinions, learner-question objective, closing line).
