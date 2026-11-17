# English course (A1–C1)

A free self-study English course for Spanish-speaking adults. Claude is the tutor: it teaches one lesson at a time in chat, follows a validated A1–C1 curriculum (410 lessons, v3.1), and keeps the learner's progress in their own Claude project.

## What the learner needs

1. **A Claude project called "English course".** Always start the class from inside that project: the tutor saves the learner's progress there. Without a project, the tutor gives a backup file at the end of each class to attach next time.
2. **Optional, for spoken practice:** a free Gemini API key from aistudio.google.com/apikey. The conversations run on a web page (the tutor gives its address); it works in Chrome or Edge on a computer and in Safari on iPhone/iPad (iOS 16.4 or later). The key is pasted only in that page, never in the chat. Without a key, conversations run in text mode.
3. **Optional, recommended with the voice page:** Google Drive. With the Google Drive connector in Claude and a small script the learner installs once in their own Google account (`skills/english-tutor/voice-page/drive-bridge.gs`; the tutor guides the steps), the tutor sends each conversation through Drive and reads its report from there: one link to tap, nothing to paste or attach, on any device. Drive is also where old voice sessions are archived, so the project stays small.

## How to start

Inside the project, say: **"Start my English class"** (or "Quiero empezar mi clase de inglés"). The first session is a placement test (about 60 min; it can be finished in a second session); after that, every session continues where the learner stopped.

## Recommended model

Use **Claude Sonnet** for the class (choose it in the app's model menu). Opus also works but uses more of your plan; Haiku is not recommended for the tutor.

## What is inside

- `skills/english-tutor/` — the tutor: instructions, curriculum data, scoring engine, contracts, the voice page and the Drive bridge script.
- `agents/evaluator.md` — gives the rubric bands for Writing and Speaking in lessons, reviews, level exits and placement (Sonnet, medium effort, read-only).
- `agents/item-checker.md` — judges open answers in listening checks and placement probes (Haiku, low effort, read-only). Closed items need no agent: the engine counts them.
- `CHANGELOG.md` — what changed in each version.

How a score is made: the engine (`scripts/engine.py`) counts every item from its key and the learner's answer, the evaluator gives one band per rubric row, and the engine alone decides pass, retest or repetition.

The scoring agents load in Cowork. In other apps the tutor runs the same instructions in a general subagent with the same model.

## Notes for the owner

- Public version: the dictionary example sentences, phonetics and audio links from the Oxford Learner's Dictionaries are not included in `data/vocabulary.csv`; each word keeps its `Dictionary URL` to look it up there.
- Listening checks use public VOA Learning English and ELLLO recordings (links only; nothing is bundled).
- The voice page is published from `web/index.html` (a copy of `skills/english-tutor/voice-page/index.html`) at the address in `config.json` › `voice_page_url`. To publish a new version of the plugin: `python3 plugin/build.py` (runs the tests, copies the page, checks the versions and writes `plugin/english-course.plugin`).
