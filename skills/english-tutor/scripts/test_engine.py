#!/usr/bin/env python3
"""Engine tests (engine.py). Usage: python3 test_engine.py  → OK/FAIL per scenario."""
import json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENG = [sys.executable, os.path.join(HERE, 'engine.py')]
sys.path.insert(0, HERE)
import curriculum as C  # noqa
FAILS, DIRS = [], []


def run(*args, ok=True):
    r = subprocess.run(ENG + list(args), capture_output=True, text=True)
    out = json.loads(r.stdout) if r.stdout.strip() else {}
    if ok and ('error' in out or r.returncode):
        raise AssertionError(f'{args[0]} failed: {r.stdout} {r.stderr}')
    return out


def check(name, cond, info=''):
    print(('OK   ' if cond else 'FAIL ') + name + (f'  [{info}]' if not cond and info != '' else ''))
    if not cond: FAILS.append(name)


def jw(d, name, obj):
    p = os.path.join(d, name); json.dump(obj, open(p, 'w', encoding='utf-8'), ensure_ascii=False); return p


def jr(d, name):
    return json.load(open(os.path.join(d, name), encoding='utf-8'))


N = [0]


def uid(prefix):
    N[0] += 1; return f'{prefix}{N[0]}'


def level_of(eid):
    if eid in C.lessons(): return C.lessons()[eid]['Level']
    m = re.match(r'(?:EXIT|ULC)-([A-C][12])', eid)
    return m.group(1) if m else 'A1'


def scores(eid, dims, extra=None, sid='student-0001', level=None):
    """Item dimensions as (correct, total); rubric dimensions as a list of bands, mapped to the real rubric rows of the level."""
    D = []; lv = level or level_of(eid); kind = 'exit' if eid.startswith(('EXIT', 'PLACEMENT')) else 'lesson'
    for k, v in dims.items():
        if isinstance(v, tuple):
            D.append({'dimension': k, 'score_pct': 100 * v[0] / v[1], 'items_correct': v[0], 'items_total': v[1]})
        else:
            ids = [r['Rubric ID'] for r in C.rubrics(lv, kind)['rubrics'] if r['Skill'] == k]
            if len(v) != len(ids):
                assert len(set(v)) == 1, (k, v, ids); v = [v[0]] * len(ids)
            D.append({'dimension': k, 'score_pct': sum(v) / len(v), 'criteria': [{'rubric_id': i, 'band': b, 'evidence_quote': 'q', 'justification': 'j'} for i, b in zip(ids, v)]})
    s = {'contract': 'evaluator_scores/1', 'student_id': sid, 'event_id': eid, 'attempt': 1, 'scored_at': '2026-10-22T10:00:00-05:00', 'dimensions': D}
    if extra: s.update(extra)
    return s


def evidence(eid, etype, level=None, att=1, res=None, items_ids=None, speak_res=None):
    e = {'contract': 'evidence_package/1', 'student_id': 'student-0001', 'event_id': eid, 'event_type': etype, 'attempt': att, 'level': level or level_of(eid),
         'spec_ref': f'X!{eid}', 'dimensions_to_score': ['Reading']}
    if res:
        e['reading'] = {'resource': {'resource_id': res, 'kind': 'text'}, 'items': [{'item_id': i, 'question': 'q', 'key': 'k', 'learner_answer': 'k'} for i in (items_ids or ['i1'])]}
    if speak_res:
        e['speaking'] = {'resource': {'resource_id': speak_res, 'kind': 'prompt'}, 'voice_session_id': 'S0001', 'voice_report_path': 'voice-sessions/S0001/report.json'}
    return e


def items(plan, first=()):
    """plan: [(sub_skill | None, correct?)] → closed items the engine can count; the first ids are kept."""
    out = []
    for n, (sub, ok) in enumerate(plan):
        it = {'item_id': first[n] if n < len(first) else uid('it'), 'question': 'q', 'options': ['k', 'x'], 'key': 'k', 'learner_answer': 'k' if ok else 'x'}
        if sub: it['sub_skill'] = sub
        out.append(it)
    return out


def fill(ev, sc):
    """Puts in the evidence the items that give the counts written in the scores (the engine counts items from the evidence)."""
    ev['spec_ref'] = uid('X!')   # every package is different (the engine rejects a package scored twice)
    for d in sc.get('dimensions', []):
        if 'items_total' not in d: continue
        blk = d['dimension'].lower(); old = ev.get(blk) or {}
        plan = [(x['sub_skill'], i < x['correct']) for x in d['subskills'] for i in range(x['total'])] if d.get('subskills') else [(None, i < d['items_correct']) for i in range(d['items_total'])]
        nb = {'items': items(plan, [i['item_id'] for i in old.get('items', []) if not i['item_id'].startswith('it')])}   # ids chosen by the test are kept
        if blk == 'reading': nb['resource'] = old.get('resource') or {'resource_id': uid('TXT-auto-'), 'kind': 'text'}
        if blk == 'listening': nb['source_id'] = old.get('source_id') or uid('LS-auto-')
        ev[blk] = nb
    return ev


def score(d, ev, sc, ok=True):
    return run('score', '--state', d, '--evidence', jw(d, 'e.json', fill(ev, sc)), '--scores', jw(d, 's.json', sc), ok=ok)


def pev(dims, wrong_section=None, level='A1'):
    """Placement evidence: closed items by dimension; the wrong grammar items carry wrong_section."""
    e = {'contract': 'evidence_package/1', 'student_id': 'student-0001', 'event_id': 'PLACEMENT', 'event_type': 'placement_stage1', 'attempt': 1, 'level': level,
         'spec_ref': uid('PT!'), 'dimensions_to_score': list(dims)}
    for k, (c, t) in dims.items():
        its = items([(None, i < c) for i in range(t)])
        if k == 'Grammar' and wrong_section:
            for it in its:
                if it['learner_answer'] != it['key']: it['section'] = wrong_section
        e[k.lower()] = {'items': its, **({'resource': {'resource_id': uid('TXT-PT-'), 'kind': 'text'}} if k == 'Reading' else {})}
    return e


def set_current(d, eid):
    p = jr(d, 'progress.json'); p['current_event'] = eid; p['current_lesson'] = eid if eid.startswith('L') else p['current_lesson']; p['pending'] = None
    jw(d, 'progress.json', p)


def new_state():
    d = tempfile.mkdtemp(); DIRS.append(d)
    run('init', '--state', d, '--student', 'student-0001', '--name', 'Test')
    return d


def placement_walk(d, level_truth, ws_pass, unit_truth):
    out = run('placement', '--state', d); nprobe = 0
    while out['next_action']['action'] != 'done':
        a = out['next_action']
        if a['action'] == 'probe_level':
            m = a['level'] in level_truth
            args = ['--evidence', jw(d, 'e.json', pev({'Grammar': (4, 4) if m else (1, 4), 'Vocabulary': (4, 4) if m else (2, 4), 'Reading': (2, 2) if m else (1, 2)}, wrong_section='7.3'))]
        elif a['action'] == 'writing_speaking':
            args = ['--scores', jw(d, 's.json', scores('PLACEMENT', {'Writing': [100, 75, 75, 75] if ws_pass else [50, 50, 50, 25], 'Speaking': [75] * 5 if ws_pass else [50] * 5}, level=a['level']))]
        else:
            nprobe += 1; m = unit_truth(a['index'])
            args = ['--evidence', jw(d, 'e.json', pev({'Grammar': (5, 5) if m else (2, 5), 'Vocabulary': (6, 6) if m else (3, 6)}))]
            if nprobe == 1:   # what the scoring agent adds (open items): joined with what the engine finds
                args += ['--scores', jw(d, 's.json', {'contract': 'evaluator_scores/1', 'student_id': 'student-0001', 'event_id': 'PLACEMENT', 'attempt': 1, 'scored_at': '2026-10-22T10:00:00-05:00',
                                                      'failed_vocabulary': [473], 'errors_observed': [{'section': '4.1', 'description': 'is/are'}]})]
        out = run('placement', '--state', d, *args)
    return out['next_action'], nprobe


