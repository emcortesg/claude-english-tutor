# Voice conversation: writing it (brief and instructions for Gemini)

Every conversation — practice **and** exam, voice **and** text mode — leaves a `brief.json` and a `report.json` in `english-course/voice-sessions/<session_id>/` in the learner's project (`references/storage.md`). Both are in English.

This file is about **writing** the conversation (§ 1 the brief, § 1b the instructions for Gemini, the text, the pictures, the placement Speaking). **Running** it — how it reaches the voice page, text mode, reading the report and what to do afterwards — is in `references/voice-delivery.md` (§ 2–4).

## 1. Build the brief (`voice_brief/3`)

From the lesson package:

| Field | Practice | Exam |
| --- | --- | --- |
| `mode` | `practice` | `exam` (+ `event_id`, `attempt` from `engine.py attempt`) |
| `visible_to_learner.situation` | 1–2 sentences from `Conversation situation`, in English at the learner's level, phrased as a conversation between two people (if the spec describes a quiz or a drill, turn it into a chat on the same topic) | A **new** situation from `Lesson assessment – Speaking` (not the class role-play) |
| `hidden_objectives` | Objectives from `Conversation purpose` / `Learning outcome` | Same objectives |
| `target_grammar` | `Conversation target grammar` (+ `target_uses` from the expected result) | Same |
| `priority_vocabulary` | `Conversation priority vocabulary` (every word must also appear in `agent_instructions`: the engine checks it) | Only the words that fit the new situation naturally (the evaluator scores vocabulary range on this list): build the situation and the picture so that each one has a place, and tell Gemini which questions make the learner need them |
| `pronunciation_focus` | `Conversation pronunciation focus` | Same |
| `pronunciation_words` | The words that carry the focus (e.g. `["mustn't"]`, `["this", "these"]`) | Same |
| `learner_notes` | Today's errors, interests (from class and notes) | **Empty** (do not condition the exam) |
| `end_condition` | `target_learner_turns` + `max_minutes` from `Conversation end condition` | **By turns** (owner decision 2026-11-05; the engine checks the exact values). Practice: `target_learner_turns` A1 18 · A2 18 · B1 22 · B2 28 · C1 34, safety `max_minutes` A1 14 · A2 16 · B1 20 · B2 25 · C1 30. Exam: turns A1 8 · A2 10 · B1 12 · B2 14 · C1 16, `max_minutes` A1 10 · A2 12 · B1 14 · B2 16 · C1 18. The reading of the text does not count (the clock starts after it). The time in the spec ("2-minute conversation") is indicative only |
| `resource` | — | `{"resource_id": "PROMPT-<lesson>-S-<situation>", "kind": "prompt"}`; check `engine.py resource` |
| `agent_instructions` | Written by you for this lesson (§ 1b) | Written by you for this exam (§ 1b) |
| `character_gender` | `female` or `male`: the gender of the character Gemini plays (its name and role must match). The voice page picks a matching Gemini voice (owner decision 2026-11-05) | Same |

Validate: `engine.py validate --file brief.json --schema voice_brief`.

## 1b. Write the instructions for Gemini (`agent_instructions`)

Gemini receives **exactly** what you write here; the page only adds a fixed technical block (button turns, how the conversation ends, how to write the report). So write it for this lesson and this learner, in English, addressed to Gemini ("You are…"), 250–600 words (max. 6000 characters). Never write the technical block yourself (no SESSION_END, no function names): the engine rejects it.

Always cover, in this order:

