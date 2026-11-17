#!/usr/bin/env python3
"""Simple original pictures for voice conversations, drawn from a small JSON spec (templates).

Usage:
  picture.py --spec picture.json [--svg out.svg]
Prints {"description": "...", "bytes": n}. The description goes, word for word, into the brief's
agent_instructions so that Gemini knows what the learner sees. engine.py voice-code draws the same SVG
and puts it in the conversation code.

Templates (all text in English):
  people   {"template":"people","title":"Old family photos","people":[{"name":"Lucy","age":"baby"|"child"|"adult"|"older",
            "sex":"female"|"male","label":"Aunt Rosa's baby","shirt":"red"}]}                        (1–6 people)
  home     {"template":"home","title":"Apartment for rent","rooms":[{"name":"bedroom","count":2,"note":"big"}],"details":["3rd floor"]}
  schedule {"template":"schedule","title":"My weekday","items":[{"time":"6:00","label":"wake up"}]}    (1–8 items)
  board    {"template":"board","title":"Case clues","notes":["Money gone: Sunday 2:14 a.m."],
            "notes_reason":"why a drawing would be too complex here"}                                   (1–8 notes)
           LAST RESORT (owner decision 2026-11-11): most pictures are drawings; notes only when drawing the
           content would be very complex. notes_reason (min. 15 characters) is required.
  card     {"template":"card","title":"Menu","items":[{"name":"coffee","price":"$2"}]}                (1–10 items)
  icons    {"template":"icons","title":"Radio news, 8:00 a.m.","items":[{"icon":"storm","label":"Hurricane Lina","extra":"Port Clara · strong winds"}]}
           (1–8 items; icons: see ICONS below)
  drawing  {"template":"drawing","title":"Map of Lakeview","height":460,
            "svg":"<rect x='40' y='80' width='300' height='40' fill='#ccc'/><text x='60' y='106'>Main Street</text>…",
            "description":"A map: Main Street across the top; the lake on the right; …"}
           ANY picture you draw yourself (a map, a floor plan, a street, a scene, objects on a table…): the SVG
           elements only (no <svg> tag), in a 760 × height canvas (height 160–720; the title takes the top 60 px).
           Allowed: g, rect, circle, ellipse, line, polyline, polygon, path, text, tspan, defs, linearGradient,
           radialGradient, stop and presentation attributes. No scripts, links, images, foreignObject, event
           attributes or url(http…). Max. 40 KB. "description" (required, 30–900 characters, English) tells Gemini
           what the learner sees, where things are, and every text written on the drawing.

KEYWORDS ONLY: every text on a picture is a short note (max. 6 words), never a sentence and never the
grammar the learner must produce: no verbs such as is/are/was/has/have/will/can (render() rejects them).
The learner builds the sentences; the picture only gives the facts.
"""
import argparse, json, sys
from xml.sax.saxutils import escape as esc

COLORS = {'red': '#d9534f', 'blue': '#4a7bd0', 'green': '#4caf6e', 'yellow': '#f2c14e', 'purple': '#8e6cc2',
          'orange': '#f0904a', 'pink': '#e88fb4', 'gray': '#9a9a9a', 'grey': '#9a9a9a', 'brown': '#9c6b43', 'black': '#3a3a3a', 'white': '#f4f4f4'}
PALETTE = ['#4a7bd0', '#d9534f', '#4caf6e', '#f2c14e', '#8e6cc2', '#f0904a']
W = 760


def _svg(h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" font-family="Segoe UI, Arial, sans-serif">'
            f'<rect width="{W}" height="{h}" rx="18" fill="#fbf8f2" stroke="#e3ddd0"/>'
            f'<text x="{W / 2}" y="40" text-anchor="middle" font-size="24" font-weight="700" fill="#2b2b2b">{esc(title)}</text>{body}</svg>')


def _wrap(text, n):
    words, lines, cur = str(text).split(), [], ''
    for w in words:
        if len(cur) + len(w) + 1 > n and cur: lines.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    if cur: lines.append(cur)
    return lines[:4]