PASS3 = {'Reading': (5, 5), 'Writing': [100] * 4, 'Speaking': [100] * 5}

# ---------------- consent
d0 = new_state()
check('C1 consent never asked → ask_consent', run('status', '--state', d0)['ask_consent'] is True)
run('consent', '--state', d0, '--given', 'no')
st = run('status', '--state', d0)
check('C1 declined: not asked again and no voice', st['ask_consent'] is False and st['voice_allowed'] is False, st)

# ---------------- T1 placement A2 up to unit 4
d = new_state()
res, n = placement_walk(d, {'A1'}, True, lambda i: i < 4)
u = C.content_units('A2'); lastprev = max(C.seq(x['lesson_id']) for x in C.unit(u[3])['lessons'])
check('T1 start = lesson after the last mastered unit', C.seq(res['start_lesson']) == lastprev + 1, res['start_lesson'])
check('T1 unit probes ≤ 6', n <= 6, n)
pr = jr(d, 'progress.json')
check('T1 EXIT-A1 credited', pr['exits_credited'] == ['EXIT-A1'])
check('T1 earlier lessons credited', len(pr['lessons_credited']) == C.seq(res['start_lesson']) - 1)
check('T1 reinforcement only with credited sections (no 7.3)', '7.3' not in pr['pending']['sections'] and '4.1' in pr['pending']['sections'], pr['pending'])
check('T1 failed word (from a credited lesson) recorded', any(v['oxford_id'] == 473 for v in jr(d, 'vocabulary.json')['priority_recycling']))
out = run('reinforced', '--state', d)
check('T1 reinforcement closed without moving the lesson', jr(d, 'progress.json')['pending'] is None and out['next_event'] == res['start_lesson'])
check('T1 reinforcement cannot be closed twice', 'error' in run('reinforced', '--state', d, ok=False))

# ---------------- T1b placement A2 with no unit mastered → first A2 lesson
d1b = new_state()
res, _ = placement_walk(d1b, {'A1'}, True, lambda i: False)
first_a2 = sorted([l for l, r in C.lessons().items() if r['Level'] == 'A2'], key=C.seq)[0]
check('T1b no unit mastered → first lesson of the level', res['start_lesson'] == first_a2, (res['start_lesson'], first_a2))

# ---------------- T2 W/S < 70 drops to A1; all mastered → A1 final review
d2 = new_state()
res2, _ = placement_walk(d2, {'A1'}, False, lambda i: True)
check('T2 W/S < 70 → A1, all mastered → L068', res2['placement_level'] == 'A1' and res2['start_lesson'] == 'L068', res2)

# ---------------- T3 lesson
d3 = new_state(); placement_walk(d3, set(), False, lambda i: False); run('reinforced', '--state', d3)
check('T3 beginner starts at L001', run('status', '--state', d3)['current_event'] == 'L001')
dec = score(d3, evidence('L001', 'lesson_assessment', res='TXT-1', items_ids=['a1']), scores('L001', {'Reading': (4, 5), 'Writing': [100, 100, 75, 100], 'Speaking': [100, 100, 50, 75, 75]}))['decision']
check('T3 passes L001 with 84.58 → L002', dec['decision'] == 'passed' and dec['global_pct'] == 84.58 and dec['next_event'] == 'L002', dec)
dec = score(d3, evidence('L002', 'lesson_assessment'), scores('L002', {'Reading': (5, 5), 'Writing': [100] * 4, 'Speaking': [50] * 5}))['decision']
check('T3 global ≥80 with Speaking 50 → retest', dec['decision'] == 'retest_pending' and dec['retest_dimensions'] == ['Speaking'], dec)
at = run('attempt', '--state', d3, '--event', 'L002', '--type', 'lesson_assessment')
check('T3 attempt 2: Speaking only', at['attempt'] == 2 and at['dimensions_to_score'] == ['Speaking'], at)
dec = score(d3, evidence('L002', 'lesson_assessment', att=2), scores('L002', {'Reading': (0, 5), 'Speaking': [50] * 5}))['decision']
check('T3 P09: extra Reading is ignored', dec['dimension_results'][0]['score_pct'] == 100 and any('P09' in n for n in dec['notes']), dec)
dec = score(d3, evidence('L002', 'lesson_assessment', att=3), scores('L002', {'Speaking': [50] * 5}))['decision']
check('T3 third failure → repeat L002', dec['decision'] == 'repeat_content' and dec['repeat_lessons'] == ['L002'], dec)
at = run('attempt', '--state', d3, '--event', 'L002', '--type', 'lesson_assessment')
check('T3 cycle 2, attempt 1, all dimensions', at['cycle'] == 2 and at['attempt'] == 1 and len(at['dimensions_to_score']) == 3, at)
dec = score(d3, evidence('L002', 'lesson_assessment'), scores('L002', PASS3))['decision']
check('T3 cycle 2 passes and clears the pending item', dec['decision'] == 'passed' and jr(d3, 'progress.json')['pending'] is None, dec)

# ---------------- R1 all ≥70 but global <80
dec = score(d3, evidence('L003', 'lesson_assessment'), scores('L003', {'Reading': (4, 5), 'Writing': [75] * 4, 'Speaking': [75] * 5}))['decision']
at = run('attempt', '--state', d3, '--event', 'L003', '--type', 'lesson_assessment')
check('R1 global 76.67 with no dimension <70 → reassess those <80', dec['decision'] == 'retest_pending' and at['dimensions_to_score'] == ['Writing', 'Speaking'] and 'Reading' in at['kept_scores'], (dec, at))
dec = score(d3, evidence('L003', 'lesson_assessment', att=2), scores('L003', {'Writing': [100] * 4, 'Speaking': [100] * 5}))['decision']
check('R1 retest raises the mean and passes', dec['decision'] == 'passed', dec)

# ---------------- T4 resources (reading and Speaking prompt)
for k in range(3):
    sc = scores('L004', PASS3 if k == 0 else {'Reading': (1, 5)}); sc['dimensions'][0].update(items_correct=1, score_pct=20)
    score(d3, evidence('L004', 'lesson_assessment', res='TXT-X', items_ids=[f'x{k}'], speak_res='PROMPT-L004-S-hotel' if k == 0 else None), sc)
r = run('resource', '--state', d3, '--id', 'TXT-X')
check('T4 after 3 uses it cannot be used', r['uses'] == 3 and not r['can_use'], r)
out = score(d3, evidence('L004', 'lesson_assessment', res='TXT-X', items_ids=['x9']), scores('L004', PASS3), ok=False)
check('T4 fourth use rejected', 'P08' in out.get('error', ''), out)
check('R7 the Speaking prompt counts as a resource', run('resource', '--state', d3, '--id', 'PROMPT-L004-S-hotel')['uses'] == 1)
score(d3, evidence('L004', 'lesson_assessment', res='TXT-Z', items_ids=['z1']), scores('L004', PASS3))
set_current(d3, 'L005')
score(d3, evidence('L005', 'lesson_assessment', res='TXT-Z', items_ids=['z2']), scores('L005', {'Reading': (1, 5), 'Writing': [100] * 4, 'Speaking': [100] * 5}))
out = score(d3, evidence('L005', 'lesson_assessment', res='TXT-Z', items_ids=['z1']), scores('L005', {'Reading': (1, 5)}), ok=False)
check('T4 repeated item rejected', 'z1' in out.get('error', ''), out)

