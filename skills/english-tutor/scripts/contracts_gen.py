"""Generate JSON Schemas (2020-12) + L001 examples for agent contracts and student-state files, and validate them."""
import json, os, sys
from jsonschema import Draft202012Validator

OUT = sys.argv[1]
BASE = 'https://curso-ingles/contracts/'
os.makedirs(f'{OUT}/schemas', exist_ok=True); os.makedirs(f'{OUT}/examples', exist_ok=True)

# ---------- shared definitions
defs = {
  'lessonId': {'type': 'string', 'pattern': '^L\\d{3}$'},
  'level': {'enum': ['A1', 'A2', 'B1', 'B2', 'C1']},
  'section': {'type': 'string', 'pattern': '^\\d\\.\\d+a?$'},
  'studentId': {'type': 'string', 'pattern': '^student-\\d{4}$'},
  'sessionId': {'type': 'string', 'pattern': '^S\\d{4,}$'},
  'eventId': {'type': 'string', 'description': 'Lesson ID (lesson assessment), Check ID (ULC-…), exit ID (EXIT-…), or PLACEMENT', 'pattern': '^(L\\d{3}|ULC-[A-C][12]-U\\d{2}R?|EXIT-[A-C][12]|PLACEMENT)$'},
  'dimension': {'enum': ['Reading', 'Writing', 'Speaking', 'Listening', 'Grammar', 'Vocabulary']},
  'band': {'enum': [0, 25, 50, 75, 100]},
  'pct': {'type': 'number', 'minimum': 0, 'maximum': 100},
  'datetime': {'type': 'string', 'format': 'date-time'},
  'date': {'type': 'string', 'format': 'date'},
  'resourceRef': {'type': 'object', 'required': ['resource_id', 'kind'], 'additionalProperties': False,
                  'properties': {'resource_id': {'type': 'string'}, 'kind': {'enum': ['text', 'audio', 'prompt']}, 'source': {'type': 'string'}}},
}
def schema(name, title, desc, props, required, extra=None):
    s = {'$schema': 'https://json-schema.org/draft/2020-12/schema', '$id': BASE + name + '.schema.json', 'title': title, 'description': desc,
         'type': 'object', 'additionalProperties': False, 'required': required, 'properties': props, '$defs': defs}
    if extra: s.update(extra)
    return s
R = lambda k: {'$ref': f'#/$defs/{k}'}
contract = {'type': 'string'}

S = {}
# ---------- 1. voice brief (tutor → voice page)
S['voice_brief'] = schema('voice_brief', 'Voice agent brief', 'Written by the tutor to voice-sessions/<session_id>/brief.json; read by the voice page. agent_instructions, written by the tutor for this lesson, is what Gemini Live receives as its instructions (the page only adds a fixed technical block: turns, ending, report).', {
  'contract': {'const': 'voice_brief/3'}, 'session_id': R('sessionId'), 'student_id': R('studentId'), 'created_at': R('datetime'),
  'mode': {'enum': ['practice', 'exam']}, 'lesson_id': R('lessonId'), 'level': R('level'), 'event_id': R('eventId'), 'attempt': {'type': 'integer', 'minimum': 1},
  'visible_to_learner': {'type': 'object', 'additionalProperties': False, 'required': ['situation'], 'properties': {
      'situation': {'type': 'string', 'description': 'The only part the page shows to the learner'}}},
  'agent_instructions': {'type': 'string', 'minLength': 300, 'maxLength': 6000, 'description': 'Instructions for Gemini Live written by the tutor for this lesson and learner, in English (references/voice.md › agent_instructions)'},
  'pictures': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'description': 'Optional picture specs for scripts/picture.py (1–3); the page shows the drawings under the situation',
      'items': {'type': 'object', 'required': ['template'], 'properties': {'template': {'enum': ['people', 'home', 'schedule', 'board', 'card', 'icons', 'drawing']}, 'title': {'type': 'string'}}}},
  'character_gender': {'enum': ['female', 'male'], 'description': "Gender of the character Gemini plays; the voice page picks a matching Gemini voice"},
  'shared_text': {'type': 'object', 'additionalProperties': False, 'required': ['kind', 'title', 'body'],
    'description': 'Required in every voice session (practice and exam): a short new text that Gemini reads aloud at the start; the conversation is only about it (references/voice.md › Text + conversation)',
    'properties': {'kind': {'enum': ['news', 'article', 'story', 'lesson']}, 'title': {'type': 'string', 'minLength': 3, 'maxLength': 80},
      'body': {'type': 'string', 'minLength': 150, 'maxLength': 2200}, 'resource_id': {'type': 'string', 'pattern': '^TXT-L\\d{3}-[A-Za-z0-9-]+$'}}},
  'picture_waived_reason': {'type': 'string', 'minLength': 15, 'description': 'A1–A2 only: why this conversation has no picture (required when pictures is absent)'},
  'hidden_objectives': {'type': 'array', 'minItems': 1, 'items': {'type': 'string'}},
  'target_grammar': {'type': 'object', 'additionalProperties': False, 'required': ['sections', 'focus'], 'properties': {
      'sections': {'type': 'array', 'items': R('section'), 'minItems': 1}, 'focus': {'type': 'string'}, 'target_uses': {'type': 'integer', 'minimum': 0}}},
  'priority_vocabulary': {'type': 'array', 'items': {'type': 'string'}},
  'pronunciation_focus': {'type': 'string'},
  'pronunciation_words': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 12, 'description': 'Words that carry the pronunciation focus (e.g. ["mustn\'t"]); the page marks the learner turns that contain them so that Gemini writes a focused note'}, 'learner_notes': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Tutor input (errors seen today, interests)'},
  'end_condition': {'type': 'object', 'additionalProperties': False, 'required': ['max_minutes'], 'properties': {
      'target_learner_turns': {'type': 'integer', 'minimum': 1}, 'max_minutes': {'type': 'number', 'exclusiveMinimum': 0}}},
  'resource': R('resourceRef'),
}, ['contract', 'session_id', 'student_id', 'created_at', 'mode', 'lesson_id', 'level', 'visible_to_learner', 'agent_instructions', 'hidden_objectives', 'target_grammar',
    'priority_vocabulary', 'pronunciation_focus', 'end_condition', 'shared_text', 'character_gender'],
 {'allOf': [{'if': {'properties': {'mode': {'const': 'exam'}}}, 'then': {'required': ['event_id', 'attempt']}}]})

