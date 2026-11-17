# Session flows

Before each flow: `curriculum.py lesson <ID>` (or `event <ID>`) and read the whole package, and adapt it to the learner's active preferences (`engine.py prefs`) only where compatible with the spec. Times are a guide (P13): move on when the criteria are met, not when the time is up.

## Lesson (Core, Application, Consolidation)

Core ≈ 90 min, Application/Consolidation ≈ 60 min.

1. **Warm-up (3–5 min).** Recall 2–3 items from the previous lesson or from `vocabulary.priority_recycling` and `errors` (sections with the most errors).
2. **Presentation (Core).** Introduce the grammar in `Grammar focus` inside the `Topic context` situation. Form → meaning → use, with examples that use the new words (`words`). Apply the `Spanish-L1 alert` proactively. Present every word and form the later exercises and the assessment will need (teach before you test). Application: briefly recall the grammar and transfer it to the new situation. Consolidation: no new vocabulary; recall the grammar at control level.
3. **Reading.** Create the text from `reading_spec` (length, type, target grammar, grammar ceiling, vocabulary to integrate, activities). Run its comprehension activities (closed items with AskUserQuestion).
4. **Guided practice.** From `practice_assessment › Guided practice`: controlled items one by one with attempt → feedback → the learner corrects before moving on; then semi-controlled items. Note each error with its grammar section: at the end of the session they go to the learner's memory (`engine.py practice-log --errors`, SKILL.md › Session end).
5. **Pronunciation.** Work on `Pronunciation focus` with 3–5 examples; use the words' `us_audio` links (`curriculum.py words <lesson>`) when helpful.
6. **Independent production.** The `Independent production` task, with no visible model. Feedback at the end.
7. **Practice conversation (text + conversation; about 12–30 min by level).** `references/voice.md` (the brief) and `references/voice-delivery.md` (running it), mode `practice` (brief and report saved to the project). Always a new short text that Gemini reads first, then a conversation only about it (voice.md › Text + conversation; turns per level in voice.md § 1). Comment on 2–3 points of the report; its errors reach the learner's memory with `engine.py practice-log --report` at the end of the session.
8. **Formal assessment (≈15 min Core, ≈10 others).** See § Scoring in SKILL.md. Reading: new text from `Lesson assessment – Reading` (items with AskUserQuestion). Writing: prompt from `Lesson assessment – Writing`. Speaking: voice in `exam` mode from `Speaking exam brief`, also as text + conversation (a new text read first; voice.md › Text + conversation). No help or corrections during the assessment.
9. **Embedded listening check** (if the lesson has one): only **after** the lesson is passed; the engine gives it as `next_event`. If the lesson was not passed, the check waits (§ Listening check).
10. **Result and session end.** If the learner made suggestions during the class, handle them as in SKILL.md § Learner preferences.

## Review: checkpoint (option B, diagnostic first)

`review_plan › Session flow` and `Sections recalled`.

1. **Short diagnostic.** Reading, Writing and Speaking with items tagged by section (≥2 per reviewed section; each Reading item carries its `section`, and `tagged_sections` lists the reviewed ones). Event `review_diagnostic`: the engine counts the sections that have items, the evaluator judges the others from the Writing and Speaking (`sections`). `engine.py score` returns `diagnosed` and `flagged_sections`, stored in `progress.pending` (status `diagnosed`): if the session is interrupted, the next one resumes at step 2.
2. **Reinforcement** of the flagged sections only, with new examples and guided practice from the lessons that introduced them (`curriculum.py lesson-of-section 4.2`). If no section is flagged, go to step 3.
3. **Practice conversation** centred on the flagged sections; include the `Mediation micro-task`.
4. **Formal assessment** (`review_assessment`), new items, also tagged by section.
5. Embedded listening check if there is one (after passing).

## Review: level final review

Guided recall of all the level's sections, a practice conversation and a practice assessment. It does not decide the level pass (P05): score it as `review_assessment`; the engine returns `diagnosed` and always moves on to the level exit (or the embedded check), with no retests. Use its `flagged_sections` to reinforce before the exit and write them in the session note.

## Listening check (`ULC-…`)

