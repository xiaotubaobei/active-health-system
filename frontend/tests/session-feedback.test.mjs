import test from 'node:test';
import assert from 'node:assert/strict';
import { useSessionFeedback } from '../src/composables/useSessionFeedback.js';

const defer = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const record = (changes = {}) => ({ performed: true, completion: 'partial', effort: 'hard', discomfort: true,
  note: '最后一组没做完', revision: 1, updated_at: '2026-11-25T03:00:00', ...changes });
const response = row => ({ data: { feedback: row } });
function state(api, id = () => 1) {
  return useSessionFeedback({ api, sessionId: id, errorMessage: (e, fallback) => e.response?.data?.detail || fallback });
}
function fill(s, changes = {}) {
  s.form.value = { performed: 'training', completion: 'partial', effort: 'hard', discomfort: 'yes',
    note: '最后一组没做完', ...changes };
}

test('blank feedback has no inferred success or comfort; incomplete answers never post', async () => {
  let calls = 0;
  const s = state({ get: async () => response(null), put: async () => { calls++; } });
  await s.load();
  assert.equal(s.form.value.performed, '');
  assert.equal(s.form.value.discomfort, '');
  assert.equal(s.dirty.value, false);
  s.form.value.note = '只写了一句说明';
  await s.save();
  assert.match(s.saveError.value, /请选择|请先选择/);
  s.form.value.performed = 'training';
  await s.save();
  assert.match(s.saveError.value, /填完整/);
  assert.equal(calls, 0);
});

test('load failure blocks creating an empty replacement and supports explicit retry', async () => {
  let attempt = 0, calls = 0;
  const s = state({ get: async () => { if (++attempt === 1) throw new Error('offline'); return response(record()); },
    put: async () => { calls++; } });
  await s.load();
  assert.equal(s.loaded.value, false);
  assert.match(s.loadError.value, /重新加载/);
  fill(s); await s.save();
  assert.equal(calls, 0);
  await s.load();
  assert.equal(s.loaded.value, true);
  assert.equal(s.form.value.discomfort, 'yes');
  assert.equal(s.revision.value, 1);
  assert.equal(s.dirty.value, false);
});

test('failed save keeps all answers and retries the same revision and payload', async () => {
  const requests = [];
  const s = state({ get: async () => response(null), put: async (url, body) => {
    requests.push({ url, body });
    if (requests.length === 1) throw new Error('response lost');
    return response(record());
  } });
  await s.load(); fill(s);
  await s.save();
  assert.equal(s.dirty.value, true);
  assert.equal(s.revision.value, 0);
  assert.equal(s.form.value.discomfort, 'yes');
  assert.match(s.saveError.value, /未确认保存/);
  await s.save();
  assert.deepEqual(requests[0], requests[1]);
  assert.equal(requests[0].url, '/sessions/1/feedback');
  assert.equal(requests[0].body.discomfort, true);
  assert.equal(s.dirty.value, false);
  assert.equal(s.revision.value, 1);
  assert.equal(s.saveError.value, '');
});

test('duplicate save clicks send once; late edits remain dirty after the response', async () => {
  const pending = defer(); let calls = 0;
  const s = state({ get: async () => response(null), put: () => { calls++; return pending.promise; } });
  await s.load(); fill(s);
  const saving = s.save();
  await s.save();
  assert.equal(calls, 1);
  s.form.value.note = '请求期间新填的内容';
  pending.resolve(response(record()));
  await saving;
  assert.equal(s.form.value.note, '请求期间新填的内容');
  assert.equal(s.dirty.value, true);
  assert.equal(s.revision.value, 1);
});

test('revision conflict keeps local answers and blocks retries until explicitly reloaded', async () => {
  let reads = 0, writes = 0;
  const s = state({ get: async () => response(record({ revision: ++reads })), put: async () => {
    writes++; throw { response: { status: 409, data: { detail: '其他页面已修改，请先重新加载' } } };
  } });
  await s.load(); s.form.value.note = '本地内容';
  await s.save(); await s.save();
  assert.equal(s.conflict.value, true);
  assert.equal(s.form.value.note, '本地内容');
  assert.equal(writes, 1); assert.equal(reads, 1);
  await s.load();
  assert.equal(s.conflict.value, false);
  assert.equal(s.revision.value, 2);
  assert.equal(s.dirty.value, false);
});

test('switching to demo clears personal results and only saves an experience note', async () => {
  let sent;
  const s = state({ get: async () => response(record()), put: async (url, body) => {
    sent = body;
    return response(record({ ...body, revision: 2 }));
  } });
  await s.load(); s.form.value.performed = 'demo'; s.participationChanged();
  assert.equal(s.form.value.completion, '');
  assert.equal(s.form.value.discomfort, '');
  await s.save();
  assert.equal(sent.performed, false);
  assert.equal(sent.completion, null);
  assert.equal(sent.effort, null);
  assert.equal(sent.discomfort, null);
  assert.equal(s.dirty.value, false);
});

test('switching reports ignores the previous report load response', async () => {
  const old = defer(); let id = 1;
  const s = state({ get: url => url.includes('/1/') ? old.promise : Promise.resolve(response(record({ note: '新训练' }))) }, () => id);
  const loading = s.load(); id = 2; await s.load();
  old.resolve(response(record({ note: '旧训练' }))); await loading;
  assert.equal(s.form.value.note, '新训练');
  assert.equal(s.loading.value, false);
});

test('leaving the report prevents late save responses from mutating detached state', async () => {
  const pending = defer();
  const s = state({ get: async () => response(null), put: () => pending.promise });
  await s.load(); fill(s);
  const saving = s.save(); s.dispose();
  pending.resolve(response(record())); await saving;
  assert.equal(s.revision.value, 0);
  assert.equal(s.savedAt.value, '');
});