# ---------- 2. voice report (voice page → tutor / evaluator)
turn = {'type': 'object', 'additionalProperties': False, 'required': ['n', 'speaker', 'text', 'start_s', 'end_s'], 'properties': {
  'n': {'type': 'integer', 'minimum': 1}, 'speaker': {'enum': ['learner', 'agent']}, 'text': {'type': 'string'},
  'start_s': {'type': 'number', 'minimum': 0}, 'end_s': {'type': 'number', 'minimum': 0}}}
S['voice_report'] = schema('voice_report', 'Voice agent report', 'Written by the voice page to voice-sessions/<session_id>/report.json when the conversation ends. Audio is not kept: it is deleted as soon as Gemini writes the pronunciation notes.', {
  'contract': {'const': 'voice_report/1'}, 'session_id': R('sessionId'), 'student_id': R('studentId'), 'mode': {'enum': ['practice', 'exam']},
  'channel': {'enum': ['voice', 'text'], 'description': 'text = chat conversation (no voice page or no consent); no pronunciation notes'},
  'lesson_id': R('lessonId'), 'started_at': R('datetime'), 'ended_at': R('datetime'),
  'end_reason': {'enum': ['objectives_met', 'turns_completed', 'time_limit', 'learner_left', 'technical_error', 'quota_exceeded']},
  'duration_s': {'type': 'number', 'minimum': 0},
  'audio_deleted_at': {**R('datetime'), 'description': 'When the page deleted the audio after writing the notes (practice and exam)'},
  'transcript': {'type': 'array', 'items': turn},
  'pronunciation_notes': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['turn', 'focus_feature', 'achieved', 'observation', 'affects_intelligibility'], 'properties': {
      'turn': {'type': 'integer', 'minimum': 1}, 'focus_feature': {'type': 'string'}, 'achieved': {'type': 'boolean'}, 'observation': {'type': 'string'}, 'affects_intelligibility': {'type': 'boolean'}}},
      'description': 'Written by Gemini from the audio; descriptive, no score'},
  'target_grammar_uses': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['turn', 'form', 'accurate'], 'properties': {
      'turn': {'type': 'integer'}, 'form': {'type': 'string'}, 'accurate': {'type': 'boolean'}, 'correction_given': {'type': 'string'}}}},
  'priority_vocabulary_used': {'type': 'array', 'items': {'type': 'string'}},
  'errors': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['turn', 'learner_said', 'issue'], 'properties': {
      'turn': {'type': 'integer'}, 'learner_said': {'type': 'string'}, 'issue': {'type': 'string'}, 'section': R('section'), 'recast': {'type': 'string'}}}},
  'objectives_met': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['objective', 'met'], 'properties': {'objective': {'type': 'string'}, 'met': {'type': 'boolean'}}}},
  'learner_turns': {'type': 'integer', 'minimum': 0},
}, ['contract', 'session_id', 'student_id', 'mode', 'lesson_id', 'started_at', 'ended_at', 'end_reason', 'transcript', 'pronunciation_notes', 'objectives_met', 'learner_turns', 'duration_s', 'audio_deleted_at'])

# ---------- 3. evidence package (tutor → evaluator)
S['evidence_package'] = schema('evidence_package', 'Evidence package for the evaluator', 'Built by the tutor with the raw evidence; the evaluator never receives tutor summaries. engine.py marks every item itself from key + learner_answer: an item with options is closed (exact match); an item without options is open (exact match, or the scoring agent verdict in evaluator_scores.item_results).', {
  'contract': {'const': 'evidence_package/1'}, 'student_id': R('studentId'), 'event_id': R('eventId'),
  'event_type': {'enum': ['lesson_assessment', 'review_diagnostic', 'review_assessment', 'unit_listening_check', 'level_exit', 'placement_stage1', 'placement_stage2_probe']},
  'attempt': {'type': 'integer', 'minimum': 1}, 'form_id': {'type': 'string'}, 'level': R('level'), 'lesson_id': R('lessonId'),
  'spec_ref': {'type': 'string', 'description': 'Curriculum sheet and row with the specification (e.g. Lesson_Practice_Assessment!L001)'},
  'rubric_ids': {'type': 'array', 'items': {'type': 'string', 'pattern': '^RB-(LS|LW|XS|XW)-\\d{2}$'}},
  'dimensions_to_score': {'type': 'array', 'minItems': 1, 'items': R('dimension')},
  'reading': {'type': 'object', 'additionalProperties': False, 'required': ['resource', 'items'], 'properties': {
      'resource': R('resourceRef'), 'text': {'type': 'string'},
      'items': {'type': 'array', 'minItems': 1, 'items': {'type': 'object', 'additionalProperties': False, 'required': ['item_id', 'question', 'key', 'learner_answer'], 'properties': {
          'item_id': {'type': 'string'}, 'section': R('section'), 'sub_skill': {'type': 'string'}, 'question': {'type': 'string'}, 'options': {'type': 'array', 'items': {'type': 'string'}},
          'key': {'type': 'string'}, 'accepted_variants': {'type': 'array', 'items': {'type': 'string'}}, 'learner_answer': {'type': 'string'},
          'oxford_id': {'type': 'integer', 'description': 'Vocabulary items (placement, exit): Oxford ID of the tested word; the engine lists the failed ones'}}}}}},
  'writing': {'type': 'object', 'additionalProperties': False, 'required': ['prompt', 'learner_text', 'word_range'], 'properties': {
      'resource': R('resourceRef'), 'prompt': {'type': 'string'}, 'word_range': {'type': 'array', 'items': {'type': 'integer'}, 'minItems': 2, 'maxItems': 2},
      'target_uses': {'type': 'integer'}, 'learner_text': {'type': 'string'}}},
  'speaking': {'type': 'object', 'additionalProperties': False, 'required': ['voice_session_id', 'voice_report_path'], 'properties': {
      'resource': R('resourceRef'), 'voice_session_id': R('sessionId'), 'voice_report_path': {'type': 'string'}, 'target_uses': {'type': 'integer'},
      'channel': {'enum': ['voice', 'text'], 'description': 'Copy it from the voice report. text = no pronunciation criterion; absent = voice'}}},
  'listening': {'type': 'object', 'additionalProperties': False, 'required': ['source_id', 'items'], 'properties': {
      'source_id': {'type': 'string'}, 'items': {'$ref': '#/properties/reading/properties/items'}}},
  'grammar': {'type': 'object', 'additionalProperties': False, 'required': ['items'], 'description': 'Placement probes', 'properties': {'items': {'$ref': '#/properties/reading/properties/items'}}},
  'vocabulary': {'type': 'object', 'additionalProperties': False, 'required': ['items'], 'description': 'Placement probes; each item carries oxford_id', 'properties': {'items': {'$ref': '#/properties/reading/properties/items'}}},
  'tagged_sections': {'type': 'array', 'items': R('section'), 'description': 'Sections to score separately (Review, placement)'},
}, ['contract', 'student_id', 'event_id', 'event_type', 'attempt', 'level', 'spec_ref', 'dimensions_to_score'])