1. Package: `curriculum.py event ULC-…` (source, Form A items).
2. `engine.py attempt` and `engine.py resource --id <Source ID>`. Attempt 1: Form A with its source. Retest 1: `Alternative source` with new items. Retest 2: recording A or B again (if uses are left) or another VOA/ELLLO recording with a published transcript; always new items (P14).
3. Give the learner the **`Audio URL`** of the source (never the page `URL`: the page shows the transcript). For a retest with the alternative source, use `Alternative audio URL`. If the cell lists several files separated by `|`, they are played in order. If it starts with `NONE`, the source has no audio: use the other recording (or another VOA/ELLLO recording with a published transcript, P14) and note it. Tell them how many times they may listen (`Plays`); then ask the questions (closed items with AskUserQuestion). Never reveal the key or the transcript.
4. Evidence with `listening` (source_id + items with `options`, `key`, `sub_skill` and the learner's answer). The engine counts `Listening` and its sub-skills itself: `engine.py mark` normally answers `agent: none`, so score with `--evidence` only (an agent is needed only for open answers).

## Level exit (`EXIT-…`)

Four dimensions (P07), from `components`: Reading and Listening in chat, Writing in chat, Speaking by voice in `exam` mode. Forms generated on demand (P15). It can be split over 2 sessions with the same attempt: at the end of the first one, save the questions, keys and answers given so far in `partial-evidence/<EXIT-…>.json` in the project; the next session reads it, completes the package, scores it and deletes that file (`project_delete`). Rubrics `RB-XW/RB-XS` of the level. Give every Reading and Listening item its `section` when it tests one, and every vocabulary item its `oxford_id` (and ask the evaluator for `sections` from the Writing and Speaking), so that, if content must be repeated, the engine knows which lessons. Passing opens the next level.

## Placement (new learner, P16–P17)

About 60 min; it may be finished in a second session (the state is `placement_in_progress` and the loop simply goes on). Repeat this loop until `done`:

1. `engine.py placement --state STATE` → `next_action` (`probe_level`, `writing_speaking` or `probe_unit`) with its `spec`.
2. Create the items for that step (`curriculum.py level <L>` or `unit <U>`; what a section covers: `curriculum.py subpoints <section>`): grammar of the sections, Oxford vocabulary in context, a short reading. All closed items, asked with AskUserQuestion. Use very simple English at the start.
3. Build the evidence package (`event_id` `PLACEMENT`, `event_type` `placement_stage1` or `placement_stage2_probe`, `attempt` 1, `level` = the level probed): blocks `grammar` (each item with its `section`), `vocabulary` (each item with its `oxford_id`) and, for `probe_level`, `reading`; every item with `options`, `key` and the learner's answer.
4. Score the step:
   - `probe_level` / `probe_unit`: `engine.py placement --state STATE --evidence E.json`. The engine counts the items (no scoring agent: `engine.py mark` says so), keeps the failed words and the errors by section, and needs at least the number of items in the `spec`.
   - `writing_speaking`: a short Writing task and a short Speaking (voice: `references/voice.md` › Placement Speaking — 6 learner turns, max. 6 min; or text mode). From B2 the Writing rubric has a Mediation row: make the Writing task relay a short input (a notice, two opinions) for a reader. Launch the evaluator with the exit rubrics of that level, then `engine.py placement --state STATE --scores S.json --evidence E.json` (the evidence carries `speaking.channel`).
   Save `placement.json` (and, at the end, the files it lists).
5. At `done`: explain the level and the start lesson. The **reinforcement session** is the next session (or the same one, if there is time and the learner wants it).

## Post-placement reinforcement (P18, pending `reinforcement`)

Formative, no score: sections and words failed within the credited content (`placement.json`, `vocabulary.priority_recycling`) + REQUIRED prerequisites of the start lesson (`curriculum.py prereqs`). When it ends: `engine.py reinforced --state STATE`, save `progress.json` and delete `placement.json` from the project. The next session starts the start lesson.

## Retest (pending `retest_pending`)

New session. Only the dimensions in `pending.retest_dimensions` (and sections, if any):

1. Targeted reinforcement: re-teach what failed with new examples (check the previous attempt in `attempts.json` and the session note).
2. Short guided practice from the lessons where the content was introduced.
3. Reassessment with an equivalent task: same construct, level, length and format; new items; a text/recording can be reused if `resource` allows it.

## Repetition (pending `repeat_content`)

- Lesson: repeated in full as a new session (new materials). When scored, the engine opens a new cycle of 3 attempts.
- Level exit: the lessons in `pending.repeat_lessons` are repeated in order (each complete and scored); then the exit again. The engine does not accept the exit before they are all passed.
- Listening check (`listening_session`): listening session with the same recordings, new questions and strategy practice (gist → detail). When it ends: `engine.py repeated` and save `progress.json` (pending `repeated`); the engine does not accept a new attempt before that. The new attempt can be in that session or the next one.
- Pending `repeated` (level exit or listening check): the content has been repeated; take the event again (new cycle of 3 attempts).

## Re-placement (P19)

If in the first lessons after placement the learner repeatedly scores ≥95% in every dimension, or repeatedly fails, propose (in English, with one Spanish sentence) moving them to another lesson, with the evidence. Only if they accept: `engine.py replace --state STATE --to L0XX --evidence "<evidence in English>"` and save `progress.json`.
