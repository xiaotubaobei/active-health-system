import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import * as videoInput from '../src/utils/videoInput.js';

class Video extends EventTarget {
  constructor({ duration = 0.5, failLoad = false, stallSeek = false } = {}) {
    super(); Object.assign(this, { duration, failLoad, stallSeek, src: '', readyState: 0,
      videoWidth: 640, videoHeight: 480, seeking: false, position: 0, listeners: new Set() });
  }
  addEventListener(type, fn) { super.addEventListener(type, fn); this.listeners.add(fn); }
  removeEventListener(type, fn) { super.removeEventListener(type, fn); this.listeners.delete(fn); }
  pause() {}
  load() {
    this.position = 0;
    this.readyState = this.src ? 2 : 0;
    if (this.src) this.dispatchEvent(new Event(this.failLoad ? 'error' : 'loadeddata'));
  }
  removeAttribute(name) { if (name === 'src') this.src = ''; }
  get currentTime() { return this.position; }
  set currentTime(value) {
    this.position = value; this.seeking = this.stallSeek;
    if (!this.stallSeek) this.dispatchEvent(new Event('seeked'));
  }
}

function processor(model) {
  const revoked = [];
  let clock = 0;
  const source = readFileSync(new URL('../src/composables/usePoseVideoFile.js', import.meta.url), 'utf8')
    .replace(/import[\s\S]*?from\s*["'][^"']+["'];/g, '').replace('export async function', 'async function');
  const context = vm.createContext({ ...videoInput,
    getPoseLandmarker: model, drawSkeleton() {},
    landmarksToMp33Frame: (landmarks, t_ms, frame_index) => ({ landmarks, t_ms, frame_index }),
    anglesFromLandmarks: () => ({}), hintFromAngles: () => 'test pose',
    URL: { createObjectURL: () => 'blob:fixture', revokeObjectURL: url => revoked.push(url) },
    performance: { now: () => ++clock },
  });
  vm.runInContext(source + '\nglobalThis.process = processVideoFile;', context);
  return { process: context.process, revoked };
}

const file = { size: 20, type: 'video/mp4' };
const landmarks = Array.from({ length: 33 }, (_, i) => ({ i, x: 0.1, y: 0.2 }));

test('rejects empty, oversized and non-video inputs before processing', () => {
  for (const input of [null, { size: 0 }, { size: videoInput.MAX_VIDEO_BYTES + 1 }, { size: 10, type: 'text/plain' }]) {
    assert.throws(() => videoInput.validateVideoFile(input));
  }
  videoInput.validateVideoFile({ size: 10, type: '' }); // Some phones omit MIME type.
});

test('initial decoded frame does not wait forever for a redundant seek event', async () => {
  const video = new Video();
  await videoInput.loadVideoSource(video, 'blob:fixture', { timeoutMs: 30 });
  await videoInput.seekVideo(video, 0, { timeoutMs: 30 });
  assert.equal(video.listeners.size, 0);
});

test('seek timeout and cancellation remove all media event handlers', async () => {
  const video = new Video({ stallSeek: true }); video.readyState = 2;
  await assert.rejects(videoInput.seekVideo(video, 1, { timeoutMs: 10 }), /超时/);
  assert.equal(video.listeners.size, 0);
  const controller = new AbortController();
  const pending = videoInput.seekVideo(video, 2, { signal: controller.signal });
  controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
  assert.equal(video.listeners.size, 0);
});

test('samples a short video including its initial frame and releases its object URL', async () => {
  const times = [];
  const p = processor(async () => ({ detectForVideo: (video, timestamp) => {
    times.push(timestamp); return { landmarks: [landmarks] };
  } }));
  const video = new Video();
  const result = await p.process({ video, file });
  assert.equal(result.mpFrames.length, 3);
  assert.equal(result.mpFrames[0].t_ms, 0);
  assert.equal(result.mpFrames[2].t_ms, 1000 / 3);
  assert.deepEqual(times, [1, 2, 3]);
  assert.deepEqual(p.revoked, ['blob:fixture']);
  assert.equal(video.src, '');
  assert.equal(video.listeners.size, 0);
});

test('rejects long videos before loading the model and cleans up after decode failure', async () => {
  let modelCalls = 0;
  const p = processor(async () => { modelCalls++; });
  await assert.rejects(p.process({ video: new Video({ duration: 181 }), file }), /3分钟/);
  await assert.rejects(p.process({ video: new Video({ failLoad: true }), file }), /无法读取/);
  assert.equal(modelCalls, 0);
  assert.equal(p.revoked.length, 2);
});

test('cancel during model loading returns promptly and a late model cannot restart parsing', async () => {
  let resolveModel, reachedModel;
  const reached = new Promise(resolve => { reachedModel = resolve; });
  let detections = 0;
  const p = processor(() => { reachedModel(); return new Promise(resolve => { resolveModel = resolve; }); });
  const controller = new AbortController();
  const video = new Video();
  const pending = p.process({ video, file, signal: controller.signal });
  await reached; controller.abort();
  await assert.rejects(pending, { name: 'AbortError' });
  resolveModel({ detectForVideo() { detections++; } });
  await Promise.resolve();
  assert.equal(detections, 0);
  assert.equal(video.src, '');
  assert.equal(video.listeners.size, 0);
  assert.equal(p.revoked.length, 1);
});

test('model failure, no-person result and mid-scan cancellation all release the video', async () => {
  for (const outcome of ['failure', 'empty', 'cancel']) {
    const controller = new AbortController();
    const p = processor(async () => {
      if (outcome === 'failure') throw new Error('model failed');
      return { detectForVideo: () => ({ landmarks: outcome === 'empty' ? [] : [landmarks] }) };
    });
    const video = new Video();
    await assert.rejects(p.process({ video, file, signal: controller.signal,
      onProgress: progress => { if (outcome === 'cancel' && progress.phase === 'scan') controller.abort(); },
    }));
    assert.equal(video.src, '');
    assert.equal(video.listeners.size, 0);
    assert.equal(p.revoked.length, 1);
  }
});