# ---------- 4. evaluator scores (evaluator → server)
crit = {'type': 'object', 'additionalProperties': False, 'required': ['rubric_id', 'band', 'evidence_quote', 'justification'], 'properties': {
  'rubric_id': {'type': 'string', 'pattern': '^RB-(LS|LW|XS|XW)-\\d{2}$'}, 'band': R('band'), 'evidence_quote': {'type': 'string'}, 'justification': {'type': 'string'}}}
S['evaluator_scores'] = schema('evaluator_scores', 'Evaluator scores', 'The scoring agent gives rubric bands (Writing, Speaking) and verdicts for open items; it does NOT count items or decide pass/fail: engine.py does that (P01–P03).', {
  'contract': {'const': 'evaluator_scores/1'}, 'student_id': R('studentId'), 'event_id': R('eventId'), 'attempt': {'type': 'integer', 'minimum': 1}, 'form_id': {'type': 'string'},
  'scored_at': R('datetime'),
  'item_results': {'type': 'array', 'description': 'Verdict for each OPEN item (no options) whose answer is not identical to the key; engine.py mark lists them. The engine counts the totals.',
      'items': {'type': 'object', 'additionalProperties': False, 'required': ['item_id', 'correct'], 'properties': {'item_id': {'type': 'string'}, 'correct': {'type': 'boolean'}, 'note': {'type': 'string'}}}},
  'dimensions': {'type': 'array', 'description': 'Writing and Speaking: one criteria entry per rubric row. Item dimensions are counted by the engine from the evidence (entries for them are ignored).', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['dimension', 'score_pct'], 'properties': {
      'dimension': R('dimension'), 'score_pct': R('pct'),
      'items_correct': {'type': 'integer', 'minimum': 0}, 'items_total': {'type': 'integer', 'minimum': 1},
      'criteria': {'type': 'array', 'items': crit},
      'subskills': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['sub_skill', 'correct', 'total'], 'properties': {
          'sub_skill': {'type': 'string'}, 'correct': {'type': 'integer', 'minimum': 0}, 'total': {'type': 'integer', 'minimum': 1}}}}}}},
  'sections': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['section', 'score_pct'], 'properties': {'section': R('section'), 'score_pct': R('pct'), 'items_correct': {'type': 'integer', 'minimum': 0}, 'items_total': {'type': 'integer', 'minimum': 1}}}},
  'errors_observed': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['section', 'description'], 'properties': {'section': R('section'), 'description': {'type': 'string'}}}},
  'failed_vocabulary': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'Oxford IDs failed (placement and exams)'},
  'reinforcement_recommendation': {'type': 'string'},
}, ['contract', 'student_id', 'event_id', 'attempt', 'scored_at'])

# ---------- 5. decision (server → tutor)
S['decision'] = schema('decision', 'Engine decision', 'Result returned by engine.py to the tutor after applying P01–P03 (and P05, P06, P09, P10).', {
  'contract': {'const': 'decision/1'}, 'student_id': R('studentId'), 'event_id': R('eventId'), 'attempt': {'type': 'integer', 'minimum': 1},
  'global_pct': R('pct'), 'dimension_results': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['dimension', 'score_pct', 'passed'], 'properties': {
      'dimension': R('dimension'), 'score_pct': R('pct'), 'passed': {'type': 'boolean'}}}},
  'event_type': {'type': 'string'}, 'cycle': {'type': 'integer', 'minimum': 1},
  'decision': {'enum': ['passed', 'retest_pending', 'repeat_content', 'placed', 'diagnosed']},
  'retest_dimensions': {'type': 'array', 'items': R('dimension'), 'description': 'Dimensions to reassess in the retest'},
  'failed_dimensions': {'type': 'array', 'items': R('dimension')}, 'flagged_sections': {'type': 'array', 'items': R('section')},
  'attempts_left': {'type': 'integer', 'minimum': 0, 'maximum': 3},
  'repeat_lessons': {'type': 'array', 'items': R('lessonId'), 'description': 'Only with decision = repeat_content'},
  'listening_session': {'type': 'boolean', 'description': 'With repeat_content on a listening check: listening session with the same recordings and new questions (P10)'},
  'next_event': R('eventId'), 'next_lesson': R('lessonId'), 'start_lesson': R('lessonId'), 'notes': {'type': 'array', 'items': {'type': 'string'}},
}, ['contract', 'student_id', 'event_id', 'event_type', 'attempt', 'global_pct', 'dimension_results', 'decision', 'attempts_left'])

