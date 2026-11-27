import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
import { cameraSupportError } from '../src/utils/cameraAccess.js';

function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
}

function camera({ permission, model = async () => null, play = async () => {}, stopOnFrame = false, facingMode = 'user', actualFacing } = {}) {
  let stops = 0, scheduled = 0, frames = 0;
  let interruptions = 0;
  const draws = [], hints = [], transforms = [], constraints = [];
  const track = new EventTarget();
  track.stop = () => { stops++; };
  track.getSettings = () => ({ facingMode: actualFacing });
  const stream = { getTracks: () => [track], getVideoTracks: () => [track] };
  const video = { play, currentTime: 1 };
  const ctx = new Proxy({}, { get: (_, key) => (...args) => transforms.push([key, ...args]) });
  const context = vm.createContext({
    navigator: { mediaDevices: { getUserMedia: async opts => { constraints.push(opts); return permission ? permission(opts) : stream; } } },
    cameraSupportError: () => cameraSupportError({ navigator: { mediaDevices: { getUserMedia() {} } } }),
    getPoseLandmarker: model, drawSkeleton: (...args) => draws.push(args),
    requestAnimationFrame: () => ++scheduled, cancelAnimationFrame() {},
    performance: { now: () => 1000 },
  });
  const source = readFileSync(new URL('../src/composables/usePoseCamera.js', import.meta.url), 'utf8')
    .replace(/import[^;]+;/g, '').replace('export function', 'function');
  vm.runInContext(source + '\nglobalThis.factory = createPoseCamera;', context);
  const ctl = context.factory({ video, canvas: { getContext: () => ctx }, facingMode,
    onInterrupted: () => { interruptions++; },
    onHint: text => hints.push(text), onFrame: () => { frames++; if (stopOnFrame) ctl.stop(); } });
  return { ctl, stream, track, video, draws, hints, transforms, constraints,
    get interruptions() { return interruptions; },
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

test('system camera interruption releases preview once and removes stale track listeners', async () => {
  const c = camera();
  await c.ctl.start();
  c.track.dispatchEvent(new Event('ended'));
  assert.equal(c.interruptions, 1);
  assert.equal(c.stops, 1);
  assert.equal(c.video.srcObject, null);
  c.track.dispatchEvent(new Event('ended'));
  assert.equal(c.interruptions, 1);
  await c.ctl.start();
  c.ctl.stop();
  c.track.dispatchEvent(new Event('ended'));
  assert.equal(c.interruptions, 1);
});

test('camera interruption during model loading cannot revive the old capture', async () => {
  const loading = deferred(), reached = deferred();
  const c = camera({ model: () => { reached.resolve(); return loading.promise; } });
  const opening = c.ctl.start();
  await reached.promise;
  c.track.dispatchEvent(new Event('ended'));
  loading.resolve({ detectForVideo: () => { throw new Error('must not run'); } });
  assert.equal(await opening, false);
  assert.equal(c.interruptions, 1);
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
  assert.equal(c.transforms.filter(t => t[0] === 'scale').length, 1);
  assert.deepEqual(c.transforms.find(t => t[0] === 'scale'), ['scale', -1, 1]);
  c.ctl.stop();
});

test('rear camera requests environment and keeps video and skeleton unmirrored', async () => {
  const landmarks = Array.from({ length: 33 }, () => ({ x: 0.1, y: 0.2 }));
  const c = camera({ facingMode: 'environment', model: async () => ({ detectForVideo: () => ({ landmarks: [landmarks] }) }) });
  await c.ctl.start();
  assert.equal(c.constraints[0].video.facingMode.ideal, 'environment');
  assert.equal(c.draws.length, 1);
  assert.equal(c.transforms.filter(t => t[0] === 'scale').length, 0);
  c.ctl.stop();
});

test('camera mirror follows actual device when browser falls back to a different camera', async () => {
  const c = camera({ facingMode: 'user', actualFacing: 'environment' });
  await c.ctl.start();
  assert.equal(c.transforms.filter(t => t[0] === 'scale').length, 0);
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