# ---------------- R6 wrong event / wrong type
out = score(d3, evidence('L300', 'lesson_assessment'), scores('L300', PASS3), ok=False)
check('R6 scoring a lesson that is not current → rejected', 'is not the current event' in out.get('error', ''), out)
out = score(d3, evidence('L005', 'level_exit'), scores('L005', PASS3), ok=False)
check('R6 wrong event type → rejected', 'cannot be scored as' in out.get('error', ''), out)

# ---------------- T5 / R2 listening
d5 = new_state(); placement_walk(d5, set(), False, lambda i: False); set_current(d5, 'ULC-A1-U01')
ls = {'dimension': 'Listening', 'score_pct': 80, 'items_correct': 8, 'items_total': 10,
      'subskills': [{'sub_skill': 'gist', 'correct': 2, 'total': 2}, {'sub_skill': 'detail', 'correct': 2, 'total': 4}, {'sub_skill': 'inference', 'correct': 4, 'total': 4}]}
S = {'contract': 'evaluator_scores/1', 'student_id': 'student-0001', 'event_id': 'ULC-A1-U01', 'attempt': 1, 'scored_at': '2026-10-22T10:00:00-05:00', 'dimensions': [ls]}
E = evidence('ULC-A1-U01', 'unit_listening_check'); E['listening'] = {'source_id': 'LS-A1-01', 'items': [{'item_id': 'l1', 'question': 'q', 'key': 'k', 'learner_answer': 'k'}]}
dec = score(d5, E, S)['decision']
at = run('attempt', '--state', d5, '--event', 'ULC-A1-U01', '--type', 'unit_listening_check')
check('T5 detail 2/4 → fails although global is 80', dec['decision'] == 'retest_pending', dec)
check('R2 the retest reassesses Listening', at['dimensions_to_score'] == ['Listening'], at)
ls['subskills'] = [{'sub_skill': 'gist', 'correct': 1, 'total': 2}, {'sub_skill': 'detail', 'correct': 3, 'total': 4}, {'sub_skill': 'inference', 'correct': 4, 'total': 4}]
E['listening']['items'][0]['item_id'] = 'l2'
dec = score(d5, E, S)['decision']
check('T5 gist 1/2 does not block → passes, next L006', dec['decision'] == 'passed' and dec['next_event'] == 'L006', dec)

# ---------------- R13 listening: third failure → listening session → new cycle
set_current(d5, 'ULC-A1-U02'); ls['subskills'][1] = {'sub_skill': 'detail', 'correct': 1, 'total': 4}
for k in range(3):
    E = evidence('ULC-A1-U02', 'unit_listening_check'); E['listening'] = {'source_id': f'LS-X-0{k}', 'items': [{'item_id': f'm{k}', 'question': 'q', 'key': 'k', 'learner_answer': 'k'}]}
    S['event_id'] = 'ULC-A1-U02'; dec = score(d5, E, S)['decision']
check('R13 third failure → listening session', dec['decision'] == 'repeat_content' and dec.get('listening_session'), dec)
run('repeated', '--state', d5)
check('R13 after the session: pending "repeated" and new cycle', jr(d5, 'progress.json')['pending']['status'] == 'repeated' and run('attempt', '--state', d5, '--event', 'ULC-A1-U02', '--type', 'unit_listening_check')['cycle'] == 2)

# ---------------- T6 / R3 level exit
d6 = new_state(); placement_walk(d6, set(), False, lambda i: False); set_current(d6, 'EXIT-A1')
for k in range(1, 4):
    S = scores('EXIT-A1', {'Reading': (12, 12), 'Listening': (10, 10), 'Writing': [100] * 4, 'Speaking': [50] * 5} if k == 1 else {'Speaking': [50] * 5},
               extra={'sections': [{'section': '4.6', 'score_pct': 40}, {'section': '4.1', 'score_pct': 90}]})
    dec = score(d6, evidence('EXIT-A1', 'level_exit', att=k), S)['decision']
want = [l for l in sorted(C.lessons(), key=C.seq) if C.lessons()[l]['Level'] == 'A1' and C.lessons()[l]['Lesson type'] in ('Core', 'Application') and '4.6' in C.SEC.findall(C.lessons()[l]['Grammar section'])]
check('T6 repeat the lessons of 4.6', dec['decision'] == 'repeat_content' and dec['repeat_lessons'] == want, (dec.get('repeat_lessons'), want))
for l in want:
    dec = score(d6, evidence(l, 'lesson_assessment'), scores(l, PASS3))['decision']
check('R3 after repeating all lessons, back to EXIT-A1', dec['next_event'] == 'EXIT-A1' and jr(d6, 'progress.json')['pending']['status'] == 'repeated', dec)
dec = score(d6, evidence('EXIT-A1', 'level_exit'), scores('EXIT-A1', {'Reading': (12, 12), 'Listening': (10, 10), 'Writing': [100] * 4, 'Speaking': [100] * 5}))['decision']
check('R3 exit passes in cycle 2 → level A2', dec['decision'] == 'passed' and dec['cycle'] == 2 and C.lessons()[dec['next_lesson']]['Level'] == 'A2', dec)

# ---------------- T7 diagnostic, R4 embedded check, T8
set_current(d6, 'L400')
S = scores('L400', {'Reading': (3, 5), 'Writing': [75] * 4, 'Speaking': [75] * 5}, extra={'sections': [{'section': '4.2', 'score_pct': 50}, {'section': '4.1', 'score_pct': 100}]})
dec = score(d6, evidence('L400', 'review_diagnostic'), S)['decision']
check('T7 diagnostic flags 4.2 and it is stored in the state', dec['decision'] == 'diagnosed' and dec['flagged_sections'] == ['4.2'] and jr(d6, 'progress.json')['pending']['sections'] == ['4.2'], dec)
emb = C.embedded('L400')['check']['Check ID']
S2 = {'contract': 'evaluator_scores/1', 'student_id': 'student-0001', 'event_id': emb, 'attempt': 1, 'scored_at': '2026-10-22T10:00:00-05:00', 'dimensions': [{'dimension': 'Listening', 'score_pct': 100, 'items_correct': 6, 'items_total': 6}]}
p = jr(d6, 'progress.json'); p['current_event'] = emb; jw(d6, 'progress.json', p)
out = score(d6, evidence(emb, 'unit_listening_check'), S2, ok=False)
check('R4 embedded check before its lesson is passed → rejected', 'only after its lesson' in out.get('error', ''), out)
p['current_event'] = 'L400'; jw(d6, 'progress.json', p)
dec = score(d6, evidence('L400', 'review_assessment'), scores('L400', PASS3))['decision']
check('T8 after passing L400 its embedded check is next', dec['next_event'] == emb, dec)
dec = score(d6, evidence(emb, 'unit_listening_check'), S2)['decision']
check('T8 after the check, what follows L400 is next', dec['next_event'] == C.next_event('L400')['Event ID'], dec)

# ---------------- R8 level final review does not block
set_current(d6, 'L068')
dec = score(d6, evidence('L068', 'review_assessment'), scores('L068', {'Reading': (1, 5), 'Writing': [50] * 4, 'Speaking': [50] * 5}, extra={'sections': [{'section': '4.3', 'score_pct': 20}]}))['decision']
check('R8 final review with low scores → moves on (exit or its check), no retest', dec['decision'] == 'diagnosed' and dec['next_event'].startswith(('EXIT-A1', 'ULC-')) and jr(d6, 'progress.json')['pending'] is None, dec)