# ---------- state files
S['profile'] = schema('profile', 'profile.json', 'Learner profile. Written by engine.py.', {
  'student_id': R('studentId'), 'name': {'type': 'string'}, 'email': {'type': 'string'}, 'started_on': R('date'),
  'placement_level': R('level'), 'start_lesson': R('lessonId'),
  'recording_consent': {'type': 'object', 'additionalProperties': False, 'required': ['given', 'date'], 'properties': {'given': {'type': 'boolean'}, 'date': R('date'), 'text_version': {'type': 'string'}}},
  'interests': {'type': 'array', 'items': {'type': 'string'}}}, ['student_id', 'name', 'started_on', 'recording_consent'])
S['progress'] = schema('progress', 'progress.json', 'Learner position in the course. Written by engine.py.', {
  'student_id': R('studentId'), 'current_lesson': R('lessonId'), 'current_event': R('eventId'), 'updated_at': R('datetime'),
  'lessons_passed': {'type': 'array', 'items': R('lessonId'), 'uniqueItems': True},
  'lessons_credited': {'type': 'array', 'items': R('lessonId'), 'uniqueItems': True, 'description': 'Credited by placement (P17)'},
  'checks_passed': {'type': 'array', 'items': {'type': 'string'}, 'uniqueItems': True},
  'checks_credited': {'type': 'array', 'items': {'type': 'string'}, 'uniqueItems': True},
  'exits_passed': {'type': 'array', 'items': {'type': 'string', 'pattern': '^EXIT-[A-C][12]$'}, 'uniqueItems': True},
  'exits_credited': {'type': 'array', 'items': {'type': 'string', 'pattern': '^EXIT-[A-C][12]$'}, 'uniqueItems': True},
  'pending': {'type': ['object', 'null'], 'additionalProperties': False, 'properties': {'event_id': R('eventId'), 'event_type': {'type': 'string'}, 'status': {'enum': ['retest_pending', 'repeat_content', 'reinforcement', 'repeated', 'diagnosed']}, 'retest_dimensions': {'type': 'array', 'items': R('dimension')}, 'dimensions': {'type': 'array', 'items': R('dimension')}, 'repeat_lessons': {'type': 'array', 'items': R('lessonId')}, 'sections': {'type': 'array', 'items': R('section')}}},
  'replacements': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['date', 'from', 'to', 'accepted'], 'properties': {'date': R('date'), 'from': R('lessonId'), 'to': R('lessonId'), 'accepted': {'type': 'boolean'}, 'evidence': {'type': 'string'}}}},
}, ['student_id', 'current_lesson', 'updated_at', 'lessons_passed', 'lessons_credited', 'checks_passed', 'exits_passed'])
S['attempts'] = schema('attempts', 'attempts.json', 'Attempt history per event (P11). Written by engine.py.', {
  'student_id': R('studentId'),
  'events': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['event_id', 'cycle', 'attempts'], 'properties': {
      'event_id': R('eventId'), 'event_type': {'type': 'string'}, 'cycle': {'type': 'integer', 'minimum': 1, 'description': 'Increases by 1 each time content is repeated (P10); each cycle has up to 3 attempts'},
      'attempts': {'type': 'array', 'maxItems': 3, 'items': {'type': 'object', 'additionalProperties': False, 'required': ['attempt', 'date', 'form_id', 'scores', 'global_pct', 'decision'], 'properties': {
          'attempt': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'date': R('datetime'), 'form_id': {'type': 'string'},
          'resources': {'type': 'array', 'items': R('resourceRef')}, 'scores': {'type': 'object', 'additionalProperties': R('pct')},
          'section_scores': {'type': 'object', 'additionalProperties': R('pct')}, 'global_pct': R('pct'),
          'passed_dimensions': {'type': 'array', 'items': R('dimension')},
          'evidence_hash': {'type': 'string', 'description': 'Fingerprint of the evidence package: the same package cannot be scored twice'},
          'decision': {'enum': ['passed', 'retest_pending', 'repeat_content', 'placed', 'diagnosed']}}}}}}}}, ['student_id', 'events'])
S['resources'] = schema('resources', 'resources.json', 'Use of texts, recordings and prompts (max. 3 uses per learner, P08). Written by engine.py.', {
  'student_id': R('studentId'),
  'resources': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['resource_id', 'kind', 'uses'], 'properties': {
      'resource_id': {'type': 'string'}, 'kind': {'enum': ['text', 'audio', 'prompt']}, 'source': {'type': 'string'},
      'uses': {'type': 'array', 'maxItems': 3, 'items': {'type': 'object', 'additionalProperties': False, 'required': ['event_id', 'attempt', 'date', 'item_ids'], 'properties': {
          'event_id': R('eventId'), 'attempt': {'type': 'integer'}, 'date': R('datetime'), 'item_ids': {'type': 'array', 'items': {'type': 'string'}}}}}}}}}, ['student_id', 'resources'])
S['vocabulary'] = schema('vocabulary', 'vocabulary.json', 'Exceptions only: failed words for priority recycling. Taught words are derived from progress.json + curriculum. Written by engine.py.', {
  'student_id': R('studentId'),
  'priority_recycling': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['oxford_id', 'word', 'failed_in', 'date'], 'properties': {
      'oxford_id': {'type': 'integer'}, 'word': {'type': 'string'}, 'failed_in': R('eventId'), 'date': R('date'), 'recycled_in': {'type': 'array', 'items': R('lessonId'), 'uniqueItems': True}}}}}, ['student_id', 'priority_recycling'])
