#!/usr/bin/env python3
"""Deterministic course engine: scores, decisions and learner state.

The tutor NEVER computes scores or decides pass/fail: it runs this script.
All paths are local (sandbox). The tutor copies the learner's files from their Claude project into STATE,
runs the command and saves back to the project the files the script lists in "write"
(in that order: progress.json always goes last).

Commands:
  engine.py init       --state DIR --student student-0001 --name "Name"
  engine.py consent    --state DIR --given yes|no      Recording consent (Gemini free tier)
  engine.py status     --state DIR                     What today's session is, pending items, state consistency
  engine.py attempt    --state DIR --event L001 --type lesson_assessment
                                                       Attempt, cycle and dimensions to assess (P09)
  engine.py resource   --state DIR --id TXT-L001-R-office  Can it be used? (max. 3 uses, P08)
  engine.py mark       --evidence E.json [--scores S.json]
                                                       Counts the items of a package from key + learner_answer; says which scoring agent is needed (if any)
  engine.py score      --state DIR --evidence E.json [--scores S.json]
                                                       Counts the items itself, checks the rubric criteria, applies P01–P03/P05/P06/P07/P09/P10
                                                       and updates the state. --scores is needed only for Writing/Speaking or open items
  engine.py repeated   --state DIR                     Marks the listening session of a listening check as done (P10)
  engine.py placement  --state DIR [--evidence E.json] [--scores S.json]
                                                       Placement test, step by step (P16–P17): probes need --evidence, Writing/Speaking needs --scores
  engine.py reinforced --state DIR                     Closes the post-placement reinforcement session (P18)
  engine.py replace    --state DIR --to L0XX --evidence "text"   Re-placement accepted by the learner (P19)
  engine.py prefs      --state DIR                     Active learner preferences + allowed categories
  engine.py pref-add   --state DIR --category C --affects formative --text "..." --quote "..." [--event L001]
                                                       Stores a learner suggestion about HOW the class is taught
  engine.py pref-retire --state DIR --id PR001         Retires a preference (the learner asked, or it no longer fits)
  engine.py practice-log --state DIR --lesson L019 [--report report.json] [--errors E.json] [--failed-words 12,45] [--recycled 12,45]
                                                       Adds practice errors and failed words to the learner memory (formative, no score)
  engine.py archive-plan --state DIR --docs docs.json [--keep 6]
                                                       Which project docs can move to the Drive archive (old voice sessions and notes)
  engine.py voice-code --brief brief.json              Conversation code (EC2-…) for the voice page
  engine.py export     --state DIR --out backup.json   One-file backup of the whole state (for the learner to keep)
  engine.py import     --file backup.json --state DIR  Restores a backup into STATE
  engine.py validate   --file X.json --schema voice_brief|voice_report|evidence_package|evaluator_scores|decision|...
Output: JSON on stdout. Errors: {"error": ...} and exit code 1.
"""
import re, argparse, base64, hashlib, json, os, sys, zlib
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import curriculum as C  # noqa: E402

def _tz():
    """Timezone of config.json (IANA name); Bogota time if it is missing or the zone data is not installed."""
    try:
        from zoneinfo import ZoneInfo
        name = json.load(open(os.path.join(HERE, '..', 'config.json'), encoding='utf-8')).get('timezone')
        if name:
            return ZoneInfo(name)
    except Exception:
        pass
    return timezone(timedelta(hours=-5))


TZ = _tz()
DIMS = {'lesson_assessment': ['Reading', 'Writing', 'Speaking'], 'review_assessment': ['Reading', 'Writing', 'Speaking'],
        'review_diagnostic': ['Reading', 'Writing', 'Speaking'], 'unit_listening_check': ['Listening'],
        'level_exit': ['Reading', 'Listening', 'Writing', 'Speaking']}
STATE_FILES = ['profile', 'attempts', 'resources', 'vocabulary', 'errors', 'preferences', 'progress']  # progress last
PREF_CATEGORIES = {
    'activity_format': 'how exercises are presented (e.g. clickable options, tables, short rounds)',
    'example_topics': 'topics used for examples and practice situations (e.g. work, technology, sports)',
    'pace': 'speed and chunking inside the session (e.g. shorter explanations, more breaks)',
    'feedback_style': 'how corrections are given (e.g. immediate, at the end, more examples)',
    'explanation_style': 'how things are explained (e.g. more tables, fewer rules, more examples)',
    'practice_balance': 'balance inside the formative parts (e.g. more speaking practice, more reading practice)'}
MAX_ACTIVE_PREFS = 8
# A preference may change HOW the class is taught, never WHAT is learned or assessed: the tutor classifies the suggestion
# (--affects) and only "formative" ones are stored.
AFFECTS = {'formative': 'how the class, the practice and the feedback are done',
           'assessment': 'a formal assessment: its tasks, length, time, help, criteria or pass rules',
           'content': 'what is taught or its order: lesson, level, grammar, vocabulary, skills, English-only'}
ITEM_BLOCKS = {'Reading': 'reading', 'Listening': 'listening', 'Grammar': 'grammar', 'Vocabulary': 'vocabulary'}   # dimension → evidence block
RUBRIC_DIMS = ('Writing', 'Speaking')
PLACEMENT_MIN_ITEMS = {'probe_level': {'Grammar': 4, 'Vocabulary': 4, 'Reading': 2}, 'probe_unit': {'Grammar': 5, 'Vocabulary': 6}}
MAX_ATTEMPTS, MAX_USES = 3, 3


def die(msg, **kw):
    print(json.dumps({'error': msg, **kw}, ensure_ascii=False))
    sys.exit(1)


def now():
    return datetime.now(TZ).isoformat(timespec='seconds')


def today():
    return datetime.now(TZ).date().isoformat()


def r2(x):
    return round(x + 1e-9, 2)


def load(state, name, default=None):
    p = os.path.join(state, name + '.json')
    if not os.path.exists(p):
        if default is None:
            die(f'{name}.json is missing in {state}')
        return default
    return json.load(open(p, encoding='utf-8'))