# ---------------- T9 wrong total
set_current(d3, 'L006')
S = scores('L006', PASS3); S['dimensions'][1]['score_pct'] = 60
dec = score(d3, evidence('L006', 'lesson_assessment'), S)['decision']
check('T9 the engine recalculates a wrong total', dec['decision'] == 'passed' and any('recalculated' in n for n in dec.get('notes', [])), dec)

# ---------------- T10 re-placement, R9 end of course, R12 consistency
run('replace', '--state', d3, '--to', 'L020', '--evidence', '≥95% in the first lessons')
pr = jr(d3, 'progress.json')
check('T10 re-placement to L020', pr['current_lesson'] == 'L020' and 'L010' in pr['lessons_credited'] and 'L001' not in pr['lessons_credited'])
check('T10 invalid target → JSON error', 'error' in run('replace', '--state', d3, '--to', 'EXIT-A1', '--evidence', 'x', ok=False))
pr['exits_passed'].append('EXIT-C1'); jw(d3, 'progress.json', pr)
check('R9 EXIT-C1 passed → course_complete', run('status', '--state', d3)['status'] == 'course_complete')
pr['exits_passed'].remove('EXIT-C1'); pr['state_rev'] = 1; jw(d3, 'progress.json', pr)
st = run('status', '--state', d3)
check('R12 progress older than the rest → incomplete upload warning', 'warning' in st and not st['consistency']['complete'], st)

# ---------------- P1 learner preferences (HOW, never WHAT)
dp = new_state()
check('P1 new learner has an empty preferences file', jr(dp, 'preferences.json')['preferences'] == [])
out = run('pref-add', '--state', dp, '--category', 'activity_format', '--affects', 'formative', '--text', 'Use clickable options for closed items.', '--quote', 'Can you make the test more interactive?', '--event', 'L001')
check('P1 HOW preference stored as PR001', out['added']['id'] == 'PR001' and run('prefs', '--state', dp)['active'][0]['id'] == 'PR001', out)
out = run('pref-add', '--state', dp, '--category', 'grammar', '--affects', 'formative', '--text', 'Teach phrasal verbs now.', '--quote', 'I want phrasal verbs', ok=False)
check('P1 category outside HOW → rejected', 'category not allowed' in out.get('error', ''), out)
out = run('pref-add', '--state', dp, '--category', 'pace', '--affects', 'assessment', '--text', 'Skip the writing test.', '--quote', 'I do not like writing', ok=False)
check('P1 suggestion that changes WHAT is assessed → rejected', 'WHAT' in out.get('error', ''), out)
out = run('pref-add', '--state', dp, '--category', 'activity_format', '--affects', 'formative', '--text', 'Use clickable options for closed items.', '--quote', 'again', ok=False)
check('P1 duplicate preference → rejected', 'already active' in out.get('error', ''), out)
for k in range(7):
    run('pref-add', '--state', dp, '--category', 'example_topics', '--affects', 'formative', '--text', f'Use examples about topic number {k}.', '--quote', f'topic {k}')
out = run('pref-add', '--state', dp, '--category', 'pace', '--affects', 'formative', '--text', 'Shorter explanations, please.', '--quote', 'too long', ok=False)
check('P1 maximum of 8 active preferences', 'retire one first' in out.get('error', ''), out)
run('pref-retire', '--state', dp, '--id', 'PR002')
out = run('pref-add', '--state', dp, '--category', 'pace', '--affects', 'formative', '--text', 'Shorter explanations, please.', '--quote', 'too long')
check('P1 after retiring one, a new one fits (PR009)', out['added']['id'] == 'PR009' and len(run('prefs', '--state', dp)['active']) == 8, out)
check('P1 preferences take part in the state consistency check', 'preferences' in run('status', '--state', dp)['consistency']['state_revs'])
w = run('pref-add', '--state', d3, '--category', 'pace', '--affects', 'formative', '--text', 'Go a little slower in explanations.', '--quote', 'slower, please')['write']
check('P1 a preference write also rewrites progress.json, listed last', w == ['preferences.json', 'progress.json'], w)
st = run('status', '--state', d3)
check('P1 after a preference write there is no false incomplete-upload warning', st['consistency']['complete'] and 'warning' not in st, st)

# ---------------- B1 backup file (self-study without a Claude project)
bk = os.path.join(tempfile.mkdtemp(), 'backup.json')
os.makedirs(os.path.join(dp, 'notes'), exist_ok=True); open(os.path.join(dp, 'notes', '2026-10-22_L001.md'), 'w').write('Note.')
run('export', '--state', dp, '--out', bk)
dr = new_state() + '-restored'
out = run('import', '--file', bk, '--state', dr)
check('B1 export + import restores every file, notes included', sorted(os.listdir(dr)) == sorted(os.listdir(dp)) and os.path.exists(os.path.join(dr, 'notes', '2026-10-22_L001.md')), os.listdir(dr))
check('B1 restored state is consistent and preferences survive', run('status', '--state', dr)['consistency'] == run('status', '--state', dp)['consistency'], out)
json.dump({'contract': 'state_backup/1', 'files': {'profile.json': '{}', '../evil.json': '{}'}}, open(bk, 'w'))
check('B1 a backup with unsafe paths is rejected', 'unsafe' in run('import', '--file', bk, '--state', dr, ok=False).get('error', ''))
DIRS.append(dr)

# ---------------- V1 voice brief: the tutor writes the Gemini instructions
EX = os.path.join(os.path.dirname(HERE), 'examples')
vd = tempfile.mkdtemp(); DIRS.append(vd)
bp = json.load(open(os.path.join(EX, 'voice_brief_practice.json'), encoding='utf-8'))
be = json.load(open(os.path.join(EX, 'voice_brief_exam.json'), encoding='utf-8'))
check('V1 code for a practice brief with tutor instructions', run('voice-code', '--brief', jw(vd, 'p.json', bp))['code'].startswith('EC2-'))
check('V1 code for an exam brief', run('voice-code', '--brief', jw(vd, 'e.json', be))['code'].startswith('EC2-'))
nb = dict(bp); nb.pop('agent_instructions')
check('V1 brief without agent_instructions is rejected', 'error' in run('voice-code', '--brief', jw(vd, 'n.json', nb), ok=False))
check('V1 instructions over 6000 characters are rejected', 'error' in run('voice-code', '--brief', jw(vd, 'l.json', dict(bp, agent_instructions=bp['agent_instructions'] + 'x' * 6000)), ok=False))
check('V1 instructions with the technical block are rejected', 'technical' in run('voice-code', '--brief', jw(vd, 't.json', dict(bp, agent_instructions=bp['agent_instructions'] + ' Call end_conversation.')), ok=False).get('error', ''))
check('V1 instructions must quote the visible situation', 'situation' in run('voice-code', '--brief', jw(vd, 's.json', dict(bp, agent_instructions=bp['agent_instructions'].replace(bp['visible_to_learner']['situation'][:40], 'X'))), ok=False).get('error', ''))
check('V1 exam brief with learner notes is rejected', 'learner_notes' in run('voice-code', '--brief', jw(vd, 'en.json', dict(be, learner_notes=['likes soccer'])), ok=False).get('error', ''))
check('G an invited learner question must be a hidden objective', 'hidden_objectives' in run('voice-code', '--brief', jw(vd, 'gq.json', dict(be, hidden_objectives=['Greet people'])), ok=False).get('error', ''))
TXT = ('Maria is a nurse in Miami. Every morning she takes the bus to the hospital at six. One day the bus is late, and a man next to her '
       'is very nervous. He is a new teacher, and it is his first day at a big school. Maria talks to him, and they laugh. The bus comes, '
       'and they sit together. At the school door, the man says thank you. Now they are friends. Every morning they talk on the bus about '
       'their work, their families and their city. Maria is happy, because the bus is not boring now.')