S['errors'] = schema('errors', 'errors.json', 'Accumulated errors by grammar section, from formal events and from practice (engine.py practice-log). Written by engine.py.', {
  'student_id': R('studentId'),
  'logged_sessions': {'type': 'array', 'items': R('sessionId'), 'uniqueItems': True, 'description': 'Practice voice sessions already added with practice-log'},
  'by_section': {'type': 'object', 'propertyNames': {'pattern': '^\\d\\.\\d+a?$'}, 'additionalProperties': {'type': 'object', 'additionalProperties': False, 'required': ['count', 'last_seen'], 'properties': {
      'count': {'type': 'integer', 'minimum': 0}, 'last_seen': R('date'), 'examples': {'type': 'array', 'maxItems': 5, 'items': {'type': 'string'}}}}}}, ['student_id', 'by_section'])

CATS = ['activity_format', 'example_topics', 'pace', 'feedback_style', 'explanation_style', 'practice_balance']
S['preferences'] = schema('preferences', 'preferences.json', 'Learner suggestions about HOW the class is taught (never WHAT is learned or assessed). Written by engine.py; read by the tutor at session start.', {
  'student_id': R('studentId'),
  'preferences': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['id', 'category', 'text', 'source_quote', 'created_on', 'status'], 'properties': {
      'id': {'type': 'string', 'pattern': '^PR\\d{3}$'}, 'category': {'enum': CATS},
      'text': {'type': 'string', 'minLength': 5, 'maxLength': 140, 'description': 'Short instruction for the tutor, in English'},
      'source_quote': {'type': 'string', 'maxLength': 300, 'description': 'What the learner said'},
      'created_on': R('date'), 'event_id': R('eventId'), 'status': {'enum': ['active', 'retired']}, 'retired_on': R('date')}}}}, ['student_id', 'preferences'])

for _n in ('profile', 'progress', 'attempts', 'resources', 'vocabulary', 'errors', 'preferences'):
    S[_n]['properties']['state_rev'] = {'type': 'integer', 'minimum': 0, 'description': 'Engine write counter; all files written by the same command carry the same value'}

# ---------- examples (L001)
L001P = '''You are Alex, the new student from Brazil in the story: you are a cook, you like the class, and today you are a little nervous too. After the class you talk with another new classmate, the learner: an adult Spanish speaker at the very start of A1. This is a real, friendly chat between two new classmates, not a test.

The learner sees only this: "It's the first evening of your English class at a community center in Miami. Listen to a short story about the class. Then talk about it with your classmate Alex."

After you read the story, talk ONLY about it: the class, the teacher and the students in it. The learner is a new student in the same class, so they can say who they are in this class. Give your own short opinion or a fact about yourself before every question ("For me, Mrs. Brown is very nice!"). Do not ask a list of questions about the story, and never say "Question 1". At most one quick check, in a natural way ("Wait, is Lina from Peru?").

YOUR ENGLISH (very important): the learner has studied only the verb be (am, is, are) with I, you, he, she, it, we, they. Use only this grammar and very common words (names, countries, nationalities, jobs, hello, goodbye, nice to meet you). Good questions: "What's your name?", "Where are you from?", "Who is she?", "Is Omar from Egypt?", "Are you nervous too?". No do/does questions, no have, no past, no will, no can. Speak slowly and clearly, one or two short sentences per turn. Ask only ONE question per turn, at the end, then wait.

WHAT THE LEARNER SHOULD DO (never say this aloud): (1) greet you; (2) say their name, where they are from and their job, as a new student in this class (form: I'm…, I'm from…, I'm a…); (3) introduce people from the story with he's/she's (form: "She's Lina. She's a nurse."). After you tell them something about yourself, invite them ONCE to ask you about it, with exactly these words: "Ask me about my job!" Guide the chat so they do all of this.

PRONUNCIATION: contractions I'm, you're, he's, she's, it's. Use them yourself and ask questions whose natural answers contain them ("Who is the teacher?" → "She's Mrs. Brown.").
PRONUNCIATION CHECK (once, around the middle; each step in its own turn): (1) say only "Let's practise one sentence: I'm Alex, and I'm from Brazil. Now you: I'm…, and I'm from…" (2) After their try, ONE comment that names the exact words: "Good: I heard I'm." or "Say I'm as one sound, not I am." Never just "Great!". (3) If it needs work: "Try once more.", then a short comment. (4) Go back to the chat.

CORRECTIONS (direct, short and kind): "I am data engineer" → "We say: I'm a data engineer. Oh, a data engineer! I'm a cook." "Is Ana" → "We say: She's Ana." One correction per turn, then continue.
ABOUT THE LEARNER (background only: in role you do not know this, so never mention it before the learner does): today they said "Is Ana" instead of "She is Ana" twice; they like soccer.

PRIORITY WORDS (use them naturally so the learner needs them too): be, yourself, call ("Call me Alex."), name, hello, goodbye, introduce, meet.

If the learner speaks Spanish or does not understand, say it again in simpler English with fewer words. Never speak Spanish. Stay in role.
Start now: say hello, say you have a short story about the first English class and read it; then ask the learner's name.'''
L001E = '''You are Sam, the receptionist from Florida in the story. The learner is the new receptionist at the Palm Hotel in Orlando, on their first day (in the story her name is Maria, but the learner is themselves). The learner is an adult Spanish speaker at A1. This is a short, friendly chat between two new coworkers.

The learner sees only this: "You start a new job at a hotel reception. Listen to a short story about the hotel. Then talk about it with your coworker Sam."

After you read the story, talk ONLY about it: the hotel and the people in it.

THIS IS AN ASSESSMENT: do not correct, teach, give hints or say model answers. Never repeat the learner's sentence in a corrected form ("Oh, you're a receptionist!" after "I am receptionist" is a correction) and never judge an answer ("Correct!", "Good!"): react only as a coworker would ("I see.", "Nice.") and ask the next question. If the learner is stuck, ask the same question again in simpler words once, then move on to a new question.

YOUR ENGLISH: the learner has studied only the verb be (am, is, are) with subject pronouns. Use only this grammar and very common words. Good questions: "What's your name?", "Where are you from?", "Who is Laura?", "Is Ben from Cuba?". No do/does questions, no have, no past, no will, no can. Speak slowly, one or two short sentences per turn, ONE question per turn.

WHAT THE LEARNER SHOULD DO (never say this aloud): greet you; say their name and introduce themselves (where they are from); introduce people from the story with he's/she's. Create natural chances for all of this: tell them about yourself first, then ask. Around the middle of the conversation (never at the end), after you tell them something about yourself, invite them to ask you about it: "Ask me about my city!"

PRIORITY WORDS (use them naturally so the learner needs them too): hello, name, meet, introduce, goodbye.

Never speak Spanish. Stay in role. Start now: say hello, say you have a short story about the hotel and read it; then ask the learner's name.'''
E = {}
E['voice_brief_practice'] = ('voice_brief', {
  'contract': 'voice_brief/3', 'session_id': 'S0001', 'student_id': 'student-0001', 'created_at': '2026-10-22T14:05:00-05:00',
  'mode': 'practice', 'lesson_id': 'L001', 'level': 'A1',
  'visible_to_learner': {'situation': "It's the first evening of your English class at a community center in Miami. Listen to a short story about the class. Then talk about it with your classmate Alex."},
  'hidden_objectives': ['Greet people', 'Say their name', 'Introduce themselves and others', 'Ask the other person a question'],
  'target_grammar': {'sections': ['4.1'], 'focus': 'am/is/are + subject pronouns: identity, names, jobs, nationality', 'target_uses': 3},
  'priority_vocabulary': ['be', 'yourself', 'call', 'name', 'goodbye', 'hello', 'introduce', 'meet'],
  'pronunciation_focus': "Contractions with be: I'm /aɪm/, you're /jʊr/, he's /hiz/, she's /ʃiz/, it's /ɪts/.",
  'learner_notes': ['Today the learner said "Is Ana" instead of "She is Ana" twice.', 'Likes soccer.'],
  'agent_instructions': L001P, 'character_gender': 'male',
  'shared_text': {'kind': 'story', 'title': 'The First Class', 'resource_id': 'TXT-L001-first-class',
    'body': 'It is Monday evening, and this is the first English class at a community center in Miami. The teacher is Mrs. Brown. She is from Texas, and she is very friendly. Alex is a new student. He is from Brazil, and he is a cook. Lina is next to him. She is from Peru. She is a nurse. Omar is the student at the door. He is from Egypt, and he is a taxi driver. They are all new, and they are a little nervous. "Hello, everyone! I am Mrs. Brown. Nice to meet you," the teacher says. "Please introduce yourself." Alex is the first. "Hello! My name is Alex. I am from Brazil."'},
  'picture_waived_reason': 'The story gives the people; the learner introduces themselves with their real name, country and job.',
  'end_condition': {'target_learner_turns': 18, 'max_minutes': 14}})