def people(s):
    ps = s['people'][:6]; n = len(ps); cw = (W - 40) / n; body = []
    for i, p in enumerate(ps):
        cx = 20 + cw * i + cw / 2; age = p.get('age', 'adult'); sex = p.get('sex', 'female')
        scale = {'baby': .55, 'child': .75, 'adult': 1, 'older': .97}.get(age, 1)
        shirt = COLORS.get(str(p.get('shirt', '')).lower(), PALETTE[i % len(PALETTE)])
        hair = '#c9c9c9' if age == 'older' else ['#5a3825', '#2d2016', '#a8652e', '#e0b25a'][i % 4]
        base = 290; r = 26 * scale; hy = base - 150 * scale
        body.append(f'<rect x="{cx - cw / 2 + 8}" y="62" width="{cw - 16}" height="250" rx="14" fill="#ffffff" stroke="#e6e0d4"/>')
        if age == 'baby':
            body.append(f'<ellipse cx="{cx}" cy="{base - 40}" rx="46" ry="34" fill="{shirt}" opacity=".85"/>')
            body.append(f'<circle cx="{cx}" cy="{base - 92}" r="{r + 6}" fill="#f1c9a5"/>')
            hy = base - 92; r = r + 6
        else:
            if sex == 'female':
                body.append(f'<path d="M{cx - 30 * scale},{base} L{cx - 18 * scale},{hy + r + 4} L{cx + 18 * scale},{hy + r + 4} L{cx + 30 * scale},{base} Z" fill="{shirt}"/>')
                body.append(f'<path d="M{cx - r - 4},{hy + 14} Q{cx},{hy - r - 16} {cx + r + 4},{hy + 14} L{cx + r + 2},{hy + r + 10} L{cx - r - 2},{hy + r + 10} Z" fill="{hair}"/>')
            else:
                body.append(f'<rect x="{cx - 24 * scale}" y="{hy + r + 4}" width="{48 * scale}" height="{base - hy - r - 4}" rx="{10 * scale}" fill="{shirt}"/>')
            body.append(f'<circle cx="{cx}" cy="{hy}" r="{r}" fill="#f1c9a5"/>')
            if sex != 'female':
                body.append(f'<path d="M{cx - r},{hy - 4} Q{cx},{hy - r - 14} {cx + r},{hy - 4} Q{cx},{hy - r + 2} {cx - r},{hy - 4} Z" fill="{hair}"/>')
            if age == 'older':
                body.append(f'<rect x="{cx - 14}" y="{hy - 3}" width="11" height="7" rx="3" fill="none" stroke="#555"/><rect x="{cx + 3}" y="{hy - 3}" width="11" height="7" rx="3" fill="none" stroke="#555"/>')
        body.append(f'<circle cx="{cx - 8 * scale}" cy="{hy - 2}" r="2.4" fill="#333"/><circle cx="{cx + 8 * scale}" cy="{hy - 2}" r="2.4" fill="#333"/>')
        body.append(f'<path d="M{cx - 7 * scale},{hy + 9 * scale} Q{cx},{hy + 15 * scale} {cx + 7 * scale},{hy + 9 * scale}" stroke="#a0522d" stroke-width="2" fill="none"/>')
        body.append(f'<circle cx="{cx - cw / 2 + 28}" cy="84" r="12" fill="#efe9dc"/><text x="{cx - cw / 2 + 28}" y="89" text-anchor="middle" font-size="14" font-weight="700" fill="#777">{i + 1}</text>')
        body.append(f'<text x="{cx}" y="{base + 40}" text-anchor="middle" font-size="19" font-weight="700" fill="#2b2b2b">{esc(p.get("name", ""))}</text>')
        for j, line in enumerate(_wrap(p.get('label', ''), int(cw / 9))):
            body.append(f'<text x="{cx}" y="{base + 62 + 18 * j}" text-anchor="middle" font-size="15" fill="#555">{esc(line)}</text>')
    desc = '; '.join(f'{i + 1}) {p.get("name", "")}: {"a baby" if p.get("age") == "baby" else "a child" if p.get("age") == "child" else "an older " + ("woman" if p.get("sex") == "female" else "man") if p.get("age") == "older" else ("a woman" if p.get("sex", "female") == "female" else "a man")}'
                     + (f', in a {p["shirt"]} shirt' if p.get('shirt') else '') + (f', with the caption "{p["label"]}"' if p.get('label') else '') for i, p in enumerate(ps))
    return _svg(370, ''.join(body), s.get('title', '')), f'From left to right: {desc}.'