st = {'kind': 'story', 'title': 'The Late Bus', 'body': TXT}
check('TX practice with a shared text gets a code', run('voice-code', '--brief', jw(vd, 'tx.json', dict(bp, shared_text=st)))['code'].startswith('EC2-'))
check('TX an exam with a shared text gets a code', run('voice-code', '--brief', jw(vd, 'txe.json', dict(be, shared_text=st)))['code'].startswith('EC2-'))
check('TX a brief without a shared text is rejected', 'shared_text' in json.dumps(run('voice-code', '--brief', jw(vd, 'txn.json', {k: v for k, v in bp.items() if k != 'shared_text'}), ok=False)))
check('LEN a practice with the old turns is rejected', 'target_learner_turns 18' in run('voice-code', '--brief', jw(vd, 'len1.json', dict(bp, end_condition={'target_learner_turns': 6, 'max_minutes': 15})), ok=False).get('error', ''))
check('LEN an exam with the practice turns is rejected', 'target_learner_turns 8' in run('voice-code', '--brief', jw(vd, 'len2.json', dict(be, end_condition={'target_learner_turns': 14, 'max_minutes': 12})), ok=False).get('error', ''))
check('TX a text too long for the level is rejected', 'words' in run('voice-code', '--brief', jw(vd, 'txl.json', dict(bp, shared_text=dict(st, body=TXT + ' ' + TXT))), ok=False).get('error', ''))
check('TX the text must not be pasted into the instructions', 'must not paste' in run('voice-code', '--brief', jw(vd, 'txp.json', dict(bp, shared_text=st, agent_instructions=bp['agent_instructions'] + ' ' + TXT)), ok=False).get('error', ''))
check('VO a brief without character_gender is rejected', 'character_gender' in json.dumps(run('voice-code', '--brief', jw(vd, 'vo.json', {k: v for k, v in bp.items() if k != 'character_gender'}), ok=False)))
check('V1 old contract voice_brief/1 is rejected', 'error' in run('voice-code', '--brief', jw(vd, 'o.json', dict(bp, contract='voice_brief/1')), ok=False))

# ---------------- PIC pictures (templates)
import base64, zlib
sys.path.insert(0, HERE); import picture as PIC
pic = {'template': 'people', 'title': 'Family photos', 'people': [{'name': 'Lucy', 'age': 'baby', 'sex': 'female', 'label': "Rosa's baby"}, {'name': 'George', 'age': 'older', 'sex': 'male'}]}
svg, desc = PIC.render(pic)
check('PIC a template draws an SVG and an English description', svg.startswith('<svg') and 'Lucy' in desc and "Rosa's baby" in desc, desc)
for t, sp in [('home', {'rooms': [{'name': 'bedroom', 'count': 2}]}), ('schedule', {'items': [{'time': '6:30', 'label': 'wake up'}]}), ('board', {'notes': ['Clue'], 'notes_reason': 'Abstract clues with times: nothing to draw.'}), ('card', {'items': [{'name': 'tea', 'price': '$2'}]})]:
    check(f'PIC template {t} renders', PIC.render(dict(sp, template=t))[0].startswith('<svg'))
pic2 = {'template': 'card', 'title': 'Menu', 'items': [{'name': 'tea', 'price': '$2'}]}; desc2 = PIC.render(pic2)[1]
bpic = dict(bp, pictures=[pic, pic2], agent_instructions=bp['agent_instructions'] + ' PICTURE 1: ' + desc + ' PICTURE 2: ' + desc2)
out = run('voice-code', '--brief', jw(vd, 'pic.json', bpic))
d = zlib.decompressobj(-15); payload = json.loads(d.decompress(base64.urlsafe_b64decode(out['code'][4:] + '=' * (-len(out['code'][4:]) % 4))))
check('PIC the code carries both drawings for the page', len(payload.get('picture_svgs', [])) == 2 and all(x.startswith('<svg') for x in payload['picture_svgs']))
check('PIC instructions without the picture description are rejected', 'description' in run('voice-code', '--brief', jw(vd, 'pic2.json', dict(bp, pictures=[pic])), ok=False).get('error', ''))
check('PIC unknown template is rejected', 'error' in run('voice-code', '--brief', jw(vd, 'pic3.json', dict(bp, pictures=[{'template': 'castle'}])), ok=False))

check('PIC four pictures are rejected (max 3)', 'error' in run('voice-code', '--brief', jw(vd, 'pic4.json', dict(bpic, pictures=[pic] * 4)), ok=False))
check('EX an exam brief without target_learner_turns is rejected', 'target_learner_turns' in run('voice-code', '--brief', jw(vd, 'ex1.json', dict(be, end_condition={'max_minutes': 10})), ok=False).get('error', ''))

check('PIC icons template renders with key words', PIC.render({'template': 'icons', 'title': 'News', 'items': [{'icon': 'storm', 'label': 'Hurricane Lina', 'extra': 'Port Clara · winds'}]})[0].startswith('<svg'))
for bad, why in [({'template': 'board', 'notes': ['The river has flooded']}, 'verb'), ({'template': 'card', 'items': [{'name': 'a very nice big new red cotton shirt'}]}, 'words'), ({'template': 'icons', 'items': [{'icon': 'castle', 'label': 'x'}]}, 'icon')]:
    try: PIC.render(bad); ok = False
    except ValueError as e: ok = why in str(e)
    check(f'PIC picture rejected ({why}): sentences, long texts or unknown icons', ok)
dr = {'template': 'drawing', 'title': 'Map of Lakeview', 'height': 520, 'svg': "<rect x='20' y='60' width='720' height='440' rx='12' fill='#e9f2e1'/><path d='M560 60 H740 V500 H600 Q520 420 560 330 Q610 240 540 160 Q520 100 560 60 Z' fill='#9cc9ec'/><text x='650' y='300' text-anchor='middle' font-size='20' font-weight='700' fill='#2f5f8a'>the lake</text><rect x='20' y='250' width='560' height='34' fill='#c9c9c9'/><text x='120' y='273' font-size='15' fill='#444'>Main Street</text><rect x='250' y='60' width='34' height='440' fill='#c9c9c9'/><text x='0' y='0' transform='translate(273 470) rotate(-90)' font-size='15' fill='#444'>Station Road</text><rect x='60' y='100' width='150' height='110' rx='8' fill='#f2c14e'/><text x='135' y='150' text-anchor='middle' font-weight='700'>supermarket</text><text x='135' y='174' text-anchor='middle' font-size='14'>big</text><rect x='320' y='100' width='110' height='70' rx='8' fill='#8fb3e8'/><text x='375' y='140' text-anchor='middle' font-weight='700'>station</text><rect x='60' y='300' width='80' height='60' rx='6' fill='#cfd8e3'/><text x='100' y='336' text-anchor='middle' font-size='15' font-weight='700'>bank</text><rect x='160' y='300' width='80' height='60' rx='6' fill='#cfd8e3'/><text x='200' y='336' text-anchor='middle' font-size='15' font-weight='700'>bank</text><rect x='300' y='300' width='230' height='130' rx='10' fill='#7cc576'/><circle cx='340' cy='340' r='16' fill='#3f8f3a'/><circle cx='380' cy='370' r='16' fill='#3f8f3a'/><circle cx='480' cy='345' r='16' fill='#3f8f3a'/><text x='420' y='410' text-anchor='middle' font-weight='700'>park</text><rect x='450' y='100' width='90' height='110' rx='8' fill='#c9a6e0'/><text x='495' y='150' text-anchor='middle' font-weight='700'>library</text><text x='495' y='172' text-anchor='middle' font-size='14'>new</text><text x='70' y='470' font-size='15' fill='#555'>no hospital · no museum</text>", 'description': 'A simple map of Lakeview. Main Street goes from left to right in the middle; Station Road goes from top to bottom. The lake is on the right. Top left: a big supermarket. Top middle, next to Station Road: the train station. Top right, near the lake: a new library. Bottom left, on Main Street: two banks. Bottom middle, next to the lake: a park with trees. Text at the bottom: "no hospital · no museum".'}
dsvg, ddesc = PIC.render(dr)
check('DRAW a free drawing (map) renders with its description', dsvg.startswith('<svg') and 'Main Street' in dsvg and ddesc.startswith('Picture "Map of Lakeview". Drawing:'), ddesc[:80])
for bad, why in [(dict(dr, svg=dr['svg'] + "<script>alert(1)</script>"), 'not allowed'), (dict(dr, svg=dr['svg'] + "<image href='http://x/y.png'/>"), 'not allowed'),
                 (dict(dr, svg="<rect width='10' height='10' onload='x()'/>"), 'not allowed'), (dict(dr, svg="<rect width='10' height='10' fill='url(http://x)'/>"), 'not allowed'),
                 (dict(dr, svg=dr['svg'] + "<text x='1' y='1'>The library is new</text>"), 'verb'), (dict(dr, description=''), 'description'), (dict(dr, svg='<rect'), 'XML')]:
    try: PIC.render(bad); ok = False
    except ValueError as e: ok = why in str(e)
    check(f'DRAW unsafe or wrong drawing rejected ({why})', ok)