E['voice_brief_exam'] = ('voice_brief', {
  'contract': 'voice_brief/3', 'session_id': 'S0002', 'student_id': 'student-0001', 'created_at': '2026-10-22T14:50:00-05:00',
  'mode': 'exam', 'lesson_id': 'L001', 'level': 'A1', 'event_id': 'L001', 'attempt': 1,
  'visible_to_learner': {'situation': 'You start a new job at a hotel reception. Listen to a short story about the hotel. Then talk about it with your coworker Sam.'},
  'hidden_objectives': ['Greet people', 'Say their name', 'Introduce themselves and others', 'Ask the other person a question'],
  'target_grammar': {'sections': ['4.1'], 'focus': 'am/is/are + subject pronouns', 'target_uses': 3},
  'priority_vocabulary': ['hello', 'name', 'meet', 'introduce', 'goodbye'],
  'pronunciation_focus': "Contractions with be: I'm, you're, he's, she's, it's.",
  'agent_instructions': L001E, 'character_gender': 'male',
  'shared_text': {'kind': 'story', 'title': 'A New Job at the Hotel', 'resource_id': 'TXT-L001-hotel',
    'body': 'It is Monday morning at the Palm Hotel in Orlando. Today is Maria\'s first day. She is the new receptionist. She is from Mexico, and she is a little nervous. Sam is at the reception desk too. He is from Florida. He is friendly and funny. Laura is the manager. She is from New York, and she is very busy. Ben is the man with the bags. He is from Cuba. He is the porter, and he is very strong. "Hello, Maria! I am Sam. Nice to meet you," Sam says. "This is Laura, the manager. And that is Ben." Maria is happy. The people at the hotel are nice.'},
  'picture_waived_reason': 'The story gives the hotel and its people; the learner introduces themselves.',
  'end_condition': {'target_learner_turns': 8, 'max_minutes': 10},
  'resource': {'resource_id': 'PROMPT-L001-S-hotel', 'kind': 'prompt'}})