def validate(obj, schema):
    from jsonschema import Draft202012Validator
    s = json.load(open(os.path.join(HERE, '..', 'schemas', schema + '.schema.json'), encoding='utf-8'))
    return [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in Draft202012Validator(s, format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(obj)]


def must_valid(obj, schema):
    e = validate(obj, schema)
    if e:
        die(f'{schema} does not match its contract', details=e[:10])


def commit(state, objs):
    """Writes several state files with the same state_rev. Returns them in save order."""
    os.makedirs(state, exist_ok=True)
    revs = []
    for n in STATE_FILES:
        p = os.path.join(state, n + '.json')
        if os.path.exists(p):
            revs.append(json.load(open(p, encoding='utf-8')).get('state_rev', 0))
    rev = max(revs + [0]) + 1
    prog_path = os.path.join(state, 'progress.json')
    if 'progress' not in objs and os.path.exists(prog_path):
        # progress.json is the completion marker: it is always rewritten last with the new rev
        objs = {**objs, 'progress': json.load(open(prog_path, encoding='utf-8'))}
    todo = [(n, objs[n]) for n in STATE_FILES + ['placement'] if n in objs]
    for n, o in todo:   # validate every file before writing any: a failed command leaves STATE untouched
        if n != 'placement':
            o['state_rev'] = rev
            must_valid(o, n)
    out = []
    for n, o in todo:
        path = os.path.join(state, n + '.json')
        with open(path + '.tmp', 'w', encoding='utf-8') as f:
            json.dump(o, f, ensure_ascii=False, indent=2)
        os.replace(path + '.tmp', path)
        out.append(n + '.json')
    if 'progress.json' in out:
        out.remove('progress.json'); out.append('progress.json')
    return out


# ------------------------------------------------------------------ helpers
def attempt_info(attempts, eid, etype):
    """(cycle, attempt, previous_attempt_in_cycle_or_None) for the next attempt."""
    evs = [e for e in attempts['events'] if e['event_id'] == eid and e.get('event_type') == etype]
    if not evs:
        return 1, 1, None
    cur = max(evs, key=lambda e: e['cycle'])
    last = cur['attempts'][-1] if cur['attempts'] else None
    if last is None:
        return cur['cycle'], 1, None
    if last['decision'] in ('repeat_content', 'passed', 'diagnosed'):
        return cur['cycle'] + 1, 1, None
    return cur['cycle'], len(cur['attempts']) + 1, last


def kept_dims(prev):
    """Dimensions passed in the previous attempt keep their score (P09)."""
    if not prev:
        return {}
    ok = prev.get('passed_dimensions')
    if ok is None:
        ok = [d for d, v in prev['scores'].items() if v >= 70]
    return {d: prev['scores'][d] for d in ok if d in prev['scores']}


def to_score(etype, prev):
    k = kept_dims(prev)
    return [d for d in DIMS[etype] if d not in k]


def next_event_after(eid):
    try:
        n = C.next_event(eid)
    except SystemExit:
        return None
    return n['Event ID'] if n else None


def first_lesson_from(eid):
    ids = [r['Event ID'] for r in C.sequence()]
    i = ids.index(eid) if eid in ids else 0
    return next((x for x in ids[i:] if x.startswith('L')), ids[-1])


def is_final_review(lid):
    return any(r['Lesson ID'] == lid and r['Type'] == 'Level final review' for r in C.table('review_plan'))


def lessons_of_sections(level, sections):
    return [l['Lesson ID'] for l in sorted(C.lessons().values(), key=lambda l: C.seq(l['Lesson ID']))
            if l['Level'] == level and l['Lesson type'] in ('Core', 'Application') and set(C.SEC.findall(l['Grammar section'])) & set(sections)]


def expected_type(eid, etype):
    if eid.startswith('ULC-'):
        return etype == 'unit_listening_check'
    if eid.startswith('EXIT-'):
        return etype == 'level_exit'
    if eid not in C.lessons():
        return False
    rev = C.lessons()[eid]['Lesson type'] == 'Review'
    return etype in (('review_diagnostic', 'review_assessment') if rev else ('lesson_assessment',))


def host_of(check_id):
    chk = C.by('unit_listening_checks', 'Check ID').get(check_id)
    if chk and chk['Mode'] != 'Standalone after host lesson':
        return C.LID.findall(chk['Host lesson / position'])[0]
    return None


# ------------------------------------------------------------------ marking (items and rubric criteria)
def norm(x):
    x = re.sub(r'\s+', ' ', str(x).replace('’', "'").replace('‘', "'")).strip()
    return re.sub(r'[.!?]+$', '', x).strip().casefold()


def mark_items(ev, sc):
    """Marks every item of the package from key + learner_answer.
    Closed item (has options): exact match with the key. Open item: exact match with key / accepted_variants, empty = wrong,
    otherwise the scoring agent's verdict (scores.item_results); without a verdict it stays None.
    Returns ({dimension: [(item, True|False|None)]}, [item_ids waiting for a verdict], [problems])."""
    verdicts = {r['item_id']: bool(r['correct']) for r in (sc or {}).get('item_results', [])}
    marks, need, problems, seen = {}, [], [], set()
    for dim, blk in ITEM_BLOCKS.items():
        b = ev.get(blk)
        if not b:
            continue
        rows = []
        for it in b['items']:
            iid = it['item_id']
            if iid in seen:
                problems.append(f'{iid}: item_id used twice in this package')
            seen.add(iid)
            ans = norm(it['learner_answer']); good = {norm(it['key'])} | {norm(v) for v in it.get('accepted_variants', [])}
            if it.get('options'):
                if norm(it['key']) not in {norm(o) for o in it['options']}:
                    problems.append(f'{iid}: the key is not one of its options')
                ok = ans in good
            elif ans in good:
                ok = True
            elif not ans:
                ok = False
            elif iid in verdicts:
                ok = verdicts[iid]
            else:
                ok = None; need.append(iid)
            rows.append((it, ok))
        marks[dim] = rows
    return marks, need, problems


def count(rows):
    return sum(1 for _, ok in rows if ok), len(rows)


def item_findings(rows):
    """Errors by section and failed Oxford IDs, taken from the wrong items."""
    errs = [{'section': it['section'], 'description': f"{it['question'][:90]} — answered \"{it['learner_answer'][:40]}\" (key \"{it['key'][:40]}\")"}
            for it, ok in rows if ok is False and it.get('section')]
    return errs, [it['oxford_id'] for it, ok in rows if ok is False and 'oxford_id' in it]


def rubric_rows(level, kind, dim, starts='Pronunciation'):
    rows = [r for r in C.rubrics(level, kind)['rubrics'] if r['Skill'] == dim]
    return [r['Rubric ID'] for r in rows], [r['Rubric ID'] for r in rows if r['Criterion'].startswith(starts)]


def check_criteria(d, level, kind, text_mode, notes, placement=False):
    """A rubric dimension needs exactly one band per rubric row of the level; pronunciation is left out only in text mode.
    In the short placement tasks the mediation row may also be left out (the task may have no relay/summary element)."""
    k = d['dimension']
    need, pron = rubric_rows(level, kind, k)
    optional = set(rubric_rows(level, kind, k, 'Mediation')[1]) if placement else set()
    crit = d.get('criteria') or []
    if not crit:
        die(f'{k}: the evaluator must give one band per rubric row (criteria with rubric_id, band, evidence_quote, justification); a bare score_pct is not accepted', rubric_rows=need)
    ids = [c['rubric_id'] for c in crit]
    if len(ids) != len(set(ids)):
        die(f'{k}: a rubric row is scored twice', criteria=ids)
    extra = sorted(set(ids) - set(need))
    if extra:
        die(f'{k}: these rubric rows do not apply to a {level} {kind} {k} task: {extra}', rubric_rows=need)
    if text_mode and set(ids) & set(pron):
        d['criteria'] = [c for c in crit if c['rubric_id'] not in pron]; ids = [c['rubric_id'] for c in d['criteria']]
        notes.append(f'{k}: text mode, the pronunciation criterion is not counted.')
    missing = sorted(set(need) - set(ids) - (set(pron) if text_mode else set()) - optional)
    if missing:
        die(f'{k}: rubric rows without a band: {missing}' + ('' if text_mode or not set(missing) & set(pron) else ' (pronunciation is left out only in text mode: speaking.channel = "text" in the evidence)'), rubric_rows=need)


def ev_hash(ev):
    core = {k: v for k, v in ev.items() if k not in ('attempt', 'form_id')}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:16]


# ------------------------------------------------------------------ commands
def cmd_init(a):
    if os.path.exists(os.path.join(a.state, 'profile.json')):
        die('this learner already has profile.json')
    sid = a.student
    objs = {'profile': {'student_id': sid, 'name': a.name, 'started_on': today(),
                        'recording_consent': {'given': False, 'date': today(), 'text_version': 'not_asked'}},
            'attempts': {'student_id': sid, 'events': []}, 'resources': {'student_id': sid, 'resources': []},
            'vocabulary': {'student_id': sid, 'priority_recycling': []}, 'errors': {'student_id': sid, 'by_section': {}},
            'preferences': {'student_id': sid, 'preferences': []}}
    print(json.dumps({'write': commit(a.state, objs), 'next_action': 'consent, then placement',
                      'note': 'progress.json is created when placement ends'}, ensure_ascii=False))


def cmd_consent(a):
    profile = load(a.state, 'profile')
    profile['recording_consent'] = {'given': a.given == 'yes', 'date': today(), 'text_version': a.version}
    print(json.dumps({'write': commit(a.state, {'profile': profile}), 'recording_consent': profile['recording_consent']}, ensure_ascii=False))


def consistency(state):
    revs = {}
    for n in STATE_FILES:
        p = os.path.join(state, n + '.json')
        if os.path.exists(p):
            revs[n] = json.load(open(p, encoding='utf-8')).get('state_rev', 0)
    top = max(revs.values()) if revs else 0
    return {'state_revs': revs, 'complete': revs.get('progress', top) == top}