bdr = dict(bp, pictures=[dr], agent_instructions=bp['agent_instructions'] + ' PICTURE 1: ' + ddesc)
out = run('voice-code', '--brief', jw(vd, 'draw.json', bdr))
d = zlib.decompressobj(-15); payload = json.loads(d.decompress(base64.urlsafe_b64decode(out['code'][4:] + '=' * (-len(out['code'][4:]) % 4))))
check('DRAW the code carries the drawing for the page', len(payload.get('picture_svgs', [])) == 1 and 'the lake' in payload['picture_svgs'][0])
try: PIC.render({'template': 'board', 'title': 'Lakeview', 'notes': ['supermarket: big']}); okb = False
except ValueError as e: okb = 'last resort' in str(e)
check('NOTES a board of notes without notes_reason is rejected (draw instead)', okb)
check('PIC an A1 brief without pictures and without a reason is rejected', 'picture' in run('voice-code', '--brief', jw(vd, 'np.json', {k: v for k, v in bp.items() if k not in ('pictures', 'picture_waived_reason')}), ok=False).get('error', ''))

# ---------------- A1 the engine counts the items and checks the rubric rows (audit 2026-11-11)
da = new_state(); placement_walk(da, set(), False, lambda i: False); run('reinforced', '--state', da)
def base_ev(eid='L001', etype='lesson_assessment', dims=('Reading', 'Writing', 'Speaking')):
    e = evidence(eid, etype); e['dimensions_to_score'] = list(dims); e['spec_ref'] = uid('X!'); return e
def raw(d, e, sc=None, ok=False):
    a = ['score', '--state', d, '--evidence', jw(d, 'e.json', e)] + (['--scores', jw(d, 's.json', sc)] if sc else [])
    return run(*a, ok=ok)
WS = {'Writing': [100] * 4, 'Speaking': [100] * 5}
e = base_ev(); e['reading'] = {'resource': {'resource_id': 'TXT-A1-1', 'kind': 'text'}, 'items': items([(None, False)] * 5)}
sc = scores('L001', {'Reading': (5, 5), **WS})
out = raw(da, e, sc, ok=True)['decision']
check('A1 five wrong answers are 0% whatever the scoring agent says', out['decision'] == 'retest_pending' and out['dimension_results'][0]['score_pct'] == 0 and any('engine counted 0/5' in n for n in out['notes']), out)
db = new_state(); placement_walk(db, set(), False, lambda i: False); run('reinforced', '--state', db)
e = base_ev(); e['reading'] = {'resource': {'resource_id': 'TXT-A1-2', 'kind': 'text'}, 'items': items([(None, True)] * 5)}
bare = scores('L001', WS); bare['dimensions'][0] = {'dimension': 'Writing', 'score_pct': 95}
check('A1 a Writing score without rubric criteria is rejected', 'one band per rubric row' in raw(db, e, bare).get('error', ''))
part = scores('L001', WS); part['dimensions'][1]['criteria'] = part['dimensions'][1]['criteria'][:1]
check('A1 a Speaking score with missing rubric rows is rejected', 'without a band' in raw(db, e, part).get('error', ''))
other = scores('L001', WS); other['dimensions'][0]['criteria'][0]['rubric_id'] = 'RB-XW-01'
check('A1 a rubric row of another rubric is rejected', 'do not apply' in raw(db, e, other).get('error', ''))
nopron = scores('L001', WS); nopron['dimensions'][1]['criteria'] = [c for c in nopron['dimensions'][1]['criteria'] if c['rubric_id'] != 'RB-LS-04']
check('A1 pronunciation cannot be left out of a voice Speaking', 'text mode' in raw(db, e, nopron).get('error', ''))
e['speaking'] = {'voice_session_id': 'S0001', 'voice_report_path': 'voice-sessions/S0001/report.json', 'channel': 'text'}
out = raw(db, e, nopron, ok=True)['decision']
check('A1 text mode: Speaking without the pronunciation row is accepted', out['decision'] == 'passed', out)
check('A1 nothing was written by the rejected packages (attempt 1 was the accepted one)', out['attempt'] == 1 and len(jr(db, 'attempts.json')['events'][0]['attempts']) == 1)
e = base_ev('L002'); e['level'] = 'B1'; e['reading'] = {'resource': {'resource_id': 'TXT-A1-3', 'kind': 'text'}, 'items': items([(None, True)] * 5)}
check('A1 the package level must be the level of the event', 'A1 event' in raw(db, e, scores('L002', WS)).get('error', ''))
e['level'] = 'A1'; e['reading']['items'][0].update(options=['a', 'b'], key='c')
check('A1 a key that is not one of the options is rejected', 'not one of its options' in json.dumps(raw(db, e, scores('L002', WS))))
# open items: exact match is counted by the engine; anything else needs the agent's verdict
e = base_ev('L002'); op = [{'item_id': uid('op'), 'question': 'q', 'key': 'Mia', 'accepted_variants': ['Her name is Mia'], 'learner_answer': a} for a in ('mia.', 'Her name is Mia', "It's Mia", '', 'Tom')]
e['reading'] = {'resource': {'resource_id': 'TXT-A1-4', 'kind': 'text'}, 'items': op}
mk = run('mark', '--evidence', jw(db, 'e.json', e))
check('A1 mark: exact answers counted, two open items wait for the evaluator', mk['items']['Reading'] == {'items_correct': 2, 'items_total': 5, 'waiting': 2} and mk['agent'] == 'evaluator' and len(mk['open_items']) == 2, mk)
check('A1 open items without a verdict cannot be scored', 'without a verdict' in raw(db, e, scores('L002', WS)).get('error', ''))
sc = scores('L002', WS); sc['item_results'] = [{'item_id': op[2]['item_id'], 'correct': True}, {'item_id': op[4]['item_id'], 'correct': False}, {'item_id': op[3]['item_id'], 'correct': True}]
out = raw(db, e, sc, ok=True)['decision']
check('A1 with the verdicts: 3/5 (an empty answer stays wrong)', out['dimension_results'][0]['score_pct'] == 60, out)
# a listening check with closed items needs no scoring agent
dl = new_state(); placement_walk(dl, set(), False, lambda i: False); set_current(dl, 'ULC-A1-U01')
e = base_ev('ULC-A1-U01', 'unit_listening_check', ['Listening']); e['listening'] = {'source_id': 'LS-A1-01', 'items': items([('gist', True)] * 2 + [('detail', True)] * 3 + [('detail', False)])}
mk = run('mark', '--evidence', jw(dl, 'e.json', e))
check('A1 mark: closed items → no scoring agent', mk['agent'] == 'none' and mk['items']['Listening']['items_correct'] == 5, mk)
out = raw(dl, e, ok=True)['decision']
check('A1 listening check scored from the evidence alone (5/6 → passed)', out['decision'] == 'passed' and out['global_pct'] == 83.33, out)
# sections and failed words come from the wrong items
dx = new_state(); placement_walk(dx, set(), False, lambda i: False); set_current(dx, 'L400')
e = base_ev('L400', 'review_diagnostic'); its = items([(None, True)] * 2 + [(None, False)] * 2)
for it, sec in zip(its, ['4.1', '4.1', '4.2', '4.2']): it['section'] = sec
e['reading'] = {'resource': {'resource_id': 'TXT-C1-1', 'kind': 'text'}, 'items': its}
out = raw(dx, e, scores('L400', {'Writing': [100] * 4, 'Speaking': [100] * 8}, extra={'sections': [{'section': '4.2', 'score_pct': 100}, {'section': '4.3', 'score_pct': 50}]}), ok=True)['decision']
check('A1 sections with tagged items are counted by the engine; the others come from the evaluator', out['flagged_sections'] == ['4.2', '4.3'], out)
check('A1 wrong tagged items are stored as errors of their section', jr(dx, 'errors.json')['by_section']['4.2']['count'] == 2)