E['voice_report_exam'] = ('voice_report', {
  'contract': 'voice_report/1', 'session_id': 'S0002', 'student_id': 'student-0001', 'mode': 'exam', 'lesson_id': 'L001',
  'started_at': '2026-10-22T14:52:00-05:00', 'ended_at': '2026-10-22T14:54:00-05:00', 'end_reason': 'time_limit',
  'duration_s': 120, 'audio_deleted_at': '2026-10-22T14:54:40-05:00',
  'transcript': [
    {'n': 1, 'speaker': 'agent', 'text': "Hi! Are you the new receptionist?", 'start_s': 0, 'end_s': 2.5},
    {'n': 2, 'speaker': 'learner', 'text': "Yes. Hello, I'm Carlos. Nice to meet you.", 'start_s': 3.0, 'end_s': 6.2},
    {'n': 3, 'speaker': 'agent', 'text': "Nice to meet you, Carlos. I'm Emma. Who is that?", 'start_s': 6.5, 'end_s': 9.8},
    {'n': 4, 'speaker': 'learner', 'text': "She is Laura. She is the manager.", 'start_s': 10.2, 'end_s': 13.0}],
  'pronunciation_notes': [
    {'turn': 2, 'focus_feature': "I'm /aɪm/", 'achieved': True, 'observation': 'Clear contraction.', 'affects_intelligibility': False},
    {'turn': 4, 'focus_feature': "she's /ʃiz/", 'achieved': False, 'observation': 'Uses full form "She is"; /ʃ/ produced as /s/ once.', 'affects_intelligibility': False}],
  'target_grammar_uses': [{'turn': 2, 'form': "I'm", 'accurate': True}, {'turn': 4, 'form': 'She is', 'accurate': True}, {'turn': 4, 'form': 'She is', 'accurate': True}],
  'priority_vocabulary_used': ['hello', 'meet'], 'errors': [],
  'objectives_met': [{'objective': 'Greet people', 'met': True}, {'objective': 'Say their name', 'met': True}, {'objective': 'Introduce themselves and others', 'met': True}],
  'learner_turns': 2})
E['evidence_package'] = ('evidence_package', {
  'contract': 'evidence_package/1', 'student_id': 'student-0001', 'event_id': 'L001', 'event_type': 'lesson_assessment', 'attempt': 1, 'form_id': 'L001-A',
  'level': 'A1', 'lesson_id': 'L001', 'spec_ref': 'Lesson_Practice_Assessment!L001',
  'rubric_ids': ['RB-LS-01', 'RB-LS-02', 'RB-LS-03', 'RB-LS-04', 'RB-LS-05', 'RB-LW-01', 'RB-LW-02', 'RB-LW-03', 'RB-LW-04'],
  'dimensions_to_score': ['Reading', 'Writing', 'Speaking'],
  "reading": {"resource": {"resource_id": "TXT-L001-R-office", "kind": "text"}, "text": "(unseen dialogue, 60–90 words, generated from Lesson_Practice_Assessment!L001)", "items": [
      {"item_id": "L001-A-R1", "sub_skill": "gist", "question": "Where are the people?", "options": ["At an office", "At a school", "At a store"], "key": "At an office", "learner_answer": "At an office"},
      {"item_id": "L001-A-R2", "sub_skill": "detail", "question": "What is the new worker's name?", "key": "Mia", "accepted_variants": ["Her name is Mia"], "learner_answer": "It's Mia"},
      {"item_id": "L001-A-R3", "sub_skill": "detail", "question": "Where is Mia from?", "options": ["Canada", "Mexico", "Brazil"], "key": "Canada", "learner_answer": "Mexico"},
      {"item_id": "L001-A-R4", "sub_skill": "detail", "question": "Who is Mr. Lee?", "options": ["The manager", "A client", "A teacher"], "key": "The manager", "learner_answer": "The manager"},
      {"item_id": "L001-A-R5", "sub_skill": "detail", "question": "Mia and Sam are friends. True or false?", "options": ["True", "False"], "key": "False", "learner_answer": "False"}]},
  'writing': {'prompt': 'Write a short note (25–40 words) to a new coworker: say hello, your name and introduce a colleague.', 'word_range': [25, 40], 'target_uses': 3,
              'learner_text': "Hello Tom! I'm Carlos, I am the new receptionist. This is Laura. She is the manager. She is from Bogotá. Nice to meet you! See you tomorrow."},
  'speaking': {'voice_session_id': 'S0002', 'voice_report_path': 'voice-sessions/S0002/report.json', 'target_uses': 3, 'channel': 'voice'}})
E['evaluator_scores'] = ('evaluator_scores', {
  'contract': 'evaluator_scores/1', 'student_id': 'student-0001', 'event_id': 'L001', 'attempt': 1, 'form_id': 'L001-A', 'scored_at': '2026-10-22T15:00:00-05:00',
  'dimensions': [
    {'dimension': 'Writing', 'score_pct': 93.75, 'criteria': [
        {'rubric_id': 'RB-LW-01', 'band': 100, 'evidence_quote': "Hello Tom! I'm Carlos", 'justification': 'Correct reader, purpose and length (27 words).'},
        {'rubric_id': 'RB-LW-02', 'band': 100, 'evidence_quote': "I'm / I am / She is", 'justification': '4 accurate uses (target 3).'},
        {'rubric_id': 'RB-LW-03', 'band': 75, 'evidence_quote': 'receptionist', 'justification': 'Entries used correctly, but a narrow range (hello, meet, name).'},
        {'rubric_id': 'RB-LW-04', 'band': 100, 'evidence_quote': 'This is Laura. She is the manager.', 'justification': 'Logical order: greeting, self, colleague, closing.'}]},
    {'dimension': 'Speaking', 'score_pct': 80, 'criteria': [
        {'rubric_id': 'RB-LS-01', 'band': 100, 'evidence_quote': "Hello, I'm Carlos. Nice to meet you.", 'justification': 'All three objectives met.'},
        {'rubric_id': 'RB-LS-02', 'band': 100, 'evidence_quote': 'She is Laura. She is the manager.', 'justification': '3 accurate uses.'},
        {'rubric_id': 'RB-LS-03', 'band': 50, 'evidence_quote': 'hello, meet', 'justification': '2 of 4 priority entries.'},
        {'rubric_id': 'RB-LS-04', 'band': 75, 'evidence_quote': 'turn 4 note', 'justification': "she's not contracted; understood throughout."},
        {'rubric_id': 'RB-LS-05', 'band': 75, 'evidence_quote': 'turns 2 and 4', 'justification': 'Answers well; does not ask questions back.'}]}],
  'item_results': [{'item_id': 'L001-A-R2', 'correct': True, 'note': 'Answered "mia": same word, capital letter not tested.'}],
  'errors_observed': [{'section': '4.1', 'description': 'Avoids contractions with he/she.'}],
  'reinforcement_recommendation': 'Practise asking questions back (And you?) and he’s/she’s contractions.'})
