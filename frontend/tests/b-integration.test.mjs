import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { computed, reactive, ref, watch, nextTick } from 'vue';
import { validScale, maxScore, scoreError } from '../src/utils/assessmentScores.js';

function page(name, exposed, overrides = {}) {
  const source = readFileSync(new URL(`../src/views/${name}.vue`, import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/import .*;\r?\n/g, '');
  const context = vm.createContext({ computed, reactive, ref, watch, nextTick,
    validScale, maxScore, scoreError, AbortController,
    onMounted() {}, onBeforeUnmount() {},
    getUser: () => ({ id: 1, age_group: 'middle_age' }), setUser() {},
    errorMessage: (_, fallback) => fallback,
    useRoute: () => ({ query: {} }), useRouter: () => ({ replace() {} }),
    document: { getElementById: () => ({ focus() {} }) }, ...overrides });
  vm.runInContext(source + `\nglobalThis.check = { ${exposed} };`, context);
  return context.check;
}
const scale = (key = 'bmi', limit = 100) => ({ id: 'middle_elder', items: [{ key, name: '测试项目', weight: 100, max_score: limit }] });
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

test('assessment catalogs reject empty, duplicate and malformed scoring rules; measured zero is valid', () => {
  for (const value of [null, {}, { id: 'middle_elder', items: [] },
    { ...scale(), items: [scale().items[0], scale().items[0]] }, scale('bmi', -1), scale('bmi', '100')]) {
    assert.equal(validScale(value), false);
  }
  assert.equal(validScale(scale('bmi', 80)), true);
  assert.equal(scoreError(scale().items[0], 0), '');
  for (const value of [null, '', '  ', NaN, Infinity, -1, 101, false, []]) {
    assert.notEqual(scoreError(scale().items[0], value), '');
  }
  assert.notEqual(scoreError(scale('bmi', 80).items[0], 81), '');
});

test('fitness refresh preserves the same scale draft, but changed rules require re-entry', async () => {
  let catalog = [scale()], fail = false;
  const c = page('Fitness', 'loadScales, scores, result, scaleSwitchNotice, loadErr', {
    api: { get: async () => { if (fail) throw Error('offline'); return { data: catalog }; } },
  });
  await c.loadScales(); await nextTick(); c.scores.bmi = 63.5;
  await c.loadScales(); await nextTick(); assert.equal(c.scores.bmi, 63.5);
  fail = true; await c.loadScales(); assert.equal(c.scores.bmi, 63.5);
  assert.match(c.loadErr.value, /加载失败/);
  fail = false; catalog = [scale('bmi', 80)]; await c.loadScales(); await nextTick();
  assert.equal(c.scores.bmi, undefined); assert.match(c.scaleSwitchNotice.value, /规则有更新/);
});

test('fitness never offers another age group as a fallback or submits an empty catalog', async () => {
  let posted = 0;
  const c = page('Fitness', 'loadScales, current, submit, loadErr', {
    api: { get: async () => ({ data: [{ ...scale(), id: 'youth' }] }), post() { posted++; } },
  });
  await c.loadScales(); await nextTick(); await c.submit();
  assert.equal(c.current.value, undefined); assert.match(c.loadErr.value, /加载失败/); assert.equal(posted, 0);
});

test('an unavailable optional catalog does not block saving a genuine basic profile', async () => {
  let body;
  const c = page('Onboarding', 'load, form, consent, submit, done, catalogErr, scores', {
    api: {
      get: async url => { if (url.includes('scales')) throw Error('offline'); return { data: { onboarding_done: false } }; },
      post: async (_, payload) => { body = payload; return { data: { user: { id: 1 }, baseline: null } }; },
    },
  });
  await c.load(); assert.match(c.catalogErr.value, /加载失败/);
  Object.assign(c.form, { age_group: 'middle_age', height_cm: 163, weight_kg: 54, goal: 'fitness' });
  await nextTick(); c.consent.value = true; await c.submit();
  assert.equal(c.done.value, true); assert.equal(body.scores, undefined); assert.equal(body.generate_prescription, false);
});

test('history validates malformed pages and distinguishes filtered emptiness from never having trained', async () => {
  let malformed = false, countFails = false;
  const c = page('History', 'load, sessions, status, allSessionTotal, total, err, countErr', {
    api: { get: async (url, options) => {
      if (url.includes('summary')) return { data: {} };
      if (options.params.page_size === 1) {
        if (countFails) throw Error('offline');
        return { data: { items: [{ id: 4 }], total: 4 } };
      }
      return { data: { items: malformed ? [null] : [], total: 0 } };
    } },
  });
  c.status.value = 'cancelled'; await c.load();
  assert.equal(c.total.value, 0); assert.equal(c.allSessionTotal.value, 4); assert.equal(c.err.value, '');
  countFails = true; await c.load(); assert.equal(c.allSessionTotal.value, null); assert.match(c.countErr.value, /数量读取失败/);
  malformed = true; await c.load(); assert.match(c.err.value, /读取失败/); assert.equal(c.sessions.value.length, 0);
});

test('report rejects malformed IDs and never requests a guessed report', async () => {
  let requests = 0;
  const c = page('Report', 'sessionId, loadReport, viewState', {
    watch() {}, api: { get() { requests++; } },
  });
  for (const id of ['', '0', '-1', '1.5', '01', '1e2', ['1', '2'], '9007199254740992']) {
    c.sessionId.value = id; await c.loadReport(); assert.equal(c.viewState.value, 'invalid');
  }
  assert.equal(requests, 0);
});

test('report read states distinguish missing, forbidden and failed; stale responses never replace a new report', async () => {
  const late = deferred(); let mode = 404;
  const c = page('Report', 'sessionId, loadReport, data, viewState', {
    watch() {}, api: { get: async url => {
      if (mode === 'late' && url === '/reports/1') return late.promise;
      if (mode === 'late') return { data: { session: { id: 2 }, report: {} } };
      throw { response: { status: mode } };
    } },
  });
  c.sessionId.value = '1';
  for (const [status, expected] of [[404, 'not_found'], [403, 'forbidden'], [500, 'failed']]) {
    mode = status; await c.loadReport(); assert.equal(c.viewState.value, expected); assert.equal(c.data.value, null);
  }
  mode = 'late'; const first = c.loadReport(); c.sessionId.value = '2'; await c.loadReport();
  late.resolve({ data: { session: { id: 1 }, report: {} } }); await first;
  assert.equal(c.data.value.session.id, 2); assert.equal(c.viewState.value, 'ready');
});

test('report list failure remains a read failure and never claims the user has no reports', async () => {
  const c = page('Report', 'loadReportList, viewState, stateMessage', {
    watch() {}, api: { get: async () => { throw Error('offline'); } },
  });
  await c.loadReportList(); assert.equal(c.viewState.value, 'list_failed'); assert.match(c.stateMessage.value, /读取/);
});

test('report presents only valid advice and time intervals, while keeping a measured zero count', () => {
  const c = page('Report', 'data, modelErrors, modelAdvice, repCount, repIntervals, poseMessage', { watch() {} });
  c.data.value = { analysis: { status: 'model', score: 80 }, report: { cot: { errors: ['膝盖内扣', null, 42], advice: { unsafe: true } } },
    session: { pose_summary: { sequences: { mediapipe33: { frames: [{}, {}] } }, motion_analysis: { status: 'ok', rep_count: 3,
      rep_intervals: [{ start_sec: 0, end_sec: 1 }, { start_sec: 3, end_sec: 2 }, { start_sec: -1, end_sec: 3 }] } } } };
  assert.deepEqual(Array.from(c.modelErrors.value), ['膝盖内扣']); assert.equal(c.modelAdvice.value, '');
  assert.equal(c.repIntervals.value.length, 1); assert.match(c.poseMessage.value, /2 帧/);
  c.data.value.session.pose_summary.motion_analysis.rep_count = 0;
  assert.equal(c.repCount.value, 0); assert.equal(c.repIntervals.value.length, 0);
  c.data.value.analysis.status = 'demo'; assert.equal(c.modelErrors.value.length, 0);
});
