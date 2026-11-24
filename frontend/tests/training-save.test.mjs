import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { createCaptureClock } from '../src/utils/captureClock.js';
import test from 'node:test';
import assert from 'node:assert/strict';

// Run the actual page logic with browser/network boundaries replaced. No camera or health data is needed.
function page(put, post, get, cameraReady = () => true) {
  const source = readFileSync(new URL('../src/views/Exercise.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0]
    .replace(/import[\s\S]*?from\s*["'][^"']+["'];/g, '');
  let now = 1000;
  const context = vm.createContext({
    ref: value => ({ value }), computed: fn => ({ get value() { return fn(); } }),
    onMounted() {}, onBeforeUnmount() {}, onBeforeRouteLeave() {}, watch() {},
    getUser: () => ({ id: 1 }), useRoute: () => ({ query: {} }), useRouter: () => ({ replace: async () => {}, push: async () => {} }),
    api: { put, post, get }, createCaptureClock: () => createCaptureClock(() => now),
    crypto: { randomUUID: () => "test-request-1234567890" },
    localStorage: { setItem() {}, removeItem() {} },
    createPoseCamera: options => ({ start: async () => { options.onReady(cameraReady()); return true; }, stop() {} }), errorMessage: (e, fallback) => e.response?.data?.detail || fallback,
    isOfflineRtmpose: () => false, performance: { now: () => now },
    landmarksToMp33Frame: (landmarks, t_ms, frame_index) => ({ landmarks, t_ms, frame_index }),
    buildPoseSummary: ({ mpFrames }) => ({ source: 'camera', sequences: { mediapipe33: { frames: mpFrames } } }),
    Date, JSON, console,
  });
  vm.runInContext(source + `\n globalThis.check = { captureFrame, persistDraft,
    session, busy, inputMode, cameraFrames, draftDirty, draftConflict, saveError, saving,
    start, pendingStartBody, camOn, poseReady, paused, pauseCapture, syncClock, activeMs, savedPayload, buildSubmission,
    loadRecommendedDemo, demoVideos, demoPickId, exerciseId, recommendedDemo, err, resumeCapture };`, context);
  const c = context.check;
  c.session.value = { id: 1, draft_revision: 0 };
  c.busy.value = false; c.inputMode.value = 'camera';
  return { c, tick: delta => { now += delta; } };
}

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
    return { data: { session: { id: 12, status: 'running', pose_summary: body.pose_summary } } };
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
