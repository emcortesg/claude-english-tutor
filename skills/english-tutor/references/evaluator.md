# Scoring a formal event (scoring agents)

You never score, and you never count items: `engine.py` counts every item from its `key` and the learner's answer. A scoring agent is needed only for what code cannot judge — the rubric bands of Writing and Speaking, and open answers that are not identical to the key.

## Which agent: ask the engine

`engine.py mark --evidence E.json` (it changes nothing) returns `agent`, `open_items`, `rubric_dimensions` and `problems`:

| `agent` | When | What to do |
| --- | --- | --- |
| `none` | Every item is closed (it has `options`) or was answered exactly like the key, and there is no Writing/Speaking. Typical: unit listening checks, placement probes | No agent. `engine.py score` (or `placement`) with `--evidence` only |
| `item-checker` (`english-course:item-checker`, Haiku, low effort) | Open items wait for a verdict and there is no Writing/Speaking | Launch it with `EVIDENCE` and `OPEN_ITEMS` |
| `evaluator` (`english-course:evaluator`, Sonnet, medium effort) | Writing or Speaking is assessed: lesson assessment, review diagnostic / checkpoint, level exit, placement `writing_speaking` | Launch it with everything below; it also gives the verdicts for `open_items` |

If `problems` is not empty (a key that is not one of its options, a repeated `item_id`, a dimension without its items), fix the package first.

Launch the agent **once per formal event**, with a clean context: do not pass it the class conversation, your impressions or your opinion of the learner. Its instructions live in the plugin's agents (`agents/` at the plugin root, two folders above this skill: `../../agents/`); the model and effort are fixed there. If the Agent tool does not list these agents (e.g. the plugin's agents are not loaded on this surface), launch a general-purpose agent with `model` `haiku` (item-checker) or `sonnet` (evaluator) and paste the body of the agent file (`../../agents/item-checker.md` or `../../agents/evaluator.md`, without its frontmatter) at the top of the prompt.

## What to give it

Write the inputs to files in your working folder and give their paths (the agents can Read), or paste them:

- `EVIDENCE`: the complete `evidence_package` (JSON).
- `OPEN_ITEMS`: the `open_items` list from `engine.py mark`, or `none`.
- `VOICE_REPORT` (evaluator only): the Speaking `report.json`, or `none`.
- `RUBRICS` (evaluator only): `curriculum.py rubrics <level> lesson|exit` — every row of the dimensions to score, plus the level's calibration row. The engine checks that the evaluator gave one band for each of those rows (pronunciation may be missing only when `speaking.channel` is `text`).
- `SPEC` (evaluator only): the assessment fields of the spec (`Lesson assessment – …`, `Observable evidence of learning`, `Success criteria`) and the lesson's `Conversation priority vocabulary`.

Message template:

```
Score this event.
EVIDENCE: <path or JSON>
OPEN_ITEMS: <list of item_ids or "none">
VOICE_REPORT: <path, JSON or "none">
RUBRICS: <path or JSON>
SPEC: <text>
```

## After it answers

Save its JSON as `scores.json`, validate it (`engine.py validate --file scores.json --schema evaluator_scores`). If it does not validate, send the errors to the same agent once and ask only for the corrected JSON. Then `engine.py score --state STATE --evidence E.json --scores scores.json`. If the engine rejects the scores (a rubric row without a band, a bare `score_pct`, an open item without a verdict), send that error to the same agent once; never edit the scores yourself.
