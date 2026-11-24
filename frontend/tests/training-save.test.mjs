import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { createCaptureClock } from '../src/utils/captureClock.js';
import { createStartRecovery } from '../src/utils/startRecovery.js';
import { validateVideoFile, checkAborted } from '../src/utils/videoInput.js';
import { createScreenAwake } from '../src/utils/screenAwake.js';
import { cameraErrorMessage } from '../src/utils/cameraAccess.js';
import { ref as vueRef, computed as vueComputed, watch as vueWatch } from 'vue';
import test from 'node:test';
import assert from 'node:assert/strict';

// Run the actual page logic with browser/network boundaries replaced. No camera or health data is needed.
function page(put, post, get, cameraReady = () => true, processVideoFile, options = {}) {
  const source = readFileSync(new URL('../src/views/Exercise.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0]
    .replace(/import[\s\S]*?from\s*["'][^"']+["'];/g, '');
  let now = 1000;
  const entries = options.entries || new Map();
  const navigation = [];
  const document = { hidden: false };
  let cameraOptions;
  const context = vm.createContext({
    ref: options.reactive ? vueRef : value => ({ value }), computed: options.reactive ? vueComputed : fn => ({ get value() { return fn(); } }),
    onMounted() {}, onBeforeUnmount() {}, onBeforeRouteLeave() {}, watch: options.reactive ? vueWatch : () => {},
    getUser: () => ({ id: 1 }), useRoute: () => ({ query: options.query || {} }), useRouter: () => ({ replace: async target => navigation.push(target), push: async target => navigation.push(target) }),
    api: { put, post, get }, createCaptureClock: () => createCaptureClock(() => now),
    crypto: { randomUUID: () => "test-request-1234567890" },
    localStorage: { setItem() {}, removeItem() {} },
    createStartRecovery, sessionStorage: { getItem: key => entries.get(key) || null, setItem: (key, value) => entries.set(key, value), removeItem: key => entries.delete(key) },
    createPoseCamera: config => { cameraOptions = config; return { start: async () => { config.onReady(cameraReady()); return true; }, stop() {} }; }, errorMessage: (e, fallback) => e.response?.data?.detail || fallback,
    cameraSupportError: () => '', cameraErrorMessage,
    createScreenAwake: config => createScreenAwake({ ...config, navigator: options.navigator || {}, document }), document,
    isOfflineRtmpose: () => false, performance: { now: () => now },
    landmarksToMp33Frame: (landmarks, t_ms, frame_index) => ({ landmarks, t_ms, frame_index }),
    buildPoseSummary: ({ mpFrames }) => ({ source: 'camera', sequences: { mediapipe33: { frames: mpFrames } } }),
    Date, JSON, console, AbortController, validateVideoFile, checkAborted, processVideoFile,
  });
  vm.runInContext(source + `\n globalThis.check = { captureFrame, persistDraft,
    session, busy, inputMode, cameraFrames, draftDirty, draftConflict, saveError, saving,
    start, pendingStartBody, camOn, poseReady, paused, pauseCapture, syncClock, activeMs, savedPayload, buildSubmission,
    loadRecommendedDemo, demoVideos, demoPickId, exerciseId, recommendedDemo, err, resumeCapture,
    runVideoProcess, cancelVideoProcessing, videoFile, videoProcessing, hint, mpFrames, previewOn,
    initialize, initialized, startIntent, canStart, prescriptionId, onVisibility, cameraStarting, awakeStatus };`, context);
  const c = context.check;
  c.session.value = { id: 1, draft_revision: 0 };
  c.busy.value = false; c.inputMode.value = 'camera';
  c.initialized.value = true;
  return { c, entries, navigation, document, interrupted: () => cameraOptions.onInterrupted(), tick: delta => { now += delta; } };
}

test('real Vue capture state acquires a screen lock only during active capture and releases on pause/end', async () => {
  const locks = [];
  const p = page(async () => ({ data: { session: { draft_revision: 1 } } }), undefined, undefined, undefined, undefined,
    { reactive: true, navigator: { wakeLock: { request: async () => {
      const held = new EventTarget(); held.released = false;
      held.release = async () => { held.released = true; held.dispatchEvent(new Event('release')); };
      locks.push(held); return held;
    } } } });
  assert.equal(locks.length, 0);
  await p.c.resumeCapture();
  await Promise.resolve();
  assert.equal(p.c.awakeStatus.value, 'active');
  assert.equal(locks.length, 1);
  p.c.pauseCapture();
  assert.equal(locks[0].released, true);
  assert.equal(p.c.awakeStatus.value, 'idle');
  await p.c.persistDraft();
  await p.c.resumeCapture();
  await Promise.resolve();
  assert.equal(locks.length, 2);
  p.c.session.value = null;
  assert.equal(locks[1].released, true);
});

test('camera interruption pauses collection, retains frames, and saves to the original session', async () => {
  let sent, target;
  const p = page(async (url, body) => { target = url; sent = body; return { data: { session: { draft_revision: 1 } } }; });
  await p.c.resumeCapture();
  p.tick(1500); p.c.captureFrame([{ x: 0.1 }]);
  p.interrupted();
  await p.c.persistDraft();
  assert.equal(p.c.camOn.value, false);
  assert.equal(p.c.paused.value, true);
  assert.equal(p.c.cameraFrames.value.length, 1);
  assert.equal(target, '/sessions/1/draft');
  assert.equal(sent.pose_summary.capture_session.active_ms, 1500);
  assert.match(p.c.hint.value, /中断.*继续训练/);
  p.tick(5000); p.c.captureFrame([{ x: 0.2 }]);
  assert.equal(p.c.cameraFrames.value.length, 1);
});

test('backgrounding closes camera preview before a session exists', async () => {
  const p = page();
  p.c.session.value = null;
  await p.c.resumeCapture();
  assert.equal(p.c.camOn.value, true);
  p.document.hidden = true;
  p.c.onVisibility();
  assert.equal(p.c.camOn.value, false);
  assert.equal(p.c.cameraStarting.value, false);
  assert.match(p.c.hint.value, /已关闭/);
});

test('cancelling page video parsing releases busy state and allows a new attempt', async () => {
  let attempts = 0;
  const { c } = page(undefined, undefined, undefined, undefined, ({ signal }) => {
    attempts++;
    if (attempts === 2) throw new Error('视频中未检测到人体');
    return new Promise((resolve, reject) => signal.addEventListener('abort', () => {
      try { checkAborted(signal); } catch (error) { reject(error); }
    }, { once: true }));
  });
  c.session.value = null; c.inputMode.value = 'video';
  c.videoFile.value = { size: 100, type: 'video/mp4', name: 'test.mp4' };
  const pending = c.runVideoProcess();
  assert.equal(c.busy.value, true);
  assert.equal(c.videoProcessing.value, true);
  c.cancelVideoProcessing();
  await pending;
  assert.equal(c.busy.value, false);
  assert.equal(c.videoProcessing.value, false);
  assert.equal(c.previewOn.value, false);
  assert.equal(c.mpFrames.value.length, 0);
  assert.match(c.hint.value, /已取消/);
  assert.equal(c.err.value, '');
  await c.runVideoProcess();
  assert.equal(attempts, 2);
  assert.match(c.err.value, /未检测到人体/);
  assert.equal(c.busy.value, false);
});

test('camera sampling, immutable upload, and frames arriving during save', async () => {
  let resolve, sent;
  const { c, tick } = page((url, body) => { sent = body; return new Promise(r => { resolve = r; }); });
  c.captureFrame([{ x: 0.1 }]);
  c.captureFrame([{ x: 0.2 }]);
  assert.equal(c.cameraFrames.value.length, 1);
  const pending = c.persistDraft();
  tick(500); c.captureFrame([{ x: 0.3 }]);
  assert.equal(sent.pose_summary.sequences.mediapipe33.frames.length, 1);
  resolve({ data: { session: { draft_revision: 1 } } });
  await pending;
  assert.equal(c.session.value.draft_revision, 1);
  assert.equal(c.draftDirty.value, true);
});

test('failed save keeps frames and can retry; conflict stops automatic overwrite', async () => {
  let fail = true, conflict = false;
  const { c } = page(async () => {
    if (conflict) throw { response: { status: 409, data: { detail: 'conflict' } } };
    if (fail) throw new Error('offline');
    return { data: { session: { draft_revision: 1 } } };
  });
  c.captureFrame([{ x: 0.1 }]);
  await assert.rejects(c.persistDraft());
  assert.equal(c.draftDirty.value, true);
  assert.equal(c.cameraFrames.value.length, 1);
  fail = false; await c.persistDraft();
  assert.equal(c.draftDirty.value, false);
  conflict = true; await assert.rejects(c.persistDraft());
  assert.equal(c.draftConflict.value, true);
  await assert.rejects(c.persistDraft());
});

test('capture stops at the declared bound and ignores inactive training', () => {
  const { c, tick } = page(async () => ({}));
  c.session.value = null;
  c.captureFrame([{ x: 0.1 }]);
  assert.equal(c.cameraFrames.value.length, 0);
  c.session.value = { id: 1 };
  for (let i = 0; i < 1210; i++) { tick(500); c.captureFrame([{ x: 0.1 }]); }
  assert.equal(c.cameraFrames.value.length, 1200);
  assert.equal(c.paused.value, true);
  assert.equal(c.camOn.value, false);
});

test('recommended sample follows the selected exercise and respects active training', async () => {
  const requests = [];
  const { c } = page(async () => ({}), undefined, async (url, options) => {
    requests.push(options.params.rel);
    throw new Error('sample unavailable');
  });
  c.demoVideos.value = [
    { id: 'squat', exercise_id: 'squat', rel_path: 'squat/repcount_stu4_66.mp4' },
    { id: 'jump', exercise_id: 'jump_jack', rel_path: 'jump_jack/repcount_stu6_18.mp4' },
  ];
  c.exerciseId.value = 'jump_jack';
  await c.loadRecommendedDemo();
  assert.equal(requests.length, 0);
  c.session.value = null;
  await c.loadRecommendedDemo();
  assert.equal(c.demoPickId.value, 'jump');
  assert.deepEqual(requests, ['jump_jack/repcount_stu6_18.mp4']);
  assert.equal(c.err.value, 'sample unavailable');
  c.exerciseId.value = 'push_up';
  assert.equal(c.recommendedDemo.value, null);
});


test('pausing excludes idle time, ignores frames, and saves the measured capture time', async () => {
  let sent;
  const { c, tick } = page(async (url, body) => {
    sent = body;
    return { data: { session: { draft_revision: 1 } } };
  });
  c.camOn.value = true; c.poseReady.value = true; c.syncClock();
  tick(1000); c.captureFrame([{ x: 0.1 }]);
  c.pauseCapture();
  await c.persistDraft();
  assert.equal(c.activeMs.value, 1000);
  assert.equal(c.paused.value, true);
  assert.equal(c.camOn.value, false);
  tick(10000); c.captureFrame([{ x: 0.2 }]); c.syncClock();
  assert.equal(c.cameraFrames.value.length, 1);
  assert.equal(c.activeMs.value, 1000);
  assert.equal(sent.pose_summary.capture_session.active_ms, 1000);
  c.paused.value = false; c.camOn.value = true; c.poseReady.value = true; c.syncClock();
  tick(2000); c.syncClock();
  assert.equal(c.activeMs.value, 3000);
});

test('lost start response retries exactly the same key and input', async () => {
  const requests = [];
  const { c } = page(async () => ({}), async (url, body) => {
    requests.push(JSON.parse(JSON.stringify(body)));
    if (requests.length === 1) throw new Error('lost response');
    return { data: { session: { ...body, id: 12, status: 'running' } } };
  });
  c.session.value = null; c.camOn.value = true; c.poseReady.value = true;
  await c.start();
  assert.ok(c.pendingStartBody.value);
  // Network retry must still work if the user has since turned off the camera.
  c.camOn.value = false; c.poseReady.value = false;
  await c.start();
  assert.deepEqual(requests[0], requests[1]);
  assert.equal(requests[0].start_key, 'test-request-1234567890');
  assert.equal(c.session.value.id, 12);
  assert.equal(c.pendingStartBody.value, null);
});

test('a restored session can retry a failed model load without refreshing', async () => {
  let ready = false;
  const { c } = page(async () => ({}), undefined, undefined, () => ready);
  c.paused.value = true;
  await c.resumeCapture();
  assert.equal(c.camOn.value, false);
  assert.equal(c.paused.value, true);
  assert.match(c.err.value, /重试/);
  ready = true;
  await c.resumeCapture();
  assert.equal(c.camOn.value, true);
  assert.equal(c.poseReady.value, true);
  assert.equal(c.paused.value, false);
  assert.equal(c.err.value, '');
});

test('reload finds a committed start without posting again or relying on current plan', async () => {
  let posts = 0, committed;
  const first = page(undefined, async (url, body) => {
    posts++; committed = { ...body, id: 21, status: 'running', draft_revision: 2 };
    throw new Error('response lost');
  });
  first.c.session.value = null; first.c.camOn.value = true; first.c.poseReady.value = true;
  await first.c.start();
  const stored = JSON.parse(first.entries.get('ah_pending_start:1'));
  assert.deepEqual(Object.keys(stored).sort(), ['exercise_id', 'input_mode', 'prescription_id', 'start_key']);
  const second = page(undefined, () => { posts++; }, async url => {
    assert.match(url, /^\/sessions\/start-requests\//);
    return { data: { session: committed } };
  }, undefined, undefined, { entries: first.entries });
  second.c.session.value = null;
  await second.c.initialize();
  assert.equal(posts, 1);
  assert.equal(second.c.session.value.id, 21);
  assert.equal(second.c.session.value.draft_revision, 2);
  assert.equal(second.c.paused.value, true);
  assert.equal(first.entries.size, 0);
  assert.equal(second.navigation[0].query.session_id, 21);
});

function pendingEntries() {
  return new Map([['ah_pending_start:1', JSON.stringify({ start_key: 'retry-after-reload-123',
    exercise_id: 'squat', prescription_id: 0, input_mode: 'camera' })]]);
}

test('a missing start remains pending and retries the same key after preparing input', async () => {
  let sent;
  const { c, entries } = page(undefined, async (url, body) => {
    sent = body; return { data: { session: { ...body, id: 22, status: 'running' } } };
  }, async url => {
    if (url.includes('start-requests') || url.includes('/current')) throw { response: { status: 404 } };
    return { data: url.includes('templates') ? { fitness: { exercises: [{ id: 'squat', name: '深蹲' }] } } : { videos: [] } };
  }, undefined, undefined, { entries: pendingEntries() });
  c.session.value = null;
  await c.initialize();
  assert.equal(sent, undefined);
  assert.equal(entries.size, 1);
  c.camOn.value = true; c.poseReady.value = true;
  await c.start();
  assert.equal(sent.start_key, 'retry-after-reload-123');
  assert.equal(entries.size, 0);
});

test('lookup failure blocks new starts until recovery succeeds', async () => {
  let online = false, posts = 0;
  const { c, entries } = page(undefined, () => { posts++; }, async () => {
    if (!online) throw new Error('offline');
    return { data: { session: { id: 23, status: 'cancelled', start_key: 'retry-after-reload-123' } } };
  }, undefined, undefined, { entries: pendingEntries() });
  c.session.value = null;
  await c.initialize();
  assert.equal(c.initialized.value, false);
  assert.equal(c.canStart.value, false);
  await c.start();
  assert.equal(posts, 0);
  assert.equal(entries.size, 1);
  online = true; await c.initialize();
  assert.equal(c.initialized.value, true);
  assert.equal(entries.size, 0);
});

test('plan server failures block starting instead of falling back to a free session', async () => {
  let posts = 0;
  const { c } = page(undefined, () => { posts++; }, async url => {
    if (url.includes('/current')) throw { response: { status: 500, data: { detail: '计划读取失败' } } };
    return { data: { fitness: { exercises: [{ id: 'squat' }] } } };
  });
  c.session.value = null; c.camOn.value = true; c.poseReady.value = true;
  await c.initialize(); await c.start();
  assert.equal(c.initialized.value, false);
  assert.equal(posts, 0);
  assert.match(c.err.value, /计划读取失败/);
});

test('explicit saved session restoration does not depend on the current prescription', async () => {
  const { c } = page(undefined, undefined, async url => {
    assert.equal(url, '/sessions/24');
    return { data: { session: { id: 24, exercise_id: 'squat', prescription_id: 4,
      status: 'running', pose_summary: { source: 'camera' } } } };
  }, undefined, undefined, { query: { session_id: 24, prescription_id: 1 } });
  c.session.value = null;
  await c.initialize();
  assert.equal(c.session.value.id, 24);
  assert.equal(c.prescriptionId.value, 4);
  assert.equal(c.initialized.value, true);
});

test('a rejected retry does not forget an earlier uncertain request', async () => {
  let attempts = 0;
  const { c, entries } = page(undefined, async () => {
    attempts++;
    if (attempts === 1) throw new Error('offline');
    throw { response: { status: 400, data: { detail: '输入无效' } } };
  });
  c.session.value = null; c.camOn.value = true; c.poseReady.value = true;
  await c.start(); await c.start();
  assert.equal(attempts, 2);
  assert.equal(entries.size, 1);
  assert.ok(c.pendingStartBody.value);
});

test('an invalid first attempt releases the recovery lock for correction', async () => {
  const { c, entries } = page(undefined, async () => {
    throw { response: { status: 422, data: { detail: '输入无效' } } };
  });
  c.session.value = null; c.camOn.value = true; c.poseReady.value = true;
  await c.start();
  assert.equal(entries.size, 0);
  assert.equal(c.startIntent.value, null);
  assert.equal(c.pendingStartBody.value, null);
});

test('recovery of an already finished start opens its original report', async () => {
  const { c, entries, navigation } = page(undefined, undefined, async () => ({
    data: { session: { id: 25, status: 'finished', start_key: 'retry-after-reload-123' } },
  }), undefined, undefined, { entries: pendingEntries() });
  c.session.value = null;
  await c.initialize();
  assert.equal(c.session.value, null);
  assert.equal(entries.size, 0);
  assert.equal(navigation[0].path, '/report');
  assert.equal(navigation[0].query.session_id, 25);
});