E['decision'] = ('decision', {
  'contract': 'decision/1', 'student_id': 'student-0001', 'event_id': 'L001', 'event_type': 'lesson_assessment', 'cycle': 1, 'attempt': 1, 'global_pct': 84.58,
  'dimension_results': [{'dimension': 'Reading', 'score_pct': 80, 'passed': True}, {'dimension': 'Writing', 'score_pct': 93.75, 'passed': True}, {'dimension': 'Speaking', 'score_pct': 80, 'passed': True}],
  'decision': 'passed', 'failed_dimensions': [], 'attempts_left': 2, 'next_event': 'L002', 'next_lesson': 'L002'})
E['profile'] = ('profile', {'student_id': 'student-0001', 'name': 'Carlos Pérez', 'started_on': '2026-10-22', 'placement_level': 'A1', 'start_lesson': 'L001',
  'recording_consent': {'given': True, 'date': '2026-10-22', 'text_version': 'v1'}, 'interests': ['soccer']})
E['progress'] = ('progress', {'student_id': 'student-0001', 'current_lesson': 'L002', 'current_event': 'L002', 'updated_at': '2026-10-22T15:00:05-05:00',
  'lessons_passed': ['L001'], 'lessons_credited': [], 'checks_passed': [], 'checks_credited': [], 'exits_passed': [], 'exits_credited': [], 'pending': None, 'replacements': []})
E['attempts'] = ('attempts', {'student_id': 'student-0001', 'events': [{'event_id': 'L001', 'event_type': 'lesson_assessment', 'cycle': 1, 'attempts': [
  {'attempt': 1, 'date': '2026-10-22T15:00:00-05:00', 'form_id': 'L001-A', 'resources': [{'resource_id': 'TXT-L001-R-office', 'kind': 'text'}, {'resource_id': 'PROMPT-L001-S-hotel', 'kind': 'prompt'}],
   'scores': {'Reading': 80, 'Writing': 93.75, 'Speaking': 80}, 'global_pct': 84.58, 'decision': 'passed'}]}]})
E['resources'] = ('resources', {'student_id': 'student-0001', 'resources': [
  {'resource_id': 'TXT-L001-R-office', 'kind': 'text', 'uses': [{'event_id': 'L001', 'attempt': 1, 'date': '2026-10-22T14:40:00-05:00', 'item_ids': ['L001-A-R1', 'L001-A-R2', 'L001-A-R3', 'L001-A-R4', 'L001-A-R5']}]}]})
E['vocabulary'] = ('vocabulary', {'student_id': 'student-0001', 'priority_recycling': []})
E['errors'] = ('errors', {'student_id': 'student-0001', 'by_section': {'4.1': {'count': 2, 'last_seen': '2026-10-22', 'examples': ['Is Ana. → She is Ana.']}}})

E['preferences'] = ('preferences', {'student_id': 'student-0001', 'preferences': [
  {'id': 'PR001', 'category': 'activity_format', 'text': 'Use clickable options (AskUserQuestion) for closed items whenever possible.', 'source_quote': 'Can you make the test more interactive? With checkboxes or lists.', 'created_on': '2026-10-22', 'event_id': 'L001', 'status': 'active'},
  {'id': 'PR002', 'category': 'example_topics', 'text': 'Use examples about technology and data work when the lesson situation allows it.', 'source_quote': "I'm a data engineer.", 'created_on': '2026-10-22', 'event_id': 'L001', 'status': 'active'}]})

# ---------- write + validate
ok = True
for n, s in S.items():
    Draft202012Validator.check_schema(s)
    json.dump(s, open(f'{OUT}/schemas/{n}.schema.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
for n, (sn, ex) in E.items():
    errs = list(Draft202012Validator(S[sn], format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(ex))
    if errs: ok = False; print('INVALID', n, [e.message for e in errs[:3]])
    json.dump(ex, open(f'{OUT}/examples/{n}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
# negative tests
neg = [('voice_brief', {k: v for k, v in E['voice_brief_exam'][1].items() if k != 'attempt'}), ('decision', dict(E['decision'][1], decision='approved')),
       ('evaluator_scores', {**E['evaluator_scores'][1], 'dimensions': [{'dimension': 'Writing', 'score_pct': 90, 'criteria': [{'rubric_id': 'RB-LW-01', 'band': 80, 'evidence_quote': 'x', 'justification': 'y'}]}]})]
for sn, ex in neg:
    if Draft202012Validator(S[sn]).is_valid(ex): ok = False; print('NEGATIVE TEST PASSED WRONGLY', sn)
# arithmetic check of the decision example
sc = [80] + [d['score_pct'] for d in E['evaluator_scores'][1]['dimensions']]   # Reading 4/5 is counted by the engine from the evidence
assert abs(sum(sc) / len(sc) - E['decision'][1]['global_pct']) < 0.01
for d in E['evaluator_scores'][1]['dimensions']:
    if 'criteria' in d:
        assert abs(sum(c['band'] for c in d['criteria']) / len(d['criteria']) - d['score_pct']) < 0.01, d['dimension']
print('schemas', len(S), 'examples', len(E), 'ALL OK' if ok else 'ERRORS')