def cmd_status(a):
    profile = load(a.state, 'profile')
    cons = profile['recording_consent']
    p = load(a.state, 'progress', default={})
    pl = load(a.state, 'placement', default={})
    base = {'ask_consent': cons.get('text_version') == 'not_asked', 'voice_allowed': bool(cons.get('given')), 'consistency': consistency(a.state)}
    if not base['consistency']['complete']:
        base['warning'] = 'progress.json is older than other state files: the last save was incomplete. Do not score anything: tell the learner and restore their latest backup file (engine.py import) if they have one; otherwise continue and do not repeat the last result.'
    if not p:
        print(json.dumps({**base, 'status': 'placement_in_progress' if pl else 'new_student', 'placement_next': pl.get('expect')}, ensure_ascii=False)); return
    if 'EXIT-C1' in p['exits_passed']:
        print(json.dumps({**base, 'status': 'course_complete'}, ensure_ascii=False)); return
    ev = p.get('current_event') or p['current_lesson']
    out = {**base, 'status': 'pending' if p.get('pending') else 'ready', 'current_event': ev, 'current_lesson': p['current_lesson'],
           'pending': p.get('pending'), 'lessons_passed': len(p['lessons_passed']), 'lessons_credited': len(p['lessons_credited'])}
    if ev.startswith('ULC-'):
        out['event_type'] = 'unit_listening_check'
        h = host_of(ev)
        if h: out['embedded_in'] = h
    elif ev.startswith('EXIT-'):
        out['event_type'] = 'level_exit'
    else:
        L = C.lessons()[ev]
        out['event_type'] = ('final_review' if is_final_review(ev) else 'review_checkpoint') if L['Lesson type'] == 'Review' else 'lesson'
        emb = C.embedded(ev)
        if emb and emb['check']['Check ID'] not in p['checks_passed'] + p.get('checks_credited', []):
            out['embedded_listening_check'] = emb['check']['Check ID']
    print(json.dumps(out, ensure_ascii=False))


def cmd_attempt(a):
    it = load(a.state, 'attempts')
    cyc, att, prev = attempt_info(it, a.event, a.type)
    print(json.dumps({'event_id': a.event, 'event_type': a.type, 'cycle': cyc, 'attempt': att, 'dimensions_to_score': to_score(a.type, prev),
                      'kept_scores': kept_dims(prev)}, ensure_ascii=False))


def cmd_resource(a):
    rec = load(a.state, 'resources')
    r = next((x for x in rec['resources'] if x['resource_id'] == a.id), None)
    n = len(r['uses']) if r else 0
    print(json.dumps({'resource_id': a.id, 'uses': n, 'can_use': n < MAX_USES, 'uses_left': max(0, MAX_USES - n),
                      'items_already_used': sorted({i for u in (r['uses'] if r else []) for i in u['item_ids']})}, ensure_ascii=False))


def dim_pct(d):
    if d.get('criteria'):
        return r2(sum(c['band'] for c in d['criteria']) / len(d['criteria']))
    if d.get('items_total'):
        return r2(100 * d['items_correct'] / d['items_total'])
    return r2(d['score_pct'])


def cmd_mark(a):
    """Dry run: counts the items and says which scoring agent this package needs. Changes nothing."""
    ev = json.load(open(a.evidence, encoding='utf-8')); must_valid(ev, 'evidence_package')
    sc = json.load(open(a.scores, encoding='utf-8')) if a.scores else None
    if sc: must_valid(sc, 'evaluator_scores')
    marks, need, problems = mark_items(ev, sc)
    dims = ev['dimensions_to_score']
    problems += [f'{d}: no "{ITEM_BLOCKS[d]}" block with items in the package' for d in dims if d in ITEM_BLOCKS and d not in marks]
    rub = [d for d in dims if d in RUBRIC_DIMS]
    agent = 'evaluator' if rub else ('item-checker' if need else 'none')
    out = {'event_id': ev['event_id'], 'items': {d: {'items_correct': count(r)[0], 'items_total': count(r)[1], 'waiting': sum(1 for _, ok in r if ok is None)} for d, r in marks.items()},
           'open_items': need, 'rubric_dimensions': rub, 'agent': agent, 'problems': problems,
           'next': ('fix the problems first' if problems else
                    'no scoring agent needed: run score (or placement) with --evidence only' if agent == 'none' else
                    f'launch {agent}' + (' for the rubric bands' if rub else '') + (f' and a verdict for each open item ({len(need)})' if need else '') + ', then score with --evidence and --scores')}
    print(json.dumps(out, ensure_ascii=False))