# ---------------- A3 the repetition comes first
dg = new_state(); placement_walk(dg, set(), False, lambda i: False); set_current(dg, 'EXIT-A1')
EXA = {'Reading': (12, 12), 'Listening': (10, 10), 'Writing': [100] * 4, 'Speaking': [50] * 5}
for k in range(1, 4):
    dec = score(dg, evidence('EXIT-A1', 'level_exit', att=k), scores('EXIT-A1', EXA if k == 1 else {'Speaking': [50] * 5}, extra={'sections': [{'section': '4.6', 'score_pct': 40}]}))['decision']
out = score(dg, evidence('EXIT-A1', 'level_exit'), scores('EXIT-A1', dict(EXA, Speaking=[100] * 5)), ok=False)
check('A3 the exit cannot be taken again before its lessons are repeated', 'must be repeated and passed first' in out.get('error', '') and dec['decision'] == 'repeat_content', out)
set_current(dg, 'ULC-A1-U02')
for k in range(3):
    dec = score(dg, evidence('ULC-A1-U02', 'unit_listening_check'), scores('ULC-A1-U02', {'Listening': (1, 10)}))['decision']
out = score(dg, evidence('ULC-A1-U02', 'unit_listening_check'), scores('ULC-A1-U02', {'Listening': (10, 10)}), ok=False)
check('A3 the listening check cannot be taken again before the listening session', 'listening session first' in out.get('error', ''), out)
run('repeated', '--state', dg)
dec = score(dg, evidence('ULC-A1-U02', 'unit_listening_check'), scores('ULC-A1-U02', {'Listening': (10, 10)}))['decision']
check('A3 after the listening session it is a new cycle', dec['decision'] == 'passed' and dec['cycle'] == 2, dec)

# ---------------- A4 the same package is not scored twice; A5 a failed command writes nothing
dd = new_state(); placement_walk(dd, set(), False, lambda i: False); run('reinforced', '--state', dd)
score(dd, evidence('L001', 'lesson_assessment'), scores('L001', {'Reading': (5, 5), 'Writing': [50] * 4, 'Speaking': [100] * 5}))
e = base_ev('L001', dims=['Writing']); e['attempt'] = 2; e['writing'] = {'prompt': 'p', 'learner_text': 'Hello Tom!', 'word_range': [25, 40]}
sc = scores('L001', {'Writing': [50] * 4})
out = raw(dd, e, sc, ok=True)['decision']
e['attempt'] = 3
dup = raw(dd, e, sc)
check('A4 the same package again is rejected and uses no attempt', 'already been scored' in dup.get('error', '') and out['attempt'] == 2 and run('attempt', '--state', dd, '--event', 'L001', '--type', 'lesson_assessment')['attempt'] == 3, dup)
before = open(os.path.join(dd, 'attempts.json')).read()
pr = jr(dd, 'progress.json'); pr['lessons_passed'] = ['BAD']; jw(dd, 'progress.json', pr)
e['writing']['learner_text'] = 'Hello Ann!'
out = raw(dd, e, sc)
check('A5 a state file that does not validate stops the command before anything is written', 'error' in out and open(os.path.join(dd, 'attempts.json')).read() == before and not [f for f in os.listdir(dd) if f.endswith('.tmp')], out)

# ---------------- B1 placement: counted from the evidence; short Speaking
dq = new_state(); a = run('placement', '--state', dq)['next_action']
old = scores('PLACEMENT', {'Grammar': (4, 4), 'Vocabulary': (4, 4), 'Reading': (2, 2)})
check('B1 a placement probe without evidence is rejected', 'pass --evidence' in run('placement', '--state', dq, '--scores', jw(dq, 's.json', old), ok=False).get('error', ''))
check('B1 a probe with fewer items than the specification is rejected', 'at least 4' in run('placement', '--state', dq, '--evidence', jw(dq, 'e.json', pev({'Grammar': (1, 1), 'Vocabulary': (4, 4), 'Reading': (2, 2)})), ok=False).get('error', ''))
e = pev({'Grammar': (4, 4), 'Vocabulary': (3, 4), 'Reading': (2, 2)}); e['vocabulary']['items'][3]['oxford_id'] = 473
a = run('placement', '--state', dq, '--evidence', jw(dq, 'e.json', e), '--scores', jw(dq, 's.json', scores('PLACEMENT', {'Grammar': (0, 4)})))['next_action']
pq = jr(dq, 'placement.json')
check('B1 A1 mastered from the evidence (9/10), the failed word is kept', pq['level_results']['A1'] == {'scores': {'Grammar': 100.0, 'Vocabulary': 75.0, 'Reading': 100.0}, 'global': 90.0, 'mastered': True} and pq['failed_vocabulary'] == [473] and a['level'] == 'A2', pq)
a = run('placement', '--state', dq, '--evidence', jw(dq, 'e.json', pev({'Grammar': (1, 4), 'Vocabulary': (1, 4), 'Reading': (0, 2)})))['next_action']
bare = scores('PLACEMENT', {'Writing': [100] * 4, 'Speaking': [100] * 5}); bare['dimensions'][0] = {'dimension': 'Writing', 'score_pct': 90}
check('B1 placement Writing without rubric criteria is rejected', a['action'] == 'writing_speaking' and 'one band per rubric row' in run('placement', '--state', dq, '--scores', jw(dq, 's.json', bare), ok=False).get('error', ''), a)
dq2 = new_state(); a = run('placement', '--state', dq2)['next_action']
for lv in ('A1', 'A2', 'B1'):
    a = run('placement', '--state', dq2, '--evidence', jw(dq2, 'e.json', pev({'Grammar': (4, 4), 'Vocabulary': (4, 4), 'Reading': (2, 2)}, level=lv)))['next_action']
