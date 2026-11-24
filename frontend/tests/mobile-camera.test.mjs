import test from 'node:test';
import assert from 'node:assert/strict';
import { cameraSupportError, cameraErrorMessage } from '../src/utils/cameraAccess.js';
import { createScreenAwake } from '../src/utils/screenAwake.js';

function lock() {
  const value = new EventTarget();
  value.released = false;
  value.release = async () => { value.released = true; value.dispatchEvent(new Event('release')); };
  return value;
}
function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
}
function setup(request) {
  const states = [], document = { visibilityState: 'visible' };
  const controller = createScreenAwake({ navigator: { wakeLock: { request } }, document, onChange: state => states.push(state) });
  return { controller, states, document };
}

test('camera readiness distinguishes insecure URLs and unsupported browsers without requesting access', () => {
  assert.match(cameraSupportError({ isSecureContext: false }), /HTTPS.*局域网 HTTP/);
  assert.match(cameraSupportError({ isSecureContext: true }), /系统浏览器.*视频文件/);
  assert.equal(cameraSupportError({ isSecureContext: true, navigator: { mediaDevices: { getUserMedia() {} } } }), '');
});

test('camera failures give actionable permission, device, busy and interrupted explanations', () => {
  for (const [name, message] of [['NotAllowedError', /网站设置.*系统权限/], ['NotFoundError', /没有找到/], ['NotReadableError', /占用/], ['OverconstrainedError', /拍摄设置/], ['AbortError', /中断/]]) {
    assert.match(cameraErrorMessage({ name }), message);
  }
  assert.doesNotMatch(cameraErrorMessage(new Error('internal details')), /internal details/);
});

test('one screen lock covers active capture and is released on pause', async () => {
  const held = lock(); let calls = 0;
  const p = setup(async type => { assert.equal(type, 'screen'); calls++; return held; });
  const first = p.controller.setActive(true);
  assert.equal(await p.controller.setActive(true), true);
  assert.equal(await first, true);
  await p.controller.setActive(true);
  assert.equal(calls, 1);
  assert.equal(p.states.at(-1), 'active');
  await p.controller.setActive(false);
  assert.equal(held.released, true);
  assert.equal(p.states.at(-1), 'idle');
});

test('late permission result after pause is immediately released', async () => {
  const permission = deferred(), held = lock();
  const p = setup(() => permission.promise);
  const pending = p.controller.setActive(true);
  await Promise.resolve();
  await p.controller.setActive(false);
  permission.resolve(held);
  assert.equal(await pending, false);
  assert.equal(held.released, true);
  assert.equal(p.states.at(-1), 'idle');
});

test('resume during pending request keeps only the new lock; old releases cannot change its status', async () => {
  const oldRequest = deferred(), old = lock(), current = lock(); let calls = 0;
  const p = setup(() => ++calls === 1 ? oldRequest.promise : current);
  const pending = p.controller.setActive(true);
  await Promise.resolve();
  await p.controller.setActive(false);
  assert.equal(await p.controller.setActive(true), true);
  oldRequest.resolve(old);
  await pending;
  assert.equal(old.released, true);
  assert.equal(current.released, false);
  assert.equal(p.states.at(-1), 'active');
  await p.controller.dispose();
  assert.equal(current.released, true);
  assert.equal(await p.controller.setActive(true), false);
});

test('browser release and denied request need explicit retry, without retry loops', async () => {
  const held = lock(); let calls = 0;
  const p = setup(() => { if (++calls === 1) throw new Error('battery saving'); return held; });
  assert.equal(await p.controller.setActive(true), false);
  assert.equal(p.states.at(-1), 'unavailable');
  assert.equal(calls, 1);
  assert.equal(await p.controller.setActive(true), true);
  await held.release();
  assert.equal(p.states.at(-1), 'unavailable');
  assert.equal(calls, 2);
});

test('unsupported and hidden browsers do not block training or request a screen lock', async () => {
  const states = [];
  const unsupported = createScreenAwake({ navigator: {}, onChange: state => states.push(state) });
  assert.equal(await unsupported.setActive(true), false);
  assert.equal(states.at(-1), 'unsupported');
  let calls = 0;
  const p = setup(async () => { calls++; return lock(); });
  p.document.visibilityState = 'hidden';
  assert.equal(await p.controller.setActive(true), false);
  assert.equal(calls, 0);
});
