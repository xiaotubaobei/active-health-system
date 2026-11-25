import test from 'node:test';
import assert from 'node:assert/strict';
import { usePasswordChange } from '../src/composables/usePasswordChange.js';

function setup(post = async () => ({}), options = {}) {
  const events = [], requests = [];
  const s = usePasswordChange({ api: { post: (...args) => { requests.push(args); return post(...args); } },
    errorMessage: (e, fallback) => e.response?.data?.detail || fallback,
    onChanged: async () => events.push('changed'), onSignIn: async () => events.push('sign-in'), ...options });
  const fill = (next = 'new-password') => { s.current.value = 'old-password'; s.next.value = next; s.confirmation.value = next; };
  return { s, events, requests, fill };
}
const failure = status => ({ response: { status, data: { detail: '服务器提示' } } });
function assertCleared(s) { assert.equal(s.current.value + s.next.value + s.confirmation.value, ''); }

test('invalid or inconsistent passwords never send a request', async () => {
  const { s, fill, requests } = setup();
  await s.submit(); assert.match(s.error.value, /填写完整/);
  fill('short'); await s.submit(); assert.match(s.error.value, /8–128/);
  fill(); s.confirmation.value = 'another-new-password'; await s.submit(); assert.match(s.error.value, /不一致/);
  fill('old-password'); await s.submit(); assert.match(s.error.value, /相同/);
  assert.equal(requests.length, 0);
});

test('double clicks send once, preserve exact password and clear secrets before navigating', async () => {
  let finish;
  const { s, fill, requests, events } = setup(() => new Promise(resolve => { finish = resolve; }));
  fill('  新密码 with spaces  ');
  const pending = s.submit(); await s.submit();
  assert.equal(requests.length, 1);
  assert.deepEqual(requests[0], ['/auth/change-password', { current_password: 'old-password', new_password: '  新密码 with spaces  ' }, { skipAuthRedirect: true }]);
  finish({}); await pending;
  assertCleared(s); assert.equal(s.busy.value, false); assert.deepEqual(events, ['changed']);
  fill(); await s.submit(); assert.equal(requests.length, 1);
});

test('incorrect current password keeps account signed in and allows corrected submission', async () => {
  let attempts = 0;
  const { s, fill, events } = setup(async () => { if (++attempts === 1) throw failure(400); });
  fill(); await s.submit(); assertCleared(s);
  assert.equal(s.error.value, '服务器提示'); assert.deepEqual(events, []);
  fill(); await s.submit(); assert.deepEqual(events, ['changed']);
});

test('429 honors Retry-After without re-sending or signing out', async () => {
  let time = 1000, attempts = 0;
  const { s, fill, requests, events } = setup(async () => { if (++attempts === 1) throw { response: { status: 429, headers: { 'retry-after': '10' } } }; }, { now: () => time });
  fill(); await s.submit(); fill(); await s.submit();
  assert.equal(requests.length, 1); assert.match(s.error.value, /10 秒/); assert.deepEqual(events, []);
  time += 10000; await s.submit(); assert.deepEqual(events, ['changed']);
});

test('lost response, server failure and conflict require explicit sign-in, never replay password change', async () => {
  for (const reason of [new Error('response lost'), failure(503), failure(409)]) {
    const { s, fill, requests, events } = setup(async () => { throw reason; });
    fill(); await s.submit(); assertCleared(s);
    assert.equal(s.uncertain.value, true); assert.match(s.error.value, /先尝试新密码/);
    fill(); await s.submit(); assert.equal(requests.length, 1); assert.deepEqual(events, []);
  }
});

test('expired cookie clears secrets and returns to login without a success notice', async () => {
  const { s, fill, events } = setup(async () => { throw failure(401); });
  fill(); await s.submit(); assertCleared(s);
  assert.deepEqual(events, ['sign-in']); assert.equal(s.changed.value, false);
});

test('navigation failure after confirmed success never claims the password change failed', async () => {
  const { s, fill, requests } = setup(undefined, { onChanged: async () => { throw new Error('navigation failed'); } });
  fill(); await s.submit();
  assertCleared(s); assert.equal(s.changed.value, true); assert.equal(s.uncertain.value, false);
  assert.match(s.error.value, /密码已修改/);
  fill(); await s.submit(); assert.equal(requests.length, 1);
});

test('leaving the form clears passwords and ignores late responses', async () => {
  for (const fail of [false, true]) {
    let finish;
    const { s, fill, events } = setup(() => new Promise((resolve, reject) => { finish = fail ? () => reject(failure(401)) : resolve; }));
    fill(); const pending = s.submit(); s.dispose(); assertCleared(s); finish({}); await pending;
    assert.deepEqual(events, []); assert.equal(s.error.value, '');
  }
});
