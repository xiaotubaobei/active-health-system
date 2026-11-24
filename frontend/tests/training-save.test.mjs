import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

// Run the actual page logic with browser/network boundaries replaced. No camera or health data is needed.
function page(put) {
  const source = readFileSync(new URL('../src/views/Exercise.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0]
    .replace(/import[\s\S]*?from\s*["'][^"']+["'];/g, '');
  let now = 1000;
  const context = vm.createContext({
    ref: value => ({ value }), computed: fn => ({ get value() { return fn(); } }),
    onMounted() {}, onBeforeUnmount() {}, onBeforeRouteLeave() {}, watch() {},
    getUser: () => ({ id: 1 }), useRoute: () => ({ query: {} }), useRouter: () => ({}),
    api: { put }, errorMessage: (e, fallback) => e.response?.data?.detail || fallback,
    isOfflineRtmpose: () => false, performance: { now: () => now },
    landmarksToMp33Frame: (landmarks, t_ms, frame_index) => ({ landmarks, t_ms, frame_index }),
    buildPoseSummary: ({ mpFrames }) => ({ source: 'camera', sequences: { mediapipe33: { frames: mpFrames } } }),
    Date, JSON, console,
  });
  vm.runInContext(source + `\n globalThis.check = { captureFrame, persistDraft,
    session, busy, inputMode, cameraFrames, draftDirty, draftConflict, saveError, saving };`, context);
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
});