1. **Role and setting**: a name, who they are, where and when; who the learner is (adult Spanish speaker, level). In practice, say it is a real, friendly conversation, not a test. In the **exam**, never write "not a test" (it contradicts the assessment rules): just describe the natural situation.
2. **What the learner sees**: quote `visible_to_learner.situation` word for word (the engine checks it).
3. **Gemini's own English** — the most important part. Describe the grammar ceiling **in words**, from `curriculum.py lesson` (Grammar ceiling → section titles in `grammar_sections.csv`): which structures Gemini may use, 3–5 example questions it can ask **with that grammar only**, and which common structures it must avoid (name them: e.g. "no do/does questions, no past, no will"). This also applies to corrections and to answers to the learner's questions. At A1–A2: slow, clear, 1–2 short sentences per turn, very common words.
4. **What the learner should do** (hidden objectives, "never say this aloud"): turn each objective into something concrete in this situation, with an example question that invites it **and the form the learner must produce** (e.g. "experiences with the present perfect: *I've been to…*, *I've never…*"). Write `hidden_objectives` with the form too ("Talk about experiences with the present perfect (I've been to…)"): Gemini counts an objective as done only when the learner has used its form, and asks one more natural question when the learner answers without it (the page adds that rule). Keep the order consistent: if you list example questions, list them in the order you want Gemini to ask them (do not also say "alternate" if the list is not alternated). Put the objectives in an order that fits the turns: an objective where the **learner** must ask or do something ("ask a question", "make a suggestion") goes **around the middle**, never last, so it is not lost when the conversation ends. When you ask Gemini to invite a learner question, tie it to the content and place it right after the character has told something about itself ("…my sister's apartment is old. Ask me about my apartment!"), never a bare "Ask me a question!"; write the exact invitation words, inside the grammar ceiling (never "Do you have any questions?" below the level that has do/have), and say it is used ONCE; if the character offers a secret fact (e.g. "I know Sara's answer"), say what it is so Gemini can tell it later if the learner does not ask; also add it to `hidden_objectives` ("Ask the other person a question"): the engine rejects the brief otherwise, and Gemini then checks it before ending. When Gemini invites the learner's question, do not script Gemini's answer (no "answer about where you studied"): the page already tells Gemini to answer the learner's actual question first. The page adds the ending rules (it checks the objectives before ending practice; it ends the exam after the target turns).
5. **Target grammar and pronunciation focus**: how Gemini models them and which questions make the learner produce them (answers that naturally contain the target forms). The page adds the focus and `pronunciation_words` to Gemini's report rules and, at the end, sends the list of learner turns with the focus words marked, so Gemini writes one note per turn (and is asked once more for any missing note).
   - **Pronunciation check (practice only, once, around the middle of the chat):** write a short, natural sentence from the situation that contains the pronunciation focus (e.g. for linking: *"I wake up at seven and eat a big breakfast"*). Write it for Gemini as four separate steps, each in its own turn:
     1. Gemini says the sentence alone and asks: *"Can you say it?"* (nothing else in that turn).
     2. After the learner's try, ONE comment that **names the exact words** of the focus and says what it heard: *"Good: I heard wake‿up as one word."* or *"Join these two words: eat‿a, like 'ee-ta'."*. A bare *"Great!"* is not allowed.
     3. If anything needs work: *"Try once more."*, then a short comment on the second try.
     4. Back to the conversation in role.
     Never in the exam.
6. **Conversation style**: mostly open questions; ONE question per turn, at the end; react to answers with a short comment of its own; connect to the learner's life and interests (from notes and preferences). Give the character 2–3 facts of its own (likes, a small story, an opinion on the topic) that it can share: the page tells Gemini to start every turn (except the pronunciation check) with its own opinion or a fact about itself, and to react to a personal answer with one more question about it before moving on. Never write questions that name the grammar ("Can you compare them using better than?"): the page forbids it; write content questions whose answers need the form.
7. **Corrections**:
   - practice → **direct corrections** (owner decision 2026-11-05): every mistake with the lesson's grammar or words is corrected at once, short and kind, with "We say: …" + the full correct phrase, one per turn, no rule explanation and no "say it again"; give 2 examples built on **this lesson's** grammar and typical errors of Spanish speakers (e.g. "different for" → "We say: different from Max.");
   - exam → the page already adds the general assessment rules (no corrections, no praise, no help); write only one line with an example from **this** situation of what a correction would look like, and what to do if the learner is stuck (ask again more simply once, then move on). Spell out, with an example from this situation, that repeating the learner's sentence in a corrected form **is** a correction, and that judging answers ("Correct!", "Good!") is not allowed: the character reacts naturally ("I see.", "Nice.") and asks the next question.