a = run('placement', '--state', dq2, '--evidence', jw(dq2, 'e.json', pev({'Grammar': (0, 4), 'Vocabulary': (0, 4), 'Reading': (0, 2)}, level='B2')))['next_action']
ws = scores('PLACEMENT', {'Writing': [75] * 4, 'Speaking': [75] * 6}, level='B1'); ws['dimensions'][1]['criteria'] = [c for c in ws['dimensions'][1]['criteria'] if c['rubric_id'] != 'RB-XS-06']
out = run('placement', '--state', dq2, '--scores', jw(dq2, 's.json', ws), ok=False)
check('B1 placement at B1: the mediation row may be left out of the short Speaking (only in placement)', a == dict(a, action='writing_speaking', level='B1') and 'error' not in out and jr(dq2, 'placement.json')['ws']['passed'], out)
de = new_state(); placement_walk(de, set(), False, lambda i: False); set_current(de, 'EXIT-B1')
ex = scores('EXIT-B1', {'Reading': (10, 10), 'Listening': (10, 10), 'Writing': [100] * 4, 'Speaking': [100] * 6}); ex['dimensions'][3]['criteria'] = [c for c in ex['dimensions'][3]['criteria'] if c['rubric_id'] != 'RB-XS-06']
check('B1 in a level exit the mediation row is required', 'RB-XS-06' in score(de, evidence('EXIT-B1', 'level_exit'), ex, ok=False).get('error', ''))
pb = dict(be, event_id='PLACEMENT', end_condition={'target_learner_turns': 6, 'max_minutes': 6}, shared_text=dict(st, body=' '.join(TXT.split()[:80])))
out = run('voice-code', '--brief', jw(vd, 'pl.json', pb))
check('B1 placement Speaking: 6 turns, 6 minutes and a 60–100-word text get a code', out['code'].startswith('EC2-'), out)
check('B1 placement Speaking with the exam turns of the level is rejected', 'placement Speaking' in run('voice-code', '--brief', jw(vd, 'pl2.json', dict(pb, end_condition={'target_learner_turns': 8, 'max_minutes': 10})), ok=False).get('error', ''))
check('B1 placement Speaking with a full-length text is rejected', 'placement text' in run('voice-code', '--brief', jw(vd, 'pl3.json', dict(pb, shared_text=dict(st, body=TXT + ' The bus is red.'))), ok=False).get('error', ''))
check('C1 the code comes with a link by session number for Drive mode', run('voice-code', '--brief', jw(vd, 'p.json', bp)).get('drive_link', '').endswith('#S0001'))

# ---------------- B3 practice errors and words reach the memory
dm = new_state(); placement_walk(dm, set(), False, lambda i: False); run('reinforced', '--state', dm)
rp = json.load(open(os.path.join(EX, 'voice_report_exam.json'), encoding='utf-8'))
check('B3 an exam report is not a practice log', 'practice reports only' in run('practice-log', '--state', dm, '--lesson', 'L001', '--report', jw(dm, 'r.json', rp), ok=False).get('error', ''))
rp.update(mode='practice', errors=[{'turn': 2, 'learner_said': 'Is Ana', 'issue': 'missing subject', 'section': '4.1', 'recast': 'She is Ana'}, {'turn': 4, 'learner_said': 'y así', 'issue': 'recognition'}])
w473 = next(r for r in C.table('vocabulary') if r['Oxford ID'] == '473')
out = run('practice-log', '--state', dm, '--lesson', 'L001', '--report', jw(dm, 'r.json', rp), '--errors', jw(dm, 'x.json', [{'section': '4.1', 'description': 'I am engineer → I am an engineer'}]), '--failed-words', '473')
em = jr(dm, 'errors.json'); vm = jr(dm, 'vocabulary.json')
check('B3 practice errors are added by section and the word is flagged for recycling', em['by_section']['4.1']['count'] == 3 and em['by_section']['4.1']['examples'][-2:] == ['Is Ana → She is Ana', 'I am engineer → I am an engineer'] and em['logged_sessions'] == ['S0002'] and vm['priority_recycling'][0]['word'] == w473['Word'] and out['write'][-1] == 'progress.json', (out, em))
check('B3 the same practice session is not added twice', 'already' in run('practice-log', '--state', dm, '--lesson', 'L001', '--report', jw(dm, 'r.json', rp), ok=False).get('error', ''))
run('practice-log', '--state', dm, '--lesson', 'L002', '--recycled', '473')
check('B3 a recycled word remembers the lesson', jr(dm, 'vocabulary.json')['priority_recycling'][0]['recycled_in'] == ['L002'])

# ---------------- B4 what can move to the Drive archive
u1 = [l for l in sorted(C.lessons(), key=C.seq) if C.lessons()[l]['Unit'] == C.lessons()['L001']['Unit']]
set_current(dm, next(l for l in sorted(C.lessons(), key=C.seq) if C.lessons()[l]['Unit'] != C.lessons()['L001']['Unit']))
docs = [f'english-course/voice-sessions/S{n:04d}/{f}.json' for n in range(1, 10) for f in ('brief', 'report')] + ['english-course/state/progress.json', 'english-course/partial-evidence/EXIT-A1.json'] + \
       [f'english-course/notes/2026-10-{10 + n:02d}_{l}.md' for n, l in enumerate(u1[:2] + ['L300', 'L301', 'L302'])]
ap = run('archive-plan', '--state', dm, '--docs', jw(dm, 'docs.json', docs))
paths = [x['path'] for x in ap['archive']]
check('B4 the last 6 voice sessions stay; older ones and old notes can move; state files never', ap['kept_voice_sessions'] == [f'S{n:04d}' for n in range(4, 10)] and sum('voice-sessions' in x for x in paths) == 6
      and [x for x in paths if '/notes/' in x] == docs[-5:-3] and not any('/state/' in x or 'partial-evidence' in x for x in paths), ap)
check('B4 a unit summary is asked for before its notes move', ap['summaries_needed'][0]['summary_path'] == f"english-course/notes/unit-{C.lessons()['L001']['Unit']}.md" and ap['archive'][0]['drive_name'] == 'voice-sessions__S0001__brief.json', ap['summaries_needed'])

# ---------------- D preferences: the tutor says what a suggestion affects
check('D a HOW suggestion with the words "no grammar" / "remove" is stored', 'added' in run('pref-add', '--state', dm, '--category', 'explanation_style', '--affects', 'formative', '--text', 'No grammar terms at first; remove long introductions.', '--quote', 'less theory please'))
check('D a suggestion about the content is rejected', 'WHAT' in run('pref-add', '--state', dm, '--category', 'practice_balance', '--affects', 'content', '--text', 'Leave out the reading part.', '--quote', 'no reading', ok=False).get('error', ''))
r_ = subprocess.run(ENG + ['pref-add', '--state', dm, '--category', 'pace', '--text', 'Slower.', '--quote', 'slower'], capture_output=True, text=True)
check('D --affects is required', r_.returncode != 0 and 'affects' in r_.stderr)

# ---------------- E timezone from config.json
check('E dates use the timezone of config.json (America/Bogota)', jr(dm, 'progress.json')['updated_at'].endswith('-05:00'))

for x in DIRS: shutil.rmtree(x, ignore_errors=True)
print('\n' + ('ALL OK' if not FAILS else f'FAILURES ({len(FAILS)}): {FAILS}'))
sys.exit(1 if FAILS else 0)