def home(s):
    rooms = s['rooms'][:8]; cols = 4; rw = (W - 60) / cols; body = []
    for i, rm in enumerate(rooms):
        x = 30 + rw * (i % cols); y = 70 + 120 * (i // cols)
        body.append(f'<rect x="{x}" y="{y}" width="{rw - 10}" height="105" rx="10" fill="#ffffff" stroke="#c9bfa9" stroke-width="2"/>')
        body.append(f'<text x="{x + (rw - 10) / 2}" y="{y + 45}" text-anchor="middle" font-size="34" font-weight="700" fill="{PALETTE[i % 6]}">{esc(str(rm.get("count", 1)))}</text>')
        body.append(f'<text x="{x + (rw - 10) / 2}" y="{y + 72}" text-anchor="middle" font-size="18" fill="#2b2b2b">{esc(rm["name"])}</text>')
        if rm.get('note'): body.append(f'<text x="{x + (rw - 10) / 2}" y="{y + 94}" text-anchor="middle" font-size="14" fill="#777">{esc(rm["note"])}</text>')
    y = 70 + 120 * ((len(rooms) + cols - 1) // cols) + 10
    for j, d in enumerate(s.get('details', [])[:4]):
        body.append(f'<text x="40" y="{y + 26 * j}" font-size="17" fill="#444">• {esc(d)}</text>')
    h = y + 26 * len(s.get('details', [])[:4]) + 20
    desc = 'Rooms: ' + ', '.join(f'{r.get("count", 1)} {r["name"]}' + (f' ({r["note"]})' if r.get('note') else '') for r in rooms) + '.' + (' Details: ' + '; '.join(s['details']) + '.' if s.get('details') else '')
    return _svg(h, ''.join(body), s.get('title', '')), desc


def schedule(s):
    items = s['items'][:8]; cols = 4; cw = (W - 40) / cols; body = []
    for i, it in enumerate(items):
        cx = 20 + cw * (i % cols) + cw / 2; cy = 120 + 150 * (i // cols)
        try: hh, mm = [int(x) for x in str(it['time']).split(':')[:2]]
        except ValueError: hh, mm = 12, 0
        import math
        ah = math.radians((hh % 12 + mm / 60) * 30 - 90); am = math.radians(mm * 6 - 90)
        body.append(f'<circle cx="{cx}" cy="{cy}" r="44" fill="#fff" stroke="{PALETTE[i % 6]}" stroke-width="5"/>')
        body.append(f'<line x1="{cx}" y1="{cy}" x2="{cx + 24 * math.cos(ah)}" y2="{cy + 24 * math.sin(ah)}" stroke="#333" stroke-width="5" stroke-linecap="round"/>')
        body.append(f'<line x1="{cx}" y1="{cy}" x2="{cx + 34 * math.cos(am)}" y2="{cy + 34 * math.sin(am)}" stroke="#333" stroke-width="3" stroke-linecap="round"/>')
        body.append(f'<text x="{cx}" y="{cy + 70}" text-anchor="middle" font-size="18" font-weight="700" fill="#2b2b2b">{esc(it["time"])}</text>')
        body.append(f'<text x="{cx}" y="{cy + 92}" text-anchor="middle" font-size="16" fill="#555">{esc(it["label"])}</text>')
    h = 120 + 150 * ((len(items) + cols - 1) // cols) - 20
    return _svg(h, ''.join(body), s.get('title', '')), 'Clocks: ' + '; '.join(f'{it["time"]} {it["label"]}' for it in items) + '.'


def board(s):
    notes = s['notes'][:8]; cols = 4; nw = (W - 60) / cols; body = []
    fills = ['#fff3a8', '#cfe8ff', '#ffd6d6', '#d8f5d0']
    for i, t in enumerate(notes):
        x = 30 + nw * (i % cols); y = 70 + 150 * (i // cols)
        body.append(f'<rect x="{x}" y="{y}" width="{nw - 12}" height="134" rx="6" fill="{fills[i % 4]}" stroke="#d9cfa0"/><circle cx="{x + (nw - 12) / 2}" cy="{y + 10}" r="6" fill="#d9534f"/>')
        for j, line in enumerate(_wrap(t, int((nw - 20) / 8.5))):
            body.append(f'<text x="{x + 12}" y="{y + 42 + 22 * j}" font-size="16" fill="#2b2b2b">{esc(line)}</text>')
    h = 70 + 150 * ((len(notes) + cols - 1) // cols) + 10
    return _svg(h, ''.join(body), s.get('title', '')), 'Notes on the board: ' + ' | '.join(notes) + '.'


def card(s):
    items = s['items'][:10]; body = []
    for i, it in enumerate(items):
        y = 90 + 38 * i
        body.append(f'<text x="80" y="{y}" font-size="20" fill="#2b2b2b">{esc(it["name"])}</text>')
        body.append(f'<line x1="{100 + 11 * len(it["name"])}" y1="{y - 6}" x2="{W - 180}" y2="{y - 6}" stroke="#ccc" stroke-dasharray="3 5"/>')
        body.append(f'<text x="{W - 80}" y="{y}" text-anchor="end" font-size="20" font-weight="700" fill="{PALETTE[i % 6]}">{esc(str(it.get("price", "")))}</text>')
    return _svg(90 + 38 * len(items), ''.join(body), s.get('title', '')), 'Items: ' + '; '.join(f'{it["name"]} {it.get("price", "")}'.strip() for it in items) + '.'


# ---------------- icons: simple, original flat drawings in a 80×80 box centred on (x, y)
def _i(x, y, parts):
    return f'<g transform="translate({x - 40},{y - 40})">' + parts + '</g>'
ICONS = {
  'storm': '<path d="M18 44a14 14 0 0 1 4-27 18 18 0 0 1 34 4 12 12 0 0 1 4 23z" fill="#8a9bb0"/><path d="M40 46l-8 14h8l-5 14 14-18h-8l5-10z" fill="#f2c14e"/>',
  'wind': '<path d="M10 30h42a8 8 0 1 0-8-8M10 44h56a8 8 0 1 1-8 8M10 58h30" stroke="#6b8fb5" stroke-width="6" fill="none" stroke-linecap="round"/>',
  'rain': '<path d="M18 40a14 14 0 0 1 4-27 18 18 0 0 1 34 4 12 12 0 0 1 4 23z" fill="#9fb3c8"/><path d="M26 50l-4 10M40 50l-4 10M54 50l-4 10" stroke="#4a7bd0" stroke-width="5" stroke-linecap="round"/>',
  'flood': '<path d="M8 40c8-8 16 8 24 0s16 8 24 0 16 8 24 0M8 54c8-8 16 8 24 0s16 8 24 0 16 8 24 0M8 68c8-8 16 8 24 0s16 8 24 0 16 8 24 0" stroke="#4a7bd0" stroke-width="5" fill="none"/><path d="M28 32v-14l12-8 12 8v14" fill="#c9bfa9"/>',
  'fire': '<path d="M40 8c4 14 18 20 18 38a18 18 0 0 1-36 0c0-10 6-14 8-22 4 6 4 10 8 10 2-8-2-16 2-26z" fill="#f0904a"/><path d="M40 40c2 6 8 8 8 16a8 8 0 0 1-16 0c0-6 6-8 8-16z" fill="#f2c14e"/>',
  'explosion': '<path d="M40 6l7 18 18-8-8 18 18 7-18 7 8 18-18-8-7 18-7-18-18 8 8-18-18-7 18-7-8-18 18 8z" fill="#f0904a"/><circle cx="40" cy="40" r="12" fill="#f2c14e"/>',
  'school': '<path d="M8 34l32-20 32 20z" fill="#d9534f"/><rect x="14" y="34" width="52" height="34" fill="#f4e3c3"/><rect x="34" y="48" width="12" height="20" fill="#9c6b43"/><rect x="20" y="40" width="10" height="9" fill="#9fc3e8"/><rect x="50" y="40" width="10" height="9" fill="#9fc3e8"/>',
  'closed': '<circle cx="40" cy="40" r="28" fill="none" stroke="#d9534f" stroke-width="7"/><path d="M20 60L60 20" stroke="#d9534f" stroke-width="7"/>',
  'house': '<path d="M10 38l30-24 30 24z" fill="#9c6b43"/><rect x="18" y="38" width="44" height="32" fill="#f4e3c3"/><rect x="34" y="50" width="12" height="20" fill="#4a7bd0"/>',
  'building': '<rect x="20" y="10" width="40" height="62" fill="#b8c2cc"/>' + ''.join(f'<rect x="{x}" y="{y}" width="8" height="8" fill="#fff"/>' for x in (26, 36, 46) for y in (18, 32, 46)),
  'factory': '<path d="M8 70V38l18 10V38l18 10V38l18 10V20h10v50z" fill="#9a9a9a"/><rect x="62" y="8" width="8" height="14" fill="#6b6b6b"/>',
  'hospital': '<rect x="14" y="14" width="52" height="56" rx="6" fill="#f4f4f4" stroke="#ccc"/><path d="M34 26h12v12h12v12H46v12H34V50H22V38h12z" fill="#d9534f"/>',
  'person': '<circle cx="40" cy="22" r="12" fill="#f1c9a5"/><path d="M18 72a22 24 0 0 1 44 0z" fill="#4a7bd0"/>',
  'people': '<circle cx="28" cy="26" r="10" fill="#f1c9a5"/><circle cx="52" cy="26" r="10" fill="#e0b48a"/><path d="M10 70a18 22 0 0 1 36 0zM34 70a18 22 0 0 1 36 0z" fill="#4caf6e"/>',
  'car': '<path d="M10 52l8-18h44l8 18v10H10z" fill="#d9534f"/><circle cx="24" cy="62" r="7" fill="#333"/><circle cx="56" cy="62" r="7" fill="#333"/><rect x="24" y="38" width="32" height="10" fill="#cfe3f5"/>',
  'plane': '<path d="M40 8c4 0 5 6 5 12v12l26 14v6l-26-6v14l8 6v4l-13-3-13 3v-4l8-6V46l-26 6v-6l26-14V20c0-6 1-12 5-12z" fill="#6b8fb5"/>',
  'train': '<rect x="18" y="12" width="44" height="48" rx="8" fill="#4a7bd0"/><rect x="24" y="20" width="32" height="14" fill="#cfe3f5"/><circle cx="28" cy="48" r="4" fill="#f2c14e"/><circle cx="52" cy="48" r="4" fill="#f2c14e"/><path d="M22 72l8-12M58 72l-8-12" stroke="#555" stroke-width="4"/>',
  'bag': '<path d="M28 26a12 12 0 0 1 24 0" stroke="#3a3a3a" stroke-width="5" fill="none"/><rect x="16" y="26" width="48" height="44" rx="8" fill="#3a3a3a"/><rect x="26" y="40" width="28" height="4" fill="#d9534f"/>',
  'phone': '<rect x="26" y="8" width="28" height="64" rx="6" fill="#3a3a3a"/><rect x="30" y="16" width="20" height="44" fill="#9fc3e8"/>',
  'keys': '<circle cx="28" cy="30" r="12" fill="none" stroke="#c9a227" stroke-width="6"/><path d="M38 38l26 26M54 54l6-6M60 60l6-6" stroke="#c9a227" stroke-width="6" stroke-linecap="round"/>',
  'book': '<path d="M12 18h26v50H12zM42 18h26v50H42z" fill="#4caf6e"/><path d="M38 18h4v50h-4z" fill="#2e7d4f"/>',
  'clock': '<circle cx="40" cy="40" r="28" fill="#fff" stroke="#4a7bd0" stroke-width="6"/><path d="M40 40V22M40 40h12" stroke="#333" stroke-width="5" stroke-linecap="round"/>',
  'money': '<rect x="10" y="22" width="60" height="36" rx="6" fill="#4caf6e"/><circle cx="40" cy="40" r="10" fill="#d8f5d0"/>',
  'food': '<circle cx="40" cy="44" r="26" fill="#fff" stroke="#ccc"/><circle cx="40" cy="44" r="14" fill="#f0904a"/><path d="M12 12v22M70 12v22" stroke="#9a9a9a" stroke-width="4"/>',
  'coffee': '<path d="M16 30h40v22a16 16 0 0 1-16 16h-8a16 16 0 0 1-16-16z" fill="#9c6b43"/><path d="M56 36h6a8 8 0 0 1 0 16h-6" stroke="#9c6b43" stroke-width="5" fill="none"/>',
  'shirt': '<path d="M26 12l-16 12 8 12 8-6v40h28V30l8 6 8-12-16-12a14 10 0 0 1-28 0z" fill="#d9534f"/>',
  'tree': '<rect x="36" y="46" width="8" height="26" fill="#9c6b43"/><circle cx="40" cy="34" r="22" fill="#4caf6e"/>',
  'sun': '<circle cx="40" cy="40" r="16" fill="#f2c14e"/>' + ''.join(f'<path d="M40 40l0 -28" transform="rotate({a} 40 40)" stroke="#f2c14e" stroke-width="5" stroke-dasharray="0 18 10"/>' for a in range(0, 360, 45)),
  'warning': '<path d="M40 10l32 58H8z" fill="#f2c14e"/><path d="M40 30v20" stroke="#333" stroke-width="6" stroke-linecap="round"/><circle cx="40" cy="58" r="4" fill="#333"/>',
  'mayor': '<circle cx="40" cy="22" r="12" fill="#f1c9a5"/><path d="M18 72a22 24 0 0 1 44 0z" fill="#3a3a3a"/><path d="M36 40h8l-4 18z" fill="#d9534f"/>',
  'radio': '<rect x="10" y="26" width="60" height="40" rx="6" fill="#8e6cc2"/><circle cx="54" cy="46" r="11" fill="#e8ddf5"/><rect x="18" y="36" width="22" height="4" fill="#e8ddf5"/><rect x="18" y="46" width="22" height="4" fill="#e8ddf5"/><path d="M20 26l30-16" stroke="#555" stroke-width="3"/>',
}


def icons(s):
    items = s['items'][:8]; cols = min(4, len(items)) or 1; cw = (W - 40) / cols; body = []
    for i, it in enumerate(items):
        if it.get('icon') not in ICONS: raise ValueError(f"unknown icon {it.get('icon')!r}; use one of {sorted(ICONS)}")
        x0 = 20 + cw * (i % cols); y0 = 64 + 210 * (i // cols); cx = x0 + cw / 2
        body.append(f'<rect x="{x0 + 6}" y="{y0}" width="{cw - 12}" height="196" rx="14" fill="#ffffff" stroke="#e6e0d4"/>')
        body.append(_i(cx, y0 + 58, ICONS[it['icon']]))
        lab = it.get('label', ''); fs = max(12, min(18, int((cw - 26) / (0.58 * max(1, len(lab))))))
        body.append(f'<text x="{cx}" y="{y0 + 126}" text-anchor="middle" font-size="{fs}" font-weight="700" fill="#2b2b2b">{esc(lab)}</text>')
        for j, line in enumerate(_wrap(it.get('extra', ''), int((cw - 24) / 8.2))[:3]):
            body.append(f'<text x="{cx}" y="{y0 + 150 + 19 * j}" text-anchor="middle" font-size="15" fill="#555">{esc(line)}</text>')
    h = 64 + 210 * ((len(items) + cols - 1) // cols) + 6
    if not any(it.get('extra') for it in items): h -= 50
    desc = 'Picture cards (icons with key words; the learner makes the sentences): ' + '; '.join(
        f'{i + 1}) {"an" if it["icon"][0] in "aeiou" else "a"} {it["icon"]} icon, "{it.get("label", "")}"' + (f', notes "{it["extra"]}"' if it.get('extra') else '') for i, it in enumerate(items)) + '.'
    return _svg(h, ''.join(body), s.get('title', '')), desc


import xml.etree.ElementTree as _ET
SVG_NS = '{http://www.w3.org/2000/svg}'
DRAW_TAGS = {'g', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path', 'text', 'tspan', 'defs', 'linearGradient', 'radialGradient', 'stop'}
DRAW_ATTRS = {'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'width', 'height', 'd', 'points', 'transform', 'fill', 'stroke',
              'stroke-width', 'stroke-dasharray', 'stroke-linecap', 'stroke-linejoin', 'opacity', 'fill-opacity', 'stroke-opacity', 'font-size',
              'font-weight', 'font-style', 'font-family', 'text-anchor', 'dominant-baseline', 'letter-spacing', 'id', 'offset', 'stop-color',
              'stop-opacity', 'gradientUnits', 'gradientTransform', 'fx', 'fy', 'dx', 'dy', 'rotate', 'fill-rule', 'clip-rule', 'style'}


def _drawing_texts(spec):
    try:
        root = _ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{spec.get("svg", "")}</svg>')
    except _ET.ParseError as e:
        raise ValueError(f'drawing: the svg is not valid XML ({e})')
    out = []
    for el in root.iter():
        if el.tag.replace(SVG_NS, '') == 'text':
            t = ' '.join(''.join(el.itertext()).split())
            if t: out.append(t)
    return root, out


def drawing(s):
    body = str(s.get('svg', '')).strip(); desc = ' '.join(str(s.get('description', '')).split())
    if not body: raise ValueError('drawing: "svg" is empty')
    if len(body) > 40000: raise ValueError(f'drawing: svg too big ({len(body)} > 40000 characters)')
    if not 30 <= len(desc) <= 900: raise ValueError('drawing: "description" is required (30–900 characters): what the learner sees, where things are and every text on it')
    h = int(s.get('height', 460))
    if not 160 <= h <= 720: raise ValueError('drawing: height must be 160–720')
    root, _ = _drawing_texts(s)
    for el in list(root.iter())[1:]:
        tag = el.tag.replace(SVG_NS, '')
        if tag not in DRAW_TAGS: raise ValueError(f'drawing: <{tag}> is not allowed; use {sorted(DRAW_TAGS)}')
        for k, v in el.attrib.items():
            k2 = k.split('}')[-1]
            if k2 not in DRAW_ATTRS: raise ValueError(f'drawing: attribute {k2!r} on <{tag}> is not allowed')
            if _re.search(r'url\(\s*[^#\s)]|javascript:|expression\(|@import', str(v), _re.I): raise ValueError(f'drawing: {k2}="{v}" is not allowed (only url(#id))')
    return _svg(h, f'<g font-size="16" fill="#2b2b2b">{body}</g>', s.get('title', '')), 'Drawing: ' + desc


TEMPLATES = {'people': people, 'home': home, 'schedule': schedule, 'board': board, 'card': card, 'icons': icons, 'drawing': drawing}

import re as _re
VERBS = _re.compile(r"\b(am|is|are|was|were|be|been|being|has|have|had|having|will|would|shall|should|can|could|may|might|must|do|does|did|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't|won't|can't|didn't|doesn't|don't)\b", _re.I)


def _texts(spec):
    """Every text the learner will see on the picture."""
    t = spec.get('template'); out = [spec.get('title', '')]
    if t == 'people': out += [p.get('label', '') for p in spec.get('people', [])]
    elif t == 'home': out += [r.get('note', '') for r in spec.get('rooms', [])] + list(spec.get('details', []))
    elif t == 'schedule': out += [i.get('label', '') for i in spec.get('items', [])]
    elif t == 'board': out += list(spec.get('notes', []))
    elif t == 'card': out += [i.get('name', '') for i in spec.get('items', [])]
    elif t == 'icons': out += [i.get('label', '') for i in spec.get('items', [])] + [i.get('extra', '') for i in spec.get('items', [])]
    elif t == 'drawing': out += _drawing_texts(spec)[1]
    return [str(x) for x in out if x]


def check_keywords(spec):
    """Pictures give facts as key words, never sentences or the grammar the learner must produce."""
    for txt in _texts(spec):
        words = [w for w in _re.split(r'[\s·|,;:/]+', txt) if w]
        if len(words) > 6: raise ValueError(f'too many words ({len(words)} > 6): "{txt}" — use key words, not sentences')
        m = VERBS.search(txt)
        if m: raise ValueError(f'"{txt}" contains the verb "{m.group(0)}": pictures show key words only; the learner makes the sentences')


def render(spec):
    t = spec.get('template')
    if t not in TEMPLATES: raise ValueError(f'unknown template {t!r}; use one of {sorted(TEMPLATES)}')
    check_keywords(spec)
    if t == 'board' and len(str(spec.get('notes_reason', '')).strip()) < 15:
        raise ValueError('board (notes) is the last resort: draw the picture instead (template "drawing" or a drawn template), '
                         'or explain in notes_reason (min. 15 characters) why drawing it would be very complex')
    svg, desc = TEMPLATES[t](spec)
    title = spec.get('title')
    return svg, (f'Picture "{title}". ' if title else 'Picture. ') + desc


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--spec', required=True); ap.add_argument('--svg')
    a = ap.parse_args()
    try:
        svg, desc = render(json.load(open(a.spec, encoding='utf-8')))
    except (ValueError, KeyError) as e:
        print(json.dumps({'error': f'picture spec: {e}'})); sys.exit(1)
    if a.svg: open(a.svg, 'w', encoding='utf-8').write(svg)
    print(json.dumps({'description': desc, 'bytes': len(svg)}, ensure_ascii=False))
