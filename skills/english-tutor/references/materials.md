# Materials created in class

Everything the learner reads, hears or answers is created from the spec. Before showing it, run the checklist. All materials are in US English.

## Teach before you test

Every item — in practice and in assessment — must be answerable with what the learner has been taught:

- this lesson's grammar (`Grammar focus`) and words (`words`), plus earlier lessons (grammar ceiling, earlier vocabulary);
- high-frequency A1 words the learner certainly knows.

Before using an item, list the words and forms it needs. If one of them was not taught (e.g. *yourself* when only *you* was presented), either teach it first — with an example and one quick practice item — or change the item. Never discover a gap during a test.

## Readings (class and assessment)

- Class: `reading_spec` — text type, situation, `Target length min/max`, target grammar, `Grammar ceiling`, vocabulary to integrate, `Level constraints`, `Comprehension activities`, `Generation QA criteria`.
- Assessment: `Lesson assessment – Reading (unseen)` — a **different** text from the class one, in another situation, same grammar and ceiling, with the items it asks for (gist/detail…).
- US English (*US teaching form* for words with British spelling).

Checklist (all must hold): length within range (count the words with code); only structures within the ceiling; includes the new words the spec asks for; item answers are in the text without ambiguity; plausible distractors; exactly one correct answer per item; every item passes "teach before you test".

## Items

- Each item: unique `item_id` (`<event>-<cycle>-<attempt>-R1`, `-R2`… / `-L1` / `-G1` / `-V1`), `section` (if the event tags sections), `sub_skill` (gist, detail, inference…), `question`, `options` (for multiple choice, true/false, matching), `key`, `accepted_variants`, `learner_answer`.
- **The engine marks the items, not you and not an agent.** An item with `options` is closed: it is correct only when `learner_answer` is exactly the `key`, and the `key` must be one of the `options` (the engine rejects the package otherwise). An item without `options` is open: correct when the answer is exactly the `key` or one of `accepted_variants`, wrong when it is empty; any other answer waits for the scoring agent's verdict (`engine.py mark` lists it). Prefer closed items in listening checks and placement, so no agent is needed.
- Never repeat an `item_id` or a question already used with this learner (`engine.py resource` lists `items_already_used`).
- Vocabulary (placement, exit): give each item the `oxford_id` of the tested word; the engine lists the failed words itself.

## Interactive items (AskUserQuestion)

Use the question tool for closed items — multiple choice, true/false, matching, choosing the correct form — in guided practice and in assessments.

- Up to 4 questions per call; 2–4 options per question; 1–5-word option labels; a neutral one-line description per option (it must not hint at the answer).
- Never mark an option as recommended and never put the key in the question, header or descriptions. Shuffle the position of the correct option.
- In assessments, record each answer exactly as chosen (`learner_answer` = the option label, copied character by character; if the learner typed something else with "Other", record what they typed) and do not give feedback until the engine's decision.
- Open answers (short answers, gap-fills with free text, writing, conversation) stay in chat.

## Writing prompts

From `Lesson assessment – Writing`: text type, reader, new situation, word range, target grammar (number of uses). Write it in English at the learner's level, with the word range visible.

## Resources and IDs

Every formal text, recording or prompt has a stable `resource_id`: `TXT-<event>-R-<situation>`, `PROMPT-<event>-W-<situation>`, `PROMPT-<event>-S-<situation>`, or the listening `Source ID`. Before reusing one: `engine.py resource --id …` (`can_use`). If you reuse one, the questions are new.

A few recordings serve more than one listening check (P06: only when no other suitable recording with audio existed; `Notes` names the other check). Each check has its own Form A items: never copy items from the other check. The recording still counts toward the learner's 3 uses; if `can_use` is false, choose another VOA/ELLLO recording with a published transcript (P14) and note it.

## Feedback in class

- Immediate in guided practice: point out the error, give a hint, let the learner correct it; give the correct form only if they cannot.
- In free production and conversation: take notes and comment at the end (max. 3 points), starting with what went well.
- No unnecessary metalanguage at A1–A2; examples before rules.
