import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { computed, reactive, ref, watch, nextTick } from 'vue';
import { validScale, maxScore, scoreError } from '../src/utils/assessmentScores.js';

function page(name, exposed, overrides = {}) {
  const source = readFileSync(new URL(`../src/views/${name}.vue`, import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/import .*;\r?\n/g, '');
  const ctx = vm.createContext({ computed, reactive, ref, watch, nextTick, validScale, maxScore, scoreError, AbortController, onMounted() {}, onBeforeUnmount() {},
    getUser: () => ({ id: 1, age_group: 'middle_age' }), setUser() {},
    errorMessage: (_, fallback) => fallback, useRouter: () => ({ push() {}, replace() {} }),
    useRoute: () => ({ query: {} }), ...overrides });
  vm.runInContext(source + `\nglobalThis.check = { ${exposed} };`, ctx);
  return ctx.check;
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

test('home finds the latest completed report beyond the three most recent unfinished records', async () => {
  const c = page('Home', 'loadHomeData, latestFinishedSession, recentState, runningSession, finishedState', {
    api: { get: async (url, { params } = {}) => {
      if (url.includes('prescriptions')) return { data: { id: 1 } };
      if (url.includes('summary')) return { data: { finished_sessions: 1 } };
      return { data: { items: params.status === 'finished' ? [{ id: 10, status: 'finished' }]
        : params.status === 'running' ? [{ id: 20, status: 'running' }]
        : [{ id: 20 }, { id: 19 }, { id: 18 }] } };
    } },
  });
  await c.loadHomeData();
  assert.equal(c.latestFinishedSession.value.id, 10);
  assert.equal(c.runningSession.value.id, 20);
  assert.equal(c.recentState.data.length, 3);
});

test('home report failure remains an error rather than claiming there are no reports', async () => {
  const c = page('Home', 'loadHomeData, latestFinishedSession, finishedState', {
    api: { get: async (url, { params } = {}) => {
      if (params?.status === 'finished') throw new Error('offline');
      return { data: url.includes('summary') ? { finished_sessions: 3 } : url.includes('sessions') ? { items: [] } : {} };
    } },
  });
  await c.loadHomeData();
  assert.equal(c.finishedState.status, 'error');
  assert.equal(c.latestFinishedSession.value, null);
});

test('history clears old filter results and its list survives a statistics failure', async () => {
  let mode = 'ok';
  const c = page('History', 'load, sessions, summary, err, summaryErr, status', {
    api: { get: async url => {
      if (url.includes('summary')) {
        if (mode === 'summary-error') throw new Error('offline');
        return { data: { finished_sessions: 1 } };
      }
      if (mode === 'list-error') throw new Error('offline');
      return { data: { items: [{ id: 8 }], total: 1 } };
    } },
  });
  await c.load();
  assert.equal(c.sessions.value.length, 1);
  mode = 'list-error'; c.status.value = 'cancelled';
  await c.load();
  assert.equal(c.sessions.value.length, 0);
  assert.match(c.err.value, /读取失败/);
  mode = 'summary-error';
  await c.load();
  assert.equal(c.sessions.value[0].id, 8);
  assert.equal(c.summary.value, null);
  assert.match(c.summaryErr.value, /统计读取失败/);
});

test('a late history request cannot restore an old filter result', async () => {
  const old = deferred(); let count = 0;
  const c = page('History', 'load, sessions, status', {
    api: { get: async url => url.includes('summary') ? { data: {} }
      : (++count === 1 ? old.promise : { data: { items: [{ id: 2 }], total: 1 } }) },
  });
  const first = c.load(); c.status.value = 'finished'; await c.load();
  old.resolve({ data: { items: [{ id: 1 }], total: 1 } }); await first;
  assert.equal(c.sessions.value[0].id, 2);
});

test('report keeps a real zero score, rejects demo/invalid scores and zero remains a valid measured count', () => {
  const c = page('Report', 'data, validScore, hasMotionCount, analysisMessage', { watch() {} });
  c.data.value = { analysis: { status: 'model', score: 0 }, session: { pose_summary: { motion_analysis: { status: 'ok', rep_count: 0 } } } };
  assert.equal(c.validScore.value, 0); assert.equal(c.hasMotionCount.value, true);
  for (const analysis of [{ status: 'demo', score: 78 }, { status: 'model', score: '84.5' }, { status: 'model', score: NaN }, { status: 'model', score: 101 }]) {
    c.data.value = { analysis };
    assert.equal(c.validScore.value, null);
    assert.equal(c.hasMotionCount.value, false);
    assert.doesNotMatch(c.analysisMessage.value, /已完成/);
  }
});

test('report refresh preserves an unsaved feedback form when the user declines discarding it', async () => {
  let requests = 0;
  const c = page('Report', 'data, sessionId, feedbackPanel, reloadReport', {
    watch() {}, api: { get: async () => { requests++; return { data: {} }; } },
  });
  c.sessionId.value = 10; c.data.value = { session: { id: 10 } };
  c.feedbackPanel.value = { confirmLeave: () => false };
  await c.reloadReport();
  assert.equal(requests, 0); assert.equal(c.data.value.session.id, 10);
  c.feedbackPanel.value = { confirmLeave: () => true };
  await c.reloadReport(); assert.equal(requests, 1);
});

test('profile never fabricates missing measurements and preserves unfamiliar health tags', async () => {
  const c = page('Profile', 'form, save, tagsForSave', {
    getUser: () => ({ id: 1, chronic_tags: ['joint', 'doctor_note_custom'] }),
    document: { querySelector: () => ({ focus() {} }) }, api: { put() { assert.fail('Invalid profile saved'); } },
  });
  assert.equal(c.form.height_cm, ''); assert.equal(c.form.weight_kg, '');
  assert.deepEqual(Array.from(c.tagsForSave()), ['joint', 'doctor_note_custom']);
  await c.save();
});

test('fitness catalog retry and failed submission keep measured input; invalid field receives focus', async () => {
  let failLoad = true, failSave = true, focused = '';
  const posts = [];
  const c = page('Fitness', 'loadScales, scores, submit, loadErr, formErr, invalidKey, result', {
    document: { getElementById: id => ({ focus() { focused = id; } }) },
    api: {
      get: async () => { if (failLoad) throw new Error('offline'); return { data: [{ id: 'middle_elder', items: [{ key: 'bmi', name: '测试项目', weight: 100 }] }] }; },
      post: async (_, payload) => { posts.push(payload); if (failSave) throw new Error('offline'); return { data: { total_score: payload.scores.bmi } }; },
    },
  });
  await c.loadScales(); assert.match(c.loadErr.value, /加载失败/);
  failLoad = false; await c.loadScales(); await nextTick();
  await c.submit(); assert.equal(focused, 'fitness-bmi'); assert.equal(c.invalidKey.value, 'bmi');
  c.scores.bmi = 0; await c.submit();
  assert.equal(c.result.value, null); assert.equal(c.scores.bmi, 0);
  failSave = false; await c.submit(); assert.equal(c.result.value.total_score, 0);
  assert.equal(posts.length, 2);
});