8. **About the learner** (practice only): today's errors and interests from `learner_notes`, written as background for choosing topics. Tell Gemini that, in role, it does **not** know these facts: it must never mention them before the learner does (a stranger cannot ask "Is she here with you?" about a wife nobody has mentioned). Every person Gemini talks about must be introduced first. In the exam, nothing about the learner (the engine rejects exam briefs with notes).
9. **Language and role**: never speak Spanish (rephrase in simpler English); stay in role, no disclaimers.
10. **How to start**: the first thing Gemini says (greeting + first question).

### Text + conversation (every voice session: practice and exam)

Owner decision 2026-11-05: **every** conversation (practice and exam, voice and text mode) starts with a short new text, and the whole conversation is **only about that text**. Gemini first **reads the text aloud**, then the two talk about it. The engine rejects a brief without `shared_text`.

- **The text** (`shared_text`: `kind` news | article | story | lesson, `title`, `body`, optional `resource_id` `TXT-<lesson>-<n>`). Write it new for this learner (never the lesson reading or a text used before), with the lesson's grammar and priority words used naturally, inside the grammar ceiling; at A1–A2 short sentences and very common words. Length (the engine checks it): A1 80–130 · A2 110–190 · B1 160–260 · B2 220–340 · C1 280–420 words. Pick the kind that fits the lesson (news, an article, a short story, or the text type of the lesson: an email, an ad, a review…). Put enough people, places and open points (a decision, a problem, a surprise, different opinions) in it to carry the whole conversation, and make sure **every objective can be done talking about the text** (see below). Names and facts fictional or neutral.
- **Objectives inside the text world.** The conversation does not leave the text, so when an objective is about the learner ("say your name and job", "describe your home"), give the learner a place in the story: a new student in the same class, the new receptionist at the hotel, a neighbour of the people in the story… The learner's opinions about the text ("Which apartment is better for you?") are always allowed. Gemini plays a person from the story or someone who knows it.
- **On the page**: the learner hears it first; the text is also folded on the page ("Show the text"), in practice **and** in the exam, so they can check a word, but they talk with their own words. They can ask to hear it again.
- **Do not paste the text into `agent_instructions`**: the page adds it with the reading rules (read it word for word at the start, then the first question; read it again when asked) and the rule that the conversation stays on the text. The priority words may appear in the text or in your instructions (the engine checks both).
- **A natural conversation, not an interrogation** — write this into the instructions:
  - Gemini also knows the text (a friend who read the same news, a classmate, a coworker, a person in the story) and has its own opinion; it gives its reaction or a short personal comment **before every question** (practice), and sometimes disagrees. Give it 2–3 facts of its own linked to the text.
  - Questions are about opinions, feelings, predictions and the learner's place in the story ("Would you do the same?", "What do you think happens next?", "Which one is better for you?"), and follow what the learner says.
  - At most one or two quick comprehension checks, woven in naturally ("Wait — did she sell the house in the end?"), never a list of quiz questions, never "Question 1".
  - The objectives (and the target forms) still guide the questions: retelling a part (past simple), comparing, giving an opinion, predicting…
- **Exam**: the same text + conversation, with the assessment rules (no corrections, no praise, no help). The text is task material: it gives facts, never model answers for the objectives.
- Pictures are optional (at A1–A2 a picture or `picture_waived_reason` is still required: the text can be the reason, e.g. "The learner hears a short story; there is nothing else to show").
- Start the instructions' **How to start** with: say hello, say you have a short text and read it, then the first question (the page tells Gemini to read it first).

### Pictures (1–3; **required at A1–A2**, recommended at B1)

At A1–A2 every conversation has at least one picture; the engine rejects a brief without `pictures` unless you write `picture_waived_reason` (only when nothing in the situation can be shown, e.g. a chat about feelings). **If the learner must talk about something the situation gives them** — the thing they lost, the room they rent, the person they meet, a timetable — its facts must be in a picture (e.g. a `drawing` of the lost bag: a small black backpack with a red zip, a laptop and two books next to it, labelled with key words), never left for the learner to invent in a foreign language.

