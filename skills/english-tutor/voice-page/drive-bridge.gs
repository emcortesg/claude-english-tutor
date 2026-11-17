/**
 * English course — Drive bridge for the voice page (Google Apps Script web app).
 *
 * The tutor (Claude, with the Google Drive connector) saves each conversation code in
 *   <ROOT>/voice-briefs/conversation-SXXXX.txt
 * The voice page asks this script for one conversation by its number (the tutor's link ends in #SXXXX), or for
 * the newest conversation without a report when the link has no number, and at the end it sends
 * the report here, saved as <ROOT>/voice-reports/voice-report-SXXXX.json, where the tutor reads it.
 *
 * Set up once (owner of the Drive folder):
 *   1. script.google.com › New project › paste this file › put the ID of the "English course (voice)" folder in ROOT_ID.
 *   2. Deploy › New deployment › Web app · Execute as: Me · Who has access: Anyone › Deploy › authorize.
 *      Copy the "Web app URL" shown (…/macros/s/<long id>/exec) into WEB_APP_URL below and save.
 *      (Do not use the editor's test URL: it only works for you, so the page cannot use it.)
 *   3. Run connectionCode() and copy the line from the execution log into the voice page
 *      ("Connect Google Drive"), on every device you use. Never paste it in the chat.
 * To update a script that is already deployed (bridge version 2, 2026-11-11): paste this file over the old code,
 *   write your ROOT_ID and WEB_APP_URL again, save, then Deploy › Manage deployments › pencil › Version: New version ›
 *   Deploy. The address and the key stay the same, so nothing changes in the voice page.
 * The script only touches ROOT_ID and its two subfolders. Every call needs the secret key (k).
 */
var ROOT_ID = 'PUT_THE_FOLDER_ID_HERE';
var WEB_APP_URL = 'PUT_THE_WEB_APP_URL_HERE';   // Deploy › Manage deployments › Web app › URL

function key_() {
  var p = PropertiesService.getScriptProperties(), k = p.getProperty('KEY');
  if (!k) { k = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, ''); p.setProperty('KEY', k); }
  return k;
}
function connectionCode() {
  var url = String(WEB_APP_URL || '').trim();
  if (!/^https:\/\/script\.google\.com\/.*\/s\/[\w-]+\/exec$/.test(url)) { Logger.log('Copy the Web app URL (Deploy › Manage deployments › Web app › URL, it ends in /exec) into WEB_APP_URL, save, and run connectionCode again.'); return; }
  Logger.log('Paste this in the voice page (Connect Google Drive): ' + url + '?k=' + key_());
}
function newKey() {   // run it if the connection line was shared by mistake; then paste the new line in the page
  PropertiesService.getScriptProperties().deleteProperty('KEY'); connectionCode();
}
function sub_(name) {
  var root = DriveApp.getFolderById(ROOT_ID), it = root.getFoldersByName(name);
  return it.hasNext() ? it.next() : root.createFolder(name);
}
function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

/* GET ?k=KEY&action=get&id=S0022 → { ok, session_id, code, done }   that conversation (code null if it is not there;
                                                                      done = it already has a report)
   GET ?k=KEY&action=next           → { ok, session_id, code }         the newest conversation (by date) without a report
   GET ?k=KEY&action=ping           → { ok, version } */
function doGet(e) {
  var p = (e && e.parameter) || {};
  if (p.k !== key_()) return out_({ ok: false, error: 'bad_key' });
  if (p.action === 'ping') return out_({ ok: true, version: 2 });
  var done = {}, r = sub_('voice-reports').getFiles();
  while (r.hasNext()) { var m1 = /^voice-report-(S\d+)\.json$/.exec(r.next().getName()); if (m1) done[m1[1]] = true; }
  if (p.action === 'get') {
    if (!/^S\d{4,}$/.test(p.id || '')) return out_({ ok: false, error: 'bad_id' });
    var one = null, oneT = 0, g = sub_('voice-briefs').getFilesByName('conversation-' + p.id + '.txt');
    while (g.hasNext()) { var x = g.next(), xt = x.getLastUpdated().getTime(); if (!x.isTrashed() && xt > oneT) { one = x; oneT = xt; } }
    if (!one) return out_({ ok: true, session_id: p.id, code: null, error: 'not_found' });
    return out_({ ok: true, session_id: p.id, code: one.getBlob().getDataAsString().trim(), done: !!done[p.id] });
  }
  var best = null, bestT = 0, b = sub_('voice-briefs').getFiles();
  while (b.hasNext()) {
    var f = b.next(), m2 = /^conversation-(S\d+)\.txt$/.exec(f.getName());
    if (!m2 || done[m2[1]] || f.isTrashed()) continue;
    var t = f.getDateCreated().getTime();   // the newest file, not the highest number: an old test with a high number is not opened
    if (t > bestT) { best = f; bestT = t; }
  }
  if (!best) return out_({ ok: true, code: null });
  return out_({ ok: true, session_id: /^conversation-(S\d+)\.txt$/.exec(best.getName())[1], code: best.getBlob().getDataAsString().trim() });
}

/* POST (text/plain) {"k": KEY, "name": "voice-report-SXXXX.json", "text": "<report JSON>"} → { ok, saved } */
function doPost(e) {
  var d;
  try { d = JSON.parse(e.postData.contents); } catch (x) { return out_({ ok: false, error: 'bad_json' }); }
  if (!d || d.k !== key_()) return out_({ ok: false, error: 'bad_key' });
  if (!/^voice-report-S\d+\.json$/.test(d.name || '') || typeof d.text !== 'string' || d.text.length > 2000000) return out_({ ok: false, error: 'bad_report' });
  var folder = sub_('voice-reports'), it = folder.getFilesByName(d.name);
  if (it.hasNext()) it.next().setContent(d.text); else folder.createFile(d.name, d.text, 'application/json');
  return out_({ ok: true, saved: d.name });
}
