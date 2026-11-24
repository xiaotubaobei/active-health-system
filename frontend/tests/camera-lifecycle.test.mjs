import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
}

function camera({ permission, model = async () => null, play = async () => {}, stopOnFrame = false } = {}) {
  let stops = 0, scheduled = 0, frames = 0;
  const draws = [], hints = [];
  const stream = { getTracks: () => [{ stop: () => { stops++; } }] };
  const video = { play, currentTime: 1 };
  const ctx = new Proxy({}, { get: () => () => {} });
  const context = vm.createContext({
    navigator: { mediaDevices: { getUserMedia: permission || (async () => stream) } },
    getPoseLandmarker: model, drawSkeleton: (...args) => draws.push(args),
    requestAnimationFrame: () => ++scheduled, cancelAnimationFrame() {},
    performance: { now: () => 1000 },
  });
  const source = readFileSync(new URL('../src/composables/usePoseCamera.js', import.meta.url), 'utf8')
    .replace(/import[^;]+;/, '').replace('export function', 'function');
  vm.runInContext(source + '\nglobalThis.factory = createPoseCamera;', context);
  const ctl = context.factory({ video, canvas: { getContext: () => ctx },
    onHint: text => hints.push(text), onFrame: () => { frames++; if (stopOnFrame) ctl.stop(); } });
  return { ctl, stream, video, draws, hints,
    get stops() { return stops; }, get scheduled() { return scheduled; }, get frames() { return frames; } };
}

test('leaving during permission request releases the eventual stream without starting preview', async () => {
  const permission = deferred();
  const c = camera({ permission: () => permission.promise });
  const opening = c.ctl.start();
  c.ctl.stop();
  permission.resolve(c.stream);
  assert.equal(await opening, false);
  assert.equal(c.stops, 1);
  assert.equal(c.video.srcObject, null);
  assert.equal(c.scheduled, 0);
});

test('leaving during model loading never restarts capture', async () => {
  const loading = deferred(), reached = deferred();
  const c = camera({ model: () => { reached.resolve(); return loading.promise; } });
  const opening = c.ctl.start();
  await reached.promise;
  c.ctl.stop();
  loading.resolve({ detectForVideo: () => { throw new Error('must not run'); } });
  assert.equal(await opening, false);
  assert.equal(c.stops, 1);
  assert.equal(c.scheduled, 0);
});

test('play failure releases tracks and allows another start', async () => {
  let fail = true;
  const c = camera({ play: async () => { if (fail) throw new Error('play failed'); } });
  await assert.rejects(c.ctl.start(), /play failed/);
  assert.equal(c.stops, 1);
  fail = false;
  assert.equal(await c.ctl.start(), true);
  c.ctl.stop();
  assert.equal(c.stops, 2);
});

test('skeleton uses the same single mirror transform as the video', async () => {
  const landmarks = Array.from({ length: 33 }, (_, i) => ({ x: i / 33, y: i / 40 }));
  const c = camera({ model: async () => ({ detectForVideo: () => ({ landmarks: [landmarks] }) }) });
  assert.equal(await c.ctl.start(), true);
  assert.equal(c.frames, 1);
  assert.equal(c.draws.length, 1);
  assert.equal(c.draws[0][4], undefined);
  c.ctl.stop();
});

test('failed shared model download can be retried after network recovery', async () => {
  let attempts = 0;
  const model = {};
  const context = vm.createContext({
    visionModule: {
      FilesetResolver: { forVisionTasks: async () => ({}) },
      PoseLandmarker: { createFromOptions: async () => {
        if (++attempts <= 2) throw new Error('network unavailable');
        return model;
      } },
    },
    POSE_MODEL_URL: 'https://example.com/test.task', POSE_LANDMARKER_VARIANT: 'full',
  });
  const source = readFileSync(new URL('../src/composables/usePoseLandmarker.js', import.meta.url), 'utf8')
    .replace(/import[^;]+;/, '')
    .replace('await import("@mediapipe/tasks-vision")', 'visionModule')
    .replace(/export \{[^;]+;/g, '').replaceAll('export ', '');
  vm.runInContext(source + '\nglobalThis.load = getPoseLandmarker;', context);
  await assert.rejects(context.load(), /network unavailable/);
  assert.equal(await context.load(), model);
  assert.equal(await context.load(), model);
  assert.equal(attempts, 3);
});

test('reaching the capture bound inside a frame callback stops drawing and scheduling', async () => {
  const landmarks = Array.from({ length: 33 }, () => ({ x: 0.1, y: 0.2 }));
  const c = camera({ stopOnFrame: true,
    model: async () => ({ detectForVideo: () => ({ landmarks: [landmarks] }) }) });
  await c.ctl.start();
  assert.equal(c.frames, 1);
  assert.equal(c.stops, 1);
  assert.equal(c.draws.length, 0);
  assert.equal(c.scheduled, 0);
});
