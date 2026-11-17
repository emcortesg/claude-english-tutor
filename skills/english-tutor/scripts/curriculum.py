#!/usr/bin/env python3
"""Read-only queries on the English A1–C1 curriculum (v3.1).

Usage:
  curriculum.py lesson L001            Lesson package (spec, reading, conversation, assessment, vocabulary); rubrics: use `rubrics`
  curriculum.py event ULC-A1-U01       Listening check (source + Form A items), EXIT-A1 (components) or a lesson
  curriculum.py next L001              Next event in Course_Sequence (lesson, standalone listening check or level exit)
  curriculum.py embedded L400          Listening check embedded in that lesson (if any)
  curriculum.py prereqs L024           REQUIRED prerequisite lessons
  curriculum.py unit A1-U01            Unit: section, lessons, vocabulary (for placement probes)
  curriculum.py level A1               Content units of the level in order, sections and a vocabulary sample
  curriculum.py rubrics A1 lesson|exit Rubrics that apply at the level + calibration
  curriculum.py words L001             Lesson vocabulary (Oxford ID, word, class, sense hint; phonetics, examples and audio are not included in the public version: see Dictionary URL)
  curriculum.py lesson-of-section 4.1  Lessons that teach a section
  curriculum.py subpoints 4.1          Sub-points of a grammar section (what exactly it covers) and the lessons that cover each one
  curriculum.py policy [P06]           Assessment policy rules (all of them, or one)
Output: JSON on stdout.
"""
import csv, json, os, random, re, sys
from functools import lru_cache

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1']
LID = re.compile(r'L\d{3}')
SEC = re.compile(r'\d\.\d+a?')


@lru_cache(None)
def table(name):
    with open(os.path.join(DATA, name + '.csv'), encoding='utf-8', newline='') as f:
        return [{k: v for k, v in r.items()} for r in csv.DictReader(f)]


def clean(d):
    return {k: v for k, v in d.items() if v not in ('', None)}


@lru_cache(None)
def lessons():
    return {r['Lesson ID']: r for r in table('lessons')}


def seq(lid):
    return int(float(lessons()[lid]['Course seq']))


def by(name, key):
    return {r[key]: r for r in table(name)}


def words(lid):
    out = []
    for r in table('vocabulary'):
        if r['Lesson ID'] == lid:
            out.append(clean({'oxford_id': int(r['Oxford ID']), 'word': r['Word'], 'class': r['Word class'], 'us_teaching_form': r['US teaching form'],
                              'us_phonetics': r.get('US phonetics', ''), 'sense_hint': r['Sense hint (AI-generated)'],
                              'example': (r.get('Examples (Oxford)') or '').split('\n')[0].strip(), 'us_audio': r.get('US audio (mp3)', ''),
                              'lexical_status': r['Lexical status'], 'order': int(r['Order in lesson'] or 0)}))
    return sorted(out, key=lambda w: w.get('order', 0))


def rubrics(level, kind):
    pref = {'lesson': ('RB-LS', 'RB-LW'), 'exit': ('RB-XS', 'RB-XW')}[kind]
    li = LEVELS.index(level)
    rows = [clean(r) for r in table('rubrics') if r['Rubric ID'].startswith(pref) and LEVELS.index(r['From level']) <= li]
    cal = clean(by('rubric_calibration', 'Level')[level])
    return {'rubrics': rows, 'calibration': cal}


def embedded(lid):
    for r in table('unit_listening_checks'):
        if r['Mode'] != 'Standalone after host lesson' and lid in LID.findall(r['Host lesson / position']):
            return listening(r['Check ID'])
    return None


def listening(cid):
    chk = clean(by('unit_listening_checks', 'Check ID')[cid])
    src = clean(next(r for r in table('listening_sources') if r['Check ID'] == cid))
    items = [clean(r) for r in table('listening_items') if r['Check ID'] == cid]
    return {'event_type': 'unit_listening_check', 'check': chk, 'source': src, 'form_a_items': items,
            'rules': 'P06: global ≥80% of items; 70% only for sub-skills with ≥4 items. Retests: P14 (new items). Audio: play in full.'}


def lesson(lid):
    L = clean(lessons()[lid])
    lpa = clean(by('lesson_practice_assessment', 'Lesson ID')[lid])
    rs = clean(by('reading_specs', 'Lesson ID')[lid])
    ws = [{k: v for k, v in w.items() if k not in ('us_audio', 'order')} for w in words(lid)]   # audio links: curriculum.py words
    out = {'lesson': L, 'practice_assessment': lpa, 'reading_spec': rs, 'words': ws,
           'grammar_section': None, 'review_plan': None, 'embedded_listening_check': embedded(lid),
           'lexical_chunks': clean(by('lexical_chunks_spec', 'Lesson ID')[lid]) if lid in by('lexical_chunks_spec', 'Lesson ID') else None,
           'prerequisites_required': prereqs(lid)}
    gs = by('grammar_sections', 'Section')
    secs = SEC.findall(L.get('Grammar section', ''))
    out['grammar_section'] = [clean(gs[s]) for s in secs if s in gs]
    if L['Lesson type'] == 'Review':
        out['review_plan'] = clean(next(r for r in table('review_plan') if r['Lesson ID'] == lid))
    return out


def sequence():
    return table('course_sequence')