def cmd_score(a):
    ev = json.load(open(a.evidence, encoding='utf-8')); must_valid(ev, 'evidence_package')
    if a.scores:
        sc = json.load(open(a.scores, encoding='utf-8')); must_valid(sc, 'evaluator_scores')
    else:
        sc = {'event_id': ev['event_id'], 'student_id': ev['student_id'], 'dimensions': []}
    if (ev['event_id'], ev['student_id']) != (sc['event_id'], sc['student_id']):
        die('evidence and scores do not belong to the same event/learner')
    etype, eid = ev['event_type'], ev['event_id']
    if etype not in DIMS:
        die(f'{etype}: use "engine.py placement" for the placement test')
    if not expected_type(eid, etype):
        die(f'{eid} cannot be scored as {etype}')
    lv_ = C.lessons()[eid]['Level'] if eid in C.lessons() else eid.split('-')[1]
    if ev['level'] != lv_:
        die(f"{eid} is a {lv_} event; the package says level {ev['level']} (the level sets the rubric rows)")
    notes = []
    prog = load(a.state, 'progress'); it = load(a.state, 'attempts'); rec = load(a.state, 'resources')
    voc = load(a.state, 'vocabulary'); err = load(a.state, 'errors')
    cur = prog.get('current_event') or prog['current_lesson']
    pend = prog.get('pending') or {}
    allowed = {cur, pend.get('event_id')} | set(pend.get('repeat_lessons') or [])
    if eid not in allowed:
        die(f'{eid} is not the current event ({cur}) or a pending one: it cannot be scored now')
    if etype == 'unit_listening_check':
        h = host_of(eid)
        if h and h not in prog['lessons_passed'] + prog['lessons_credited']:
            die(f'the embedded listening check {eid} is scored only after its lesson {h} is passed')
    if pend.get('status') == 'repeat_content' and eid == pend.get('event_id'):   # P10: the repetition comes first
        if etype == 'level_exit' and pend.get('repeat_lessons'):
            die(f"{eid} cannot be taken yet: these lessons must be repeated and passed first (P10): {pend['repeat_lessons']}")
        if etype == 'unit_listening_check':
            die(f'{eid} cannot be taken yet: do the listening session first, then engine.py repeated (P10)')
    eh = ev_hash(ev)
    if any(x.get('evidence_hash') == eh for e in it['events'] if e['event_id'] == eid for x in e['attempts']):
        die('this evidence package has already been scored (same content): nothing was changed. If the last save to the project failed, save the files of that result again; do not score it twice.')
    marks, need, problems = mark_items(ev, sc)
    if problems:
        die('the evidence package has item problems', details=problems)
    cyc, att, prev = attempt_info(it, eid, etype)
    if ev['attempt'] != att:
        notes.append(f"The package said attempt {ev['attempt']}; the record says attempt {att} (cycle {cyc}); {att} is used.")
    want = to_score(etype, prev); kept = kept_dims(prev)

    # --- resources (P08)
    used = []
    for key in ('reading', 'writing', 'listening', 'speaking'):
        blk = ev.get(key)
        if not blk: continue
        res = blk.get('resource') or ({'resource_id': blk['source_id'], 'kind': 'audio'} if key == 'listening' else None)
        if not res: continue
        ids = [i['item_id'] for i in blk.get('items', [])]
        r = next((x for x in rec['resources'] if x['resource_id'] == res['resource_id']), None)
        if r is None:
            r = {'resource_id': res['resource_id'], 'kind': res['kind'], 'uses': []}
            if res.get('source'): r['source'] = res['source']
            rec['resources'].append(r)
        if len(r['uses']) >= MAX_USES:
            die(f"{res['resource_id']} already has {MAX_USES} uses with this learner (P08): create another text/recording/prompt")
        rep = sorted({i for u in r['uses'] for i in u['item_ids']} & set(ids))
        if rep:
            die(f'items already used with this learner (P08): {rep}')
        r['uses'].append({'event_id': eid, 'attempt': att, 'date': now(), 'item_ids': ids})
        used.append({'resource_id': r['resource_id'], 'kind': r['kind']})

    # --- dimension scores: items are counted here from the evidence; Writing/Speaking come from the evaluator's rubric bands
    scores, subfail, sec_cnt, auto_err, auto_fv = dict(kept), [], {}, [], []
    by_dim = {d['dimension']: d for d in sc.get('dimensions', [])}
    for k in list(by_dim) + [k for k in marks if k not in by_dim]:
        if k not in want:
            notes.append(f'{k} is not reassessed in this attempt (P09): ignored; kept score {kept.get(k)}.')
    kind = 'exit' if etype == 'level_exit' else 'lesson'
    text_mode = (ev.get('speaking') or {}).get('channel') == 'text'
    for k in want:
        if k in ITEM_BLOCKS:
            if k not in marks:
                die(f'{k}: the evidence package has no "{ITEM_BLOCKS[k]}" block with its items (the engine counts the items itself)')
            rows = marks[k]; waiting = [x['item_id'] for x, ok in rows if ok is None]
            if waiting:
                die(f'{k}: open items without a verdict: launch the scoring agent and pass its item_results with --scores (engine.py mark lists them)', open_items=waiting)
            c, t = count(rows); scores[k] = r2(100 * c / t)
            rp = by_dim.get(k)
            if rp and rp.get('items_total') and (rp.get('items_correct'), rp['items_total']) != (c, t):
                notes.append(f"{k}: the scoring agent reported {rp.get('items_correct')}/{rp['items_total']}; the engine counted {c}/{t} from the evidence.")
            for x, ok in rows:
                if x.get('section'):
                    a_, b_ = sec_cnt.get(x['section'], (0, 0)); sec_cnt[x['section']] = (a_ + (1 if ok else 0), b_ + 1)
            e_, f_ = item_findings(rows); auto_err += e_; auto_fv += f_
            if k == 'Listening':
                sub = {}
                for x, ok in rows:
                    if x.get('sub_skill'):
                        a_, b_ = sub.get(x['sub_skill'], (0, 0)); sub[x['sub_skill']] = (a_ + (1 if ok else 0), b_ + 1)
                subfail += [n for n, (a_, b_) in sub.items() if b_ >= 4 and 100 * a_ / b_ < 70]  # P06
        elif k in by_dim:
            d = by_dim[k]
            check_criteria(d, ev['level'], kind, text_mode and k == 'Speaking', notes)
            scores[k] = dim_pct(d)
            if abs(d['score_pct'] - scores[k]) > 0.01:
                notes.append(f"{k}: the evaluator reported {d['score_pct']}; recalculated {scores[k]}.")
    mand = DIMS[etype]
    missing = [d for d in mand if d not in scores]
    if missing:
        die(f'mandatory dimensions missing: {missing}')
    glob = r2(sum(scores[d] for d in mand) / len(mand))
    results = [{'dimension': d, 'score_pct': scores[d], 'passed': scores[d] >= 70 and not (d == 'Listening' and subfail)} for d in mand]
    failed = [r['dimension'] for r in results if not r['passed']]
    passed = glob >= 80 and not failed
    retest = list(failed)
    if not passed and not failed:  # every dimension ≥70 but global <80: reassess the ones pulling the mean down (<80)
        retest = [d for d in mand if scores[d] < 80]
        notes.append(f'No dimension below 70 but global {glob} < 80: the dimensions below 80 are reassessed {retest} (course rule).')
    sec_scores = {s['section']: s['score_pct'] for s in sc.get('sections', [])}   # sections judged from Writing/Speaking
    sec_scores.update({k: r2(100 * a_ / b_) for k, (a_, b_) in sec_cnt.items()})     # sections with tagged items: the engine's count
    errors_seen = sc.get('errors_observed', []) + auto_err[:6]
    failed_voc = sorted({int(x) for x in sc.get('failed_vocabulary', [])} | set(auto_fv))
    flagged = sorted(s for s, v in sec_scores.items() if v < 70)
    if subfail: notes.append(f'Sub-skills below 70% with ≥4 items: {subfail} (P06).')

    dec = {'contract': 'decision/1', 'student_id': ev['student_id'], 'event_id': eid, 'event_type': etype, 'cycle': cyc, 'attempt': att,
           'global_pct': glob, 'dimension_results': results, 'failed_dimensions': failed, 'flagged_sections': flagged}
    new_pend = 'keep'
    final_review = etype == 'review_assessment' and is_final_review(eid)

    def advance(from_event):
        nxt = None
        if etype in ('lesson_assessment', 'review_assessment'):
            emb = C.embedded(eid)
            if emb and emb['check']['Check ID'] not in prog['checks_passed'] + prog.get('checks_credited', []):
                nxt = emb['check']['Check ID']; notes.append(f'Next: the embedded listening check {nxt}, in this same session.')
        if nxt is None:
            nxt = next_event_after(host_of(from_event) or from_event)
        return nxt

    if etype == 'review_diagnostic':
        dec.update(decision='diagnosed', attempts_left=MAX_ATTEMPTS)
        new_pend = {'event_id': eid, 'event_type': etype, 'status': 'diagnosed', 'sections': flagged}
        notes.append('Diagnostic: reinforce only flagged_sections, then practice conversation, then review_assessment.')
    elif final_review:  # P05: practice, not the level pass decision
        if eid not in prog['lessons_passed']: prog['lessons_passed'].append(eid)
        nxt = advance(eid)
        dec.update(decision='diagnosed', attempts_left=MAX_ATTEMPTS, next_event=nxt, next_lesson=first_lesson_from(nxt))
        prog['current_event'] = nxt; prog['current_lesson'] = dec['next_lesson']; new_pend = None
        notes.append('Level final review: does not block (P05). Use flagged_sections to prepare the level exit assessment.')
    elif passed:
        if etype in ('lesson_assessment', 'review_assessment') and eid not in prog['lessons_passed']: prog['lessons_passed'].append(eid)
        if etype == 'unit_listening_check' and eid not in prog['checks_passed']: prog['checks_passed'].append(eid)
        if etype == 'level_exit' and eid not in prog['exits_passed']: prog['exits_passed'].append(eid)
        dec.update(decision='passed', attempts_left=MAX_ATTEMPTS - att)
        if pend.get('status') == 'repeat_content' and pend.get('event_type') == 'level_exit' and eid in (pend.get('repeat_lessons') or []):
            rest = [l for l in pend['repeat_lessons'] if l != eid]
            nxt = rest[0] if rest else pend['event_id']
            new_pend = {**pend, 'repeat_lessons': rest} if rest else {**pend, 'status': 'repeated', 'repeat_lessons': []}
            notes.append(f'Exit repetition: {"next lesson " + rest[0] if rest else "lessons completed; back to " + pend["event_id"]}.')
        else:
            nxt = advance(eid)
            new_pend = None if (pend.get('event_id') == eid or eid in (pend.get('repeat_lessons') or [])) else 'keep'
        if nxt:
            dec['next_event'] = nxt; dec['next_lesson'] = first_lesson_from(nxt)
            prog['current_event'] = nxt; prog['current_lesson'] = dec['next_lesson']
        else:
            notes.append('End of the course.')
    elif att < MAX_ATTEMPTS:
        dec.update(decision='retest_pending', attempts_left=MAX_ATTEMPTS - att, retest_dimensions=retest)
        new_pend = {'event_id': eid, 'event_type': etype, 'status': 'retest_pending', 'dimensions': failed, 'retest_dimensions': retest}
        if flagged: new_pend['sections'] = flagged
        notes.append('Retest in a new session: targeted reinforcement of retest_dimensions and an equivalent task with new items (P08–P09).')
    else:
        dec.update(decision='repeat_content', attempts_left=0, retest_dimensions=list(mand))
        new_pend = {'event_id': eid, 'event_type': etype, 'status': 'repeat_content', 'dimensions': failed}
        if etype in ('lesson_assessment', 'review_assessment'):
            dec['repeat_lessons'] = [eid]
        elif etype == 'level_exit':
            lv = ev['level']
            fv = {str(x) for x in failed_voc}
            vlessons = {r['Lesson ID'] for r in C.table('vocabulary') if r['Oxford ID'] in fv and r['Level'] == lv}
            rl = sorted(set(lessons_of_sections(lv, flagged)) | vlessons, key=C.seq)
            if not rl:
                rl = [next(r['Lesson ID'] for r in C.table('review_plan') if r['Level'] == lv and r['Type'] == 'Level final review')]
                notes.append('No flagged sections or words: the level final review is repeated.')
            dec['repeat_lessons'] = rl
        elif etype == 'unit_listening_check':
            dec['listening_session'] = True
            notes.append('Listening session with the same recordings and new questions; when it is done: engine.py repeated. Then a new cycle (P10).')
        if dec.get('repeat_lessons'):
            new_pend['repeat_lessons'] = dec['repeat_lessons']
            prog['current_lesson'] = dec['repeat_lessons'][0]; prog['current_event'] = dec['repeat_lessons'][0]
        if flagged: new_pend['sections'] = flagged
        notes.append('After the repetition the counter goes back to 3 attempts (P10).')
    if new_pend != 'keep': prog['pending'] = new_pend
    prog['updated_at'] = now()

    evr = next((e for e in it['events'] if e['event_id'] == eid and e.get('event_type') == etype and e['cycle'] == cyc), None)
    if evr is None:
        evr = {'event_id': eid, 'event_type': etype, 'cycle': cyc, 'attempts': []}; it['events'].append(evr)
    keep_ok = [r['dimension'] for r in results if r['passed'] and r['dimension'] not in (retest if dec['decision'] == 'retest_pending' else [])]
    rowa = {'attempt': att, 'date': now(), 'form_id': ev.get('form_id') or sc.get('form_id') or f'{eid}-{cyc}-{att}', 'resources': used,
            'scores': scores, 'global_pct': glob, 'decision': dec['decision'], 'passed_dimensions': keep_ok, 'evidence_hash': eh}
    if sec_scores: rowa['section_scores'] = sec_scores
    evr['attempts'].append(rowa)

    for e in errors_seen:
        b = err['by_section'].setdefault(e['section'], {'count': 0, 'last_seen': today(), 'examples': []})
        b['count'] += 1; b['last_seen'] = today()
        if len(b['examples']) < 5: b['examples'].append(e['description'])
    vmap = {r['Oxford ID']: r['Word'] for r in C.table('vocabulary')}
    have = {v['oxford_id'] for v in voc['priority_recycling']}
    for oid in failed_voc:
        if int(oid) not in have and str(oid) in vmap:
            voc['priority_recycling'].append({'oxford_id': int(oid), 'word': vmap[str(oid)], 'failed_in': eid, 'date': today()})

    if notes: dec['notes'] = notes
    must_valid(dec, 'decision')
    w = commit(a.state, {'progress': prog, 'attempts': it, 'resources': rec, 'vocabulary': voc, 'errors': err})
    json.dump(dec, open(os.path.join(a.state, 'decision.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(json.dumps({'write': w, 'decision': dec}, ensure_ascii=False, indent=1))


def cmd_repeated(a):
    prog = load(a.state, 'progress'); p = prog.get('pending') or {}
    if p.get('status') != 'repeat_content' or p.get('event_type') != 'unit_listening_check':
        die('there is no pending listening session (repeat_content of a listening check)')
    prog['pending'] = {**p, 'status': 'repeated'}; prog['updated_at'] = now()
    print(json.dumps({'write': commit(a.state, {'progress': prog}), 'next': f"new attempt of {p['event_id']} (new cycle)"}, ensure_ascii=False))


def cmd_reinforced(a):
    prog = load(a.state, 'progress')
    if not prog.get('pending') or prog['pending'].get('status') != 'reinforcement':
        die('there is no pending post-placement reinforcement')
    prog['pending'] = None; prog['updated_at'] = now()
    print(json.dumps({'write': commit(a.state, {'progress': prog}), 'next_event': prog['current_event'],
                      'note': 'Delete placement.json from the project.'}, ensure_ascii=False))


# ------------------------------------------------------------------ placement (P16–P17)
def pooled(marks, dims, minimum):
    """Per-dimension and pooled % of a placement probe, counted from the evidence items."""
    corr = tot = 0; per = {}
    for d in dims:
        if d not in marks:
            die(f'{d}: the placement evidence has no "{ITEM_BLOCKS[d]}" block with its items')
        waiting = [x['item_id'] for x, ok in marks[d] if ok is None]
        if waiting:
            die(f'{d}: open items without a verdict: launch item-checker and pass its item_results with --scores', open_items=waiting)
        c, t = count(marks[d])
        if t < minimum.get(d, 1):
            die(f'{d}: {t} items; this placement step needs at least {minimum[d]} (Placement_Test)')
        corr += c; tot += t; per[d] = r2(100 * c / t)
    return per, (r2(100 * corr / tot) if tot else 0)


def mastered(per, glob, need):
    return all(per.get(k, 0) >= 70 for k in need) and glob >= 80


def cmd_placement(a):
    pl = load(a.state, 'placement', default={'stage': 1, 'level_results': {}, 'probes': [], 'failed_vocabulary': [], 'errors': [], 'started_at': now()})
    if pl.get('stage') == 'done':
        die('placement has already finished', result=pl.get('result'))
    sc = json.load(open(a.scores, encoding='utf-8')) if a.scores else None
    ev = json.load(open(a.evidence, encoding='utf-8')) if a.evidence else None
    act = pl.get('expect')
    if act and not (sc or ev):
        print(json.dumps({'next_action': act, 'note': 'waiting for this step: probes need --evidence (items with key and learner_answer), writing_speaking needs --scores'}, ensure_ascii=False)); return
    if (sc or ev) and not act:
        die('no placement step is waiting for scores')
    if sc or ev:
        if sc: must_valid(sc, 'evaluator_scores')
        if ev:
            must_valid(ev, 'evidence_package')
            if ev['event_id'] != 'PLACEMENT': die('placement evidence must have event_id PLACEMENT')
        sc = sc or {}
        k = act['action']; found_err, found_voc = [], []
        if k in ('probe_level', 'probe_unit'):
            if not ev:
                die('this placement step is counted from the evidence package (grammar / vocabulary / reading items with key and learner_answer): pass --evidence')
            marks, need, problems = mark_items(ev, sc)
            if problems:
                die('the evidence package has item problems', details=problems)
            dims = ['Grammar', 'Vocabulary', 'Reading'] if k == 'probe_level' else ['Grammar', 'Vocabulary']
            per, g = pooled(marks, dims, PLACEMENT_MIN_ITEMS[k])
            for d in dims:
                e_, f_ = item_findings(marks[d]); found_err += e_; found_voc += f_
            if k == 'probe_level':
                pl['level_results'][act['level']] = {'scores': per, 'global': g, 'mastered': mastered(per, g, ['Grammar', 'Vocabulary'])}
            else:
                m = mastered(per, g, ['Grammar', 'Vocabulary'])
                pl['probes'].append({'unit': act['unit'], 'index': act['index'], 'scores': per, 'global': g, 'mastered': m, 'confirm': act.get('confirm', False)})
                if not act.get('confirm'):
                    if m: pl['lo'] = act['index'] + 1
                    else: pl['hi'] = act['index']
        elif k == 'writing_speaking':
            if not sc.get('dimensions'):
                die('writing_speaking is scored by the evaluator with the exit rubrics: pass --scores')
            text_mode = ((ev or {}).get('speaking') or {}).get('channel') == 'text'; ws = {}
            for d in sc['dimensions']:
                if d['dimension'] in RUBRIC_DIMS:
                    check_criteria(d, act['level'], 'exit', text_mode and d['dimension'] == 'Speaking', pl.setdefault('notes', []), placement=True)
                    ws[d['dimension']] = dim_pct(d)
            pl['ws'] = {'level': act['level'], 'scores': ws, 'passed': len(ws) == 2 and all(v >= 70 for v in ws.values())}
        pl['failed_vocabulary'] += [int(x) for x in sc.get('failed_vocabulary', [])] + found_voc
        pl['errors'] += sc.get('errors_observed', []) + found_err[:6]
        pl['expect'] = None

    nxt = None
    if pl['stage'] == 1:
        res = pl['level_results']; tested = [l for l in C.LEVELS if l in res]
        if not tested:
            nxt = {'action': 'probe_level', 'level': 'A1'}
        else:
            last = tested[-1]
            if res[last]['mastered'] and last != 'C1':
                nxt = {'action': 'probe_level', 'level': C.LEVELS[C.LEVELS.index(last) + 1]}
            else:
                mast = [l for l in tested if res[l]['mastered']]
                place = 'C1' if res[last]['mastered'] else last
                if mast and 'ws' not in pl:
                    nxt = {'action': 'writing_speaking', 'level': mast[-1]}
                else:
                    if 'ws' in pl and not pl['ws']['passed']:
                        place = C.LEVELS[max(0, C.LEVELS.index(place) - 1)]
                        pl.setdefault('notes', []).append(f"Writing/Speaking < 70% at {pl['ws']['level']}: the placement level drops to {place}.")
                    pl['stage'] = 2; pl['level'] = place
                    pl['units'] = C.content_units(place); pl['lo'] = 0; pl['hi'] = len(pl['units'])
    if pl['stage'] == 2 and nxt is None:
        units = pl['units']
        if pl['lo'] < pl['hi']:
            mid = (pl['lo'] + pl['hi']) // 2
            nxt = {'action': 'probe_unit', 'unit': units[mid], 'index': mid}
        else:
            lo = pl['lo']; conf = [p for p in pl['probes'] if p['confirm']]
            if lo > 0 and not conf and not any(p['index'] == lo - 1 for p in pl['probes']):
                nxt = {'action': 'probe_unit', 'unit': units[lo - 1], 'index': lo - 1, 'confirm': True}
            else:
                if conf and not conf[-1]['mastered']:
                    lo -= 1; pl.setdefault('notes', []).append('The confirmation probe was not mastered: the learner starts one unit earlier.')
                pl['stage'] = 3; pl['start_index'] = lo
    if pl['stage'] == 3 and nxt is None:
        nxt, objs = finish_placement(a, pl)
        objs['placement'] = pl
        print(json.dumps({'write': commit(a.state, objs), 'next_action': nxt}, ensure_ascii=False, indent=1)); return
    specs = {'probe_level': ('PT-1: grammar 4 items (level sections; each with its section) + vocabulary 4 items (Oxford entries of the level, in context; each with its oxford_id) + reading 1 text with 2 items. Closed items (options). Data: curriculum.py level {level}. Score: engine.py placement --evidence E.json', ['Grammar', 'Vocabulary', 'Reading']),
             'writing_speaking': ('PT-1-WS: short Writing task of the level (lower bound of its word range) + short Speaking (voice brief in exam mode with event_id PLACEMENT: 6 learner turns, max. 6 min, text of 60–100 words; or text mode); rubrics: curriculum.py rubrics {level} exit. Score: evaluator, then engine.py placement --scores S.json [--evidence E.json]', ['Writing', 'Speaking']),
             'probe_unit': ('PT-2-PROBE: grammar 5 items on the unit section (each with its section) + vocabulary 6 items from its lessons (each with its oxford_id). Closed items (options). Data: curriculum.py unit {unit}. Score: engine.py placement --evidence E.json', ['Grammar', 'Vocabulary'])}
    t, dims = specs[nxt['action']]
    nxt['spec'] = t.format(**nxt); nxt['dimensions'] = dims
    pl['expect'] = nxt
    print(json.dumps({'write': commit(a.state, {'placement': pl}), 'next_action': nxt}, ensure_ascii=False, indent=1))


def finish_placement(a, pl):
    profile = load(a.state, 'profile')
    lv = pl['level']; units = pl['units']; i = pl['start_index']
    level_lessons = sorted([l for l, r in C.lessons().items() if r['Level'] == lv], key=C.seq)
    if i == 0:
        start = level_lessons[0]  # includes consolidation/review lessons before the first content unit
    elif i >= len(units):
        start = next(r['Lesson ID'] for r in C.table('review_plan') if r['Level'] == lv and r['Type'] == 'Level final review')
    else:
        last_prev = max(C.seq(x['lesson_id']) for x in C.unit(units[i - 1])['lessons'])
        start = next(l for l in level_lessons if C.seq(l) > last_prev)  # what follows the last mastered unit
    s0 = C.seq(start)
    credited = [l for l in sorted(C.lessons(), key=C.seq) if C.seq(l) < s0]
    cred_units = {C.lessons()[l]['Unit'] for l in credited}
    cred_secs = {s for l in credited for s in C.SEC.findall(C.lessons()[l]['Grammar section'])}
    checks = [r['Check ID'] for r in C.table('unit_listening_checks') if r['Unit'] in cred_units]
    exits = [f'EXIT-{l}' for l in C.LEVELS[:C.LEVELS.index(lv)]]
    reinf_secs = sorted({e['section'] for e in pl['errors'] if e['section'] in cred_secs})
    prog = {'student_id': profile['student_id'], 'current_lesson': start, 'current_event': start, 'updated_at': now(), 'lessons_passed': [],
            'lessons_credited': credited, 'checks_passed': [], 'checks_credited': checks, 'exits_passed': [], 'exits_credited': exits,
            'pending': {'event_id': start, 'status': 'reinforcement', 'sections': reinf_secs}, 'replacements': []}
    profile['placement_level'] = lv; profile['start_lesson'] = start
    voc = load(a.state, 'vocabulary'); err = load(a.state, 'errors')
    vrows = {r['Oxford ID']: r for r in C.table('vocabulary')}
    cred_set = set(credited)
    for oid in sorted(set(pl['failed_vocabulary'])):
        r = vrows.get(str(oid))
        if r and r['Lesson ID'] in cred_set and oid not in {v['oxford_id'] for v in voc['priority_recycling']}:
            voc['priority_recycling'].append({'oxford_id': oid, 'word': r['Word'], 'failed_in': 'PLACEMENT', 'date': today()})
    for e in pl['errors']:
        b = err['by_section'].setdefault(e['section'], {'count': 0, 'last_seen': today(), 'examples': []})
        b['count'] += 1
        if len(b['examples']) < 5: b['examples'].append(e['description'])
    pl['stage'] = 'done'; pl['result'] = {'level': lv, 'start_lesson': start}
    nxt = {'action': 'done', 'placement_level': lv, 'start_lesson': start, 'lessons_credited': len(credited), 'exits_credited': exits,
           'reinforcement': {'sections': reinf_secs, 'prerequisites': C.prereqs(start),
                             'words': [v['word'] for v in voc['priority_recycling'] if v['failed_in'] == 'PLACEMENT']},
           'notes': pl.get('notes', []), 'note': 'Next: reinforcement session (P18, formative), then the start lesson.'}
    return nxt, {'progress': prog, 'profile': profile, 'vocabulary': voc, 'errors': err}


def cmd_replace(a):
    if a.to not in C.lessons():
        die(f'{a.to} is not a lesson of the curriculum')
    prog = load(a.state, 'progress')
    old = prog['current_lesson']; s0 = C.seq(a.to)
    done = set(prog['lessons_passed'])
    prog['lessons_credited'] = [l for l in sorted(C.lessons(), key=C.seq) if C.seq(l) < s0 and l not in done]
    cred_units = {C.lessons()[l]['Unit'] for l in prog['lessons_credited']}
    prog['checks_credited'] = [r['Check ID'] for r in C.table('unit_listening_checks') if r['Unit'] in cred_units and r['Check ID'] not in prog['checks_passed']]
    lv = C.lessons()[a.to]['Level']
    prog['exits_credited'] = [f'EXIT-{l}' for l in C.LEVELS[:C.LEVELS.index(lv)] if f'EXIT-{l}' not in prog['exits_passed']]
    prog['current_lesson'] = a.to; prog['current_event'] = a.to; prog['pending'] = None; prog['updated_at'] = now()
    prog['replacements'].append({'date': today(), 'from': old, 'to': a.to, 'accepted': True, 'evidence': a.evidence})
    print(json.dumps({'write': commit(a.state, {'progress': prog}), 'from': old, 'to': a.to}, ensure_ascii=False))


def load_prefs(state):
    prof = load(state, 'profile')
    return load(state, 'preferences', default={'student_id': prof['student_id'], 'preferences': []})


def cmd_prefs(a):
    pr = load_prefs(a.state)
    act = [p for p in pr['preferences'] if p['status'] == 'active']
    print(json.dumps({'active': act, 'allowed_categories': PREF_CATEGORIES, 'affects': AFFECTS, 'max_active': MAX_ACTIVE_PREFS,
                      'rule': 'Apply a preference only where it is compatible with the lesson spec; the spec always wins. Preferences never change objectives, grammar, vocabulary, assessments, pass rules or the English-only rule.'}, ensure_ascii=False))


def cmd_pref_add(a):
    pr = load_prefs(a.state)
    if a.category not in PREF_CATEGORIES:
        die(f'category not allowed: {a.category}. A preference may only change HOW the class is taught.', allowed_categories=PREF_CATEGORIES)
    if a.affects != 'formative':
        die(f'this suggestion would change WHAT is learned or assessed ({a.affects}: {AFFECTS[a.affects]}): it cannot be stored as a preference. Explain to the learner, kindly, why the course keeps it, and offer a HOW alternative if there is one.')
    act = [p for p in pr['preferences'] if p['status'] == 'active']
    if len(act) >= MAX_ACTIVE_PREFS:
        die(f'already {MAX_ACTIVE_PREFS} active preferences: retire one first (engine.py pref-retire)', active=[(p["id"], p["text"]) for p in act])
    dup = [p['id'] for p in act if p['text'].strip().lower() == a.text.strip().lower()]
    if dup:
        die(f'the same preference is already active: {dup[0]}')
    n = max([int(p['id'][2:]) for p in pr['preferences']] + [0]) + 1
    item = {'id': f'PR{n:03d}', 'category': a.category, 'text': a.text.strip(), 'source_quote': a.quote.strip(), 'created_on': today(), 'status': 'active'}
    if a.event: item['event_id'] = a.event
    pr['preferences'].append(item)
    print(json.dumps({'write': commit(a.state, {'preferences': pr}), 'added': item}, ensure_ascii=False))


def cmd_pref_retire(a):
    pr = load_prefs(a.state)
    p = next((x for x in pr['preferences'] if x['id'] == a.id and x['status'] == 'active'), None)
    if not p:
        die(f'no active preference {a.id}')
    p['status'] = 'retired'; p['retired_on'] = today()
    print(json.dumps({'write': commit(a.state, {'preferences': pr}), 'retired': p}, ensure_ascii=False))


PLACEMENT_VOICE = {'words': (60, 100), 'end': (6, 6)}   # placement Speaking: short text, 6 learner turns, max. 6 min (owner decision 2026-11-11)
TEXT_WORDS = {'A1': (80, 130), 'A2': (110, 190), 'B1': (160, 260), 'B2': (220, 340), 'C1': (280, 420)}   # shared_text heard aloud (owner decision 2026-11-05)
# Every voice session is "text + conversation" (owner decision 2026-11-05): learner turns and safety minutes per level and mode
VOICE_END = {'practice': {'A1': (18, 14), 'A2': (18, 16), 'B1': (22, 20), 'B2': (28, 25), 'C1': (34, 30)},
             'exam':     {'A1': (8, 10), 'A2': (10, 12), 'B1': (12, 14), 'B2': (14, 16), 'C1': (16, 18)}}


def cmd_voice_code(a):
    """Conversation code for the voice page: EC2-<base64url(deflate-raw(brief JSON))>."""
    brief = json.load(open(a.brief, encoding='utf-8'))
    must_valid(brief, 'voice_brief')
    ins = brief['agent_instructions']
    if brief['mode'] == 'exam' and brief.get('learner_notes'):
        die('exam brief: learner_notes must be empty (do not condition the exam)')
    low = ins.lower()
    placement = brief['mode'] == 'exam' and brief.get('event_id') == 'PLACEMENT'
    st = brief.get('shared_text')
    if not st:
        die('every voice session starts with a text (shared_text) and the conversation is only about it (references/voice.md › Text + conversation)')
    if st:
        n = len(re.findall(r"[A-Za-z][A-Za-z'’-]*", st['body']))
        lo, hi = PLACEMENT_VOICE['words'] if placement else TEXT_WORDS[brief['level']]
        if not lo <= n <= hi:
            die(f'shared_text: {n} words; ' + (f'a placement text to hear has {lo}–{hi} words' if placement else f'a {brief["level"]} text to hear has {lo}–{hi} words'), words=n)
        if st['body'].strip()[:60].lower() in low:
            die('agent_instructions must not paste the shared text: the voice page adds it (with the reading rules)')
        low = low + ' ' + st['body'].lower() + ' ' + st['title'].lower()   # Gemini reads the text aloud: its words count as used
    missing = [w for w in brief['priority_vocabulary'] if not re.search(r'\b' + re.escape(w.lower()), low)]
    if missing:
        die('agent_instructions must use every priority word (the evaluator scores vocabulary with this list): ' + ', '.join(missing), missing=missing)
    if re.search(r"\b(you|now you) ask me\b|ask me (a|something|one)\b|ask me about|a question for me|your turn to ask", ins, re.I) and not any(re.search(r'\bquestion', o, re.I) for o in brief['hidden_objectives']):
        die('the instructions invite a learner question: add it to hidden_objectives (e.g. "Ask the other person a question") so Gemini checks it before ending')
    turns, mins = PLACEMENT_VOICE['end'] if placement else VOICE_END[brief['mode']][brief['level']]
    ec = brief['end_condition']
    if ec.get('target_learner_turns') != turns or ec.get('max_minutes') != mins:
        die(f'end_condition for a {"placement Speaking" if placement else brief["level"] + " " + brief["mode"]}: target_learner_turns {turns}, max_minutes {mins} (references/voice.md § 1)', expected={'target_learner_turns': turns, 'max_minutes': mins})
    if re.search(r'SESSION_END|submit_session_report|end_conversation', ins):
        die('agent_instructions must not contain the technical block (turns, ending, report): the voice page adds it')
    if brief['visible_to_learner']['situation'].strip()[:40] not in ins:
        die('agent_instructions must quote the situation the learner sees (visible_to_learner.situation)')
    payload = dict(brief)
    if brief['level'] in ('A1', 'A2') and not brief.get('pictures') and not brief.get('picture_waived_reason'):
        die('A1–A2 brief without pictures: add 1–3 pictures (references/voice.md › Pictures) or explain why not in picture_waived_reason')
    if brief.get('pictures'):
        import picture as PIC
        payload['picture_svgs'] = []
        for i, spec in enumerate(brief['pictures'], 1):
            try:
                svg, desc = PIC.render(spec)
            except (ValueError, KeyError) as e:
                die(f'picture {i}: {e}')
            if desc not in ins:
                die(f'agent_instructions must contain the description of picture {i} word for word (scripts/picture.py prints it)', description=desc)
            payload['picture_svgs'].append(svg)
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    code = 'EC2-' + base64.urlsafe_b64encode(c.compress(raw) + c.flush()).decode().rstrip('=')
    out = {'session_id': brief['session_id'], 'code': code}
    try:   # iPhone / iPad: the page is opened from a web address; the code travels in the link after '#'
        url = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json'), encoding='utf-8')).get('voice_page_url') or ''
    except Exception:
        url = ''
    if url:
        out['link'] = url.split('#')[0] + '#' + code                       # the conversation travels in the link (no Drive)
        out['drive_link'] = url.split('#')[0] + '#' + brief['session_id']   # Drive mode: the page asks the bridge for this conversation
    print(json.dumps(out, ensure_ascii=False))


def cmd_practice_log(a):
    """Formative memory: errors of the practice (voice report and/or guided practice) and failed words. No score."""
    if a.lesson not in C.lessons():
        die(f'{a.lesson} is not a lesson of the curriculum')
    err = load(a.state, 'errors'); voc = load(a.state, 'vocabulary')
    added = {'errors': 0, 'words': [], 'recycled': []}
    found = []
    if a.report:
        rp = json.load(open(a.report, encoding='utf-8')); must_valid(rp, 'voice_report')
        if rp['mode'] != 'practice':
            die('practice-log takes practice reports only: an exam is scored by the evaluator and the engine')
        if rp['session_id'] in err.get('logged_sessions', []):
            die(f"{rp['session_id']} is already in the learner memory")
        err.setdefault('logged_sessions', []).append(rp['session_id'])
        found += [{'section': e['section'], 'description': f"{e['learner_said'][:80]} → {(e.get('recast') or e['issue'])[:80]}"} for e in rp.get('errors', []) if e.get('section')]
    if a.errors:
        extra = json.load(open(a.errors, encoding='utf-8'))
        if not isinstance(extra, list) or any(not isinstance(e, dict) or not C.SEC.fullmatch(str(e.get('section', ''))) or not e.get('description') for e in extra):
            die('--errors: a JSON list of {"section": "4.1", "description": "learner said → correct form"}')
        found += [{'section': e['section'], 'description': str(e['description'])[:170]} for e in extra]
    for e in found:
        b = err['by_section'].setdefault(e['section'], {'count': 0, 'last_seen': today(), 'examples': []})
        b['count'] += 1; b['last_seen'] = today(); added['errors'] += 1
        b['examples'] = (b.get('examples', []) + [e['description']])[-5:]   # keep the 5 most recent
    vmap = {r['Oxford ID']: r['Word'] for r in C.table('vocabulary')}
    ids = lambda t: [int(x) for x in re.findall(r'\d+', t or '')]
    have = {v['oxford_id']: v for v in voc['priority_recycling']}
    for oid in ids(a.failed_words):
        if str(oid) not in vmap:
            die(f'{oid} is not an Oxford ID of the curriculum (curriculum.py words {a.lesson})')
        if oid not in have:
            v = {'oxford_id': oid, 'word': vmap[str(oid)], 'failed_in': a.lesson, 'date': today()}
            voc['priority_recycling'].append(v); have[oid] = v; added['words'].append(v['word'])
    for oid in ids(a.recycled):
        if oid in have and a.lesson not in have[oid].get('recycled_in', []):
            have[oid].setdefault('recycled_in', []).append(a.lesson); added['recycled'].append(have[oid]['word'])
    if not (found or added['words'] or added['recycled']):
        die('nothing to add: give --report (practice voice report with errors), --errors, --failed-words or --recycled')
    top = sorted(err['by_section'].items(), key=lambda kv: (-kv[1]['count'], kv[0]))[:3]
    print(json.dumps({'write': commit(a.state, {'errors': err, 'vocabulary': voc}), 'added': added,
                      'sections_with_most_errors': [{'section': k, 'count': v['count']} for k, v in top]}, ensure_ascii=False))


NOTE = re.compile(r'^english-course/notes/(\d{4}-\d{2}-\d{2})_(.+)\.md$')
VSESSION = re.compile(r'^english-course/voice-sessions/(S\d{4,})/')


def cmd_archive_plan(a):
    """Old voice sessions and notes that can move from the Claude project to the Drive archive. Read-only: the tutor moves them."""
    prog = load(a.state, 'progress', default={})
    docs = json.load(open(a.docs, encoding='utf-8'))
    if not isinstance(docs, list) or any(not isinstance(x, str) for x in docs):
        die('--docs: a JSON list with the paths of the project docs (project_info)')
    sessions = sorted({m.group(1) for x in docs for m in [VSESSION.match(x)] if m}, key=lambda z: int(z[1:]))
    keep_s = set(sessions[-a.keep:]) if a.keep > 0 else set()
    move = [x for x in docs for m in [VSESSION.match(x)] if m and m.group(1) not in keep_s]

    def unit_of(ev):
        if ev in C.lessons(): return C.lessons()[ev]['Unit']
        chk = C.by('unit_listening_checks', 'Check ID').get(ev)
        return chk['Unit'] if chk else None
    cur_unit = unit_of(prog.get('current_lesson', '')) if prog else None
    notes = sorted(x for x in docs if NOTE.match(x))
    old = [x for x in notes[:-3] if unit_of(NOTE.match(x).group(2)) != cur_unit] if prog else []
    by_unit = {}
    for x in old:
        by_unit.setdefault(unit_of(NOTE.match(x).group(2)) or 'other', []).append(x)
    need = [{'unit': u, 'summary_path': f'english-course/notes/unit-{u}.md', 'notes': v} for u, v in sorted(by_unit.items())
            if u != 'other' and f'english-course/notes/unit-{u}.md' not in docs]
    name = lambda x: x[len('english-course/'):].replace('/', '__')
    print(json.dumps({'archive': [{'path': x, 'drive_name': name(x)} for x in move + old], 'summaries_needed': need,
                      'kept_voice_sessions': sorted(keep_s, key=lambda z: int(z[1:])), 'drive_folder': 'archive',
                      'rule': 'Only with the Google Drive connector and the voice folder: first write each unit summary, then copy each doc to <voice folder>/archive/ under drive_name and delete it from the project only after Drive confirmed the copy. Without Drive: move and delete nothing.'}, ensure_ascii=False))


def cmd_export(a):
    files = {}
    for root, _, names in os.walk(a.state):
        for n in sorted(names):
            if n.endswith(('.json', '.md')):
                full = os.path.join(root, n)
                files[os.path.relpath(full, a.state).replace(os.sep, '/')] = open(full, encoding='utf-8').read()
    if 'profile.json' not in files: die('STATE has no profile.json')
    json.dump({'contract': 'state_backup/1', 'created_at': now(), 'files': files}, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(json.dumps({'out': a.out, 'files': len(files)}, ensure_ascii=False))


def cmd_import(a):
    try: b = json.load(open(a.file, encoding='utf-8'))
    except Exception: die('the backup file is not valid JSON')
    if b.get('contract') != 'state_backup/1' or 'profile.json' not in b.get('files', {}): die('this is not an English course backup file')
    written = []
    for rel, text in b['files'].items():
        if rel.startswith(('/', '..')) or '..' in rel.split('/') or not rel.endswith(('.json', '.md')): die(f'unsafe path in backup: {rel}')
        full = os.path.join(a.state, *rel.split('/')); os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, 'w', encoding='utf-8').write(text); written.append(rel)
    order = [f for f in written if f != 'progress.json'] + (['progress.json'] if 'progress.json' in written else [])
    print(json.dumps({'write': order, 'backup_created_at': b.get('created_at')}, ensure_ascii=False))


def cmd_validate(a):
    e = validate(json.load(open(a.file, encoding='utf-8')), a.schema)
    print(json.dumps({'valid': not e, 'errors': e}, ensure_ascii=False))
    sys.exit(0 if not e else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd', required=True)
    x = sp.add_parser('init'); x.add_argument('--state', required=True); x.add_argument('--student', required=True); x.add_argument('--name', required=True)
    x = sp.add_parser('consent'); x.add_argument('--state', required=True); x.add_argument('--given', required=True, choices=['yes', 'no']); x.add_argument('--version', default='v1')
    x = sp.add_parser('status'); x.add_argument('--state', required=True)
    x = sp.add_parser('attempt'); x.add_argument('--state', required=True); x.add_argument('--event', required=True); x.add_argument('--type', required=True, choices=list(DIMS))
    x = sp.add_parser('resource'); x.add_argument('--state', required=True); x.add_argument('--id', required=True)
    x = sp.add_parser('mark'); x.add_argument('--evidence', required=True); x.add_argument('--scores')
    x = sp.add_parser('score'); x.add_argument('--state', required=True); x.add_argument('--evidence', required=True); x.add_argument('--scores')
    x = sp.add_parser('repeated'); x.add_argument('--state', required=True)
    x = sp.add_parser('placement'); x.add_argument('--state', required=True); x.add_argument('--scores'); x.add_argument('--evidence')
    x = sp.add_parser('reinforced'); x.add_argument('--state', required=True)
    x = sp.add_parser('replace'); x.add_argument('--state', required=True); x.add_argument('--to', required=True); x.add_argument('--evidence', required=True)
    x = sp.add_parser('prefs'); x.add_argument('--state', required=True)
    x = sp.add_parser('pref-add'); x.add_argument('--state', required=True); x.add_argument('--category', required=True); x.add_argument('--affects', required=True, choices=list(AFFECTS)); x.add_argument('--text', required=True); x.add_argument('--quote', required=True); x.add_argument('--event')
    x = sp.add_parser('pref-retire'); x.add_argument('--state', required=True); x.add_argument('--id', required=True)
    x = sp.add_parser('practice-log'); x.add_argument('--state', required=True); x.add_argument('--lesson', required=True); x.add_argument('--report'); x.add_argument('--errors'); x.add_argument('--failed-words'); x.add_argument('--recycled')
    x = sp.add_parser('archive-plan'); x.add_argument('--state', required=True); x.add_argument('--docs', required=True); x.add_argument('--keep', type=int, default=6)
    x = sp.add_parser('voice-code'); x.add_argument('--brief', required=True)
    x = sp.add_parser('export'); x.add_argument('--state', required=True); x.add_argument('--out', required=True)
    x = sp.add_parser('import'); x.add_argument('--file', required=True); x.add_argument('--state', required=True)
    x = sp.add_parser('validate'); x.add_argument('--file', required=True); x.add_argument('--schema', required=True)
    a = p.parse_args()
    {'init': cmd_init, 'consent': cmd_consent, 'status': cmd_status, 'attempt': cmd_attempt, 'resource': cmd_resource, 'mark': cmd_mark, 'score': cmd_score,
     'practice-log': cmd_practice_log, 'archive-plan': cmd_archive_plan,
     'repeated': cmd_repeated, 'placement': cmd_placement, 'reinforced': cmd_reinforced, 'replace': cmd_replace, 'prefs': cmd_prefs, 'pref-add': cmd_pref_add, 'pref-retire': cmd_pref_retire, 'voice-code': cmd_voice_code, 'export': cmd_export, 'import': cmd_import, 'validate': cmd_validate}[a.cmd](a)


if __name__ == '__main__':
    main()