A picture helps when the learner must talk about things they can see: people in a photo, a home, a timetable, clues, a menu. Use more than one when the situation has more than one thing to look at (e.g. a family photo **and** the things on a table). Write a small spec for `scripts/picture.py` and put the specs in the brief as `pictures` (a list, max. 3). **Most pictures are drawings** (owner decision 2026-11-11). Choose in this order (the docstring shows each format and the icon list):
1. **`drawing`** — the default: a map, a floor plan, a street, a room, a scene, people doing something, objects on a table, a product, a chart. You draw it yourself with simple SVG shapes (rect, circle, ellipse, line, path, polygon, text) on a canvas 760 wide: flat colours, large clear shapes, short labels as key words, things placed where the conversation needs them (left/right, near/far, next to, in front of). Add `description`: what the learner sees, where each thing is, and every text written on it; it goes word for word into the instructions like any other picture. Before using a new drawing, render it once (`--svg out.svg`) and look at it.
2. A drawn template when it shows exactly what you need with less work: `people` (a photo of people), `home` (rooms of a home), `icons` (a few events, objects or places, each with a small drawing), `schedule` (a timetable), `card` (a menu, a price list, a ticket).
3. **`board` (notes) only as the last resort**, when drawing the content would be very complex (e.g. abstract clues with times and amounts). It needs `notes_reason`; the engine rejects a board without it. Never turn a map, a place or a scene into notes.

`picture.py` rejects scripts, images, links and texts that break the key-word rule.

**A picture is a help, not a script.** It gives the facts as **key words** (max. 6 per text, no verbs such as is/are/has/have/will/can), never sentences and never the grammar the learner must produce: write *"Blue River · Main Street · 200 people"*, not *"The Blue River has flooded"*. Put the facts on the drawing as short labels next to the thing they belong to. `picture.py` rejects texts that break this rule. In `agent_instructions`, tell Gemini that the picture shows key words and that the learner must make the sentences.

1. For each spec: `python3 scripts/picture.py --spec picture.json` → `description`.
2. Copy each description **word for word** into `agent_instructions` ("PICTURE 1 — THE LEARNER SEES: …", "PICTURE 2 — …") and tell Gemini how to use them (ask about one item at a time; refer to people by position or name; say "the first picture", "the second picture"). The engine rejects a picture without its description.
3. `engine.py voice-code` draws the pictures and puts them in the code; the page shows them under the situation, in order.

Keep the picture consistent with the situation text and the lesson's vocabulary. When the lesson is about near and far (this/that, these/those, here/there) or left and right, say where **both** people are (e.g. "You stand next to the learner at the table"), so that near and far are the same for both and Gemini models the right word. When the practice is about the learner's own life (their real family, their routine), either give them a character with the picture ("You are Ana; this is your family") or use no picture. In the exam a picture is task material: it may show facts, never model answers.

Examples to copy only where they fit: never use examples from other levels (no C1 structures in an A1 prompt). Full examples for L001: `examples/voice_brief_practice.json` and `examples/voice_brief_exam.json` (field `agent_instructions`).

Before generating the code, reread the text as Gemini would: is every example question inside the ceiling? Does every objective have a way to happen? Is there anything that sounds like a quiz?

`session_id` = next free number in `voice-sessions/` (S0001, S0002…; look at the project's doc list). Save `brief.json` before the conversation starts, in both modes.

### Placement Speaking (step `writing_speaking` of the placement test)

A short conversation, so the placement test stays near its 60 minutes (owner decision 2026-11-11). Write the brief as an exam with these differences (the engine checks them):

- `mode` `exam`, `event_id` `PLACEMENT`, `attempt` 1, `level` = the level in the placement step; `lesson_id` = the level's final review lesson (`curriculum.py level <L>` › `final_review`), only because the contract needs a lesson.
- `end_condition`: `target_learner_turns` 6, `max_minutes` 6, at every level.
- `shared_text`: 60–100 words, in the grammar and vocabulary of that level.
- Objectives, target grammar and situation: from the Speaking component of that level's exit (`curriculum.py event EXIT-<L>`), cut down to what six turns can show: 2–3 objectives. No `resource`, no `learner_notes`.
- From B1 the exit Speaking rubric has a Mediation row: have Gemini ask once, in a natural way, for a part of the text in the learner's own words ("I missed the end — what happened?"), so the evaluator can score it. Without such a moment the evaluator leaves that row out (allowed in placement only).
- Everything else as in an exam (§ 1b): no corrections, no praise, no help; a picture or `picture_waived_reason` at A1–A2.