def next_event(eid):
    s = sequence()
    ids = [r['Event ID'] for r in s]
    if eid not in ids:
        raise SystemExit(json.dumps({'error': f'{eid} is not in Course_Sequence (embedded listening check?)'}))
    i = ids.index(eid)
    return clean(s[i + 1]) if i + 1 < len(s) else None


def prereqs(lid):
    req = sorted({r['Resolved lesson'] for r in table('prerequisite_map') if r['Dependent lesson'] == lid and r['Requirement'] == 'REQUIRED' and r['Resolved lesson']}, key=seq)
    return req


def unit(uid):
    ls = sorted([l for l in lessons().values() if l['Unit'] == uid], key=lambda l: seq(l['Lesson ID']))
    if not ls:
        raise SystemExit(json.dumps({'error': f'unit {uid} does not exist'}))
    secs = sorted({s for l in ls for s in SEC.findall(l['Grammar section'])})
    keep = ('oxford_id', 'word', 'class', 'sense_hint')   # enough to write placement items; full entries: curriculum.py words
    vocab = [dict({k: w[k] for k in keep if k in w}, lesson_id=l['Lesson ID']) for l in ls for w in words(l['Lesson ID'])]
    gs = by('grammar_sections', 'Section')
    return {'unit': uid, 'level': ls[0]['Level'], 'unit_grammar': ls[0]['Unit grammar'], 'sections': [clean(gs[s]) for s in secs if s in gs],
            'lessons': [{'lesson_id': l['Lesson ID'], 'type': l['Lesson type'], 'title': l['Title'], 'grammar_focus': l['Grammar focus']} for l in ls],
            'first_lesson': ls[0]['Lesson ID'], 'vocabulary': vocab}


def content_units(level):
    seen = []
    for l in sorted(lessons().values(), key=lambda l: seq(l['Lesson ID'])):
        if l['Level'] == level and l['Lesson type'] in ('Core', 'Application') and l['Unit'] not in seen:
            seen.append(l['Unit'])
    return seen


def level(lv, sample=40, seed=None):
    units = content_units(lv)
    gs = [clean(r) for r in table('grammar_sections') if r['Level (PDF chapter)'] == lv]
    voc = [r for r in table('vocabulary') if r['Level'] == lv]
    rnd = random.Random(seed)
    smp = rnd.sample(voc, min(sample, len(voc)))
    final = next(r['Lesson ID'] for r in table('review_plan') if r['Level'] == lv and r['Type'] == 'Level final review')
    return {'level': lv, 'content_units': units, 'final_review': final, 'sections': gs,
            'vocabulary_sample': [{'oxford_id': int(r['Oxford ID']), 'word': r['Word'], 'class': r['Word class'], 'lesson_id': r['Lesson ID']} for r in smp],
            'placement_spec': [clean(r) for r in table('placement_test')]}


def subpoints(sec):
    rows = [r for r in table('grammar_subpoints') if r['Section'] == sec]
    if not rows:
        raise SystemExit(json.dumps({'error': f'section {sec} has no sub-points'}))
    return [clean({'id': r['Sub-point ID'], 'sub_point': r['PDF sub-point (paraphrase of the source section)'], 'lessons': r['Covering lessons']}) for r in rows]


def policy(pid=None):
    rows = [clean(r) for r in table('assessment_policy') if pid in (None, r['Rule ID'])]
    if not rows:
        raise SystemExit(json.dumps({'error': f'{pid} is not a rule of Assessment_Policy'}))
    return rows


def event(eid):
    if eid.startswith('ULC-'):
        return listening(eid)
    if eid.startswith('EXIT-'):
        comps = [clean(r) for r in table('level_exit_assessments') if r['Exit assessment'] == eid]
        lv = comps[0]['Level']
        return {'event_type': 'level_exit', 'components': comps, **rubrics(lv, 'exit'),
                'level_sections': [r['Section'] for r in table('grammar_sections') if r['Level (PDF chapter)'] == lv]}
    return lesson(eid)


def main(a):
    if a[:1] == ['policy']:
        print(json.dumps(policy(a[1] if len(a) > 1 else None), ensure_ascii=False, separators=(',', ':'))); return
    if len(a) < 2:
        print(__doc__); return
    cmd, arg = a[0], a[1]
    if cmd == 'lesson': out = lesson(arg)
    elif cmd == 'event': out = event(arg)
    elif cmd == 'next': out = next_event(arg)
    elif cmd == 'embedded': out = embedded(arg)
    elif cmd == 'prereqs': out = prereqs(arg)
    elif cmd == 'unit': out = unit(arg)
    elif cmd == 'level': out = level(arg, seed=a[2] if len(a) > 2 else None)
    elif cmd == 'rubrics': out = rubrics(arg, a[2] if len(a) > 2 else 'lesson')
    elif cmd == 'words': out = words(arg)
    elif cmd == 'subpoints': out = subpoints(arg)
    elif cmd == 'lesson-of-section': out = [l['Lesson ID'] for l in sorted(lessons().values(), key=lambda l: seq(l['Lesson ID'])) if arg in SEC.findall(l['Grammar section'])]
    else:
        print(__doc__); return
    print(json.dumps(out, ensure_ascii=False, separators=(',', ':')))   # compact: fewer tokens


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except (KeyError, StopIteration, IndexError) as e:
        print(json.dumps({'error': f'ID not found in the curriculum: {e}'}, ensure_ascii=False)); sys.exit(1)
