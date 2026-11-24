import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { createAuthGuard, safeReturnPath, loginDestination } from '../src/utils/authNavigation.js';

const target = { path: '/exercise', fullPath: '/exercise?session_id=42' };
function guardFixture(cached, response) {
  const calls = [];
  const guard = createAuthGuard({
    getUser: () => cached,
    setUser: user => calls.push(['set', user]), clearUser: () => calls.push(['clear']),
    api: { get: async (...args) => { calls.push(args); return response(); } },
  });
  return { guard, calls };
}

test('first visit and expired login have distinct messages and retain destination', async () => {
  for (const cached of [null, { id: 1 }]) {
    const { guard, calls } = guardFixture(cached, () => { throw { response: { status: 401 } }; });
    const result = await guard(target);
    assert.equal(result.path, '/login');
    assert.equal(result.query.next, target.fullPath);
    assert.equal(result.query.expired, cached ? '1' : undefined);
    assert.equal(calls[0][1].skipAuthRedirect, true);
    assert.deepEqual(calls[1], ['clear']);
  }
});

test('network outage preserves account and saved-session cache, retry reaches original page', async () => {
  let offline = true;
  const { guard, calls } = guardFixture({ id: 1 }, () => {
    if (offline) throw new Error('offline');
    return { data: { id: 1, role: 'user', onboarding_done: true } };
  });
  assert.deepEqual(await guard(target), { path: '/connection', query: { next: target.fullPath } });
  assert.equal(calls.some(call => call[0] === 'clear'), false);
  offline = false;
  assert.equal(await guard(target), true);
  assert.equal(calls.at(-1)[0], 'set');
});

test('public recovery/login pages never probe the unavailable server; onboarding still enforced', async () => {
  const { guard, calls } = guardFixture(null, () => { throw new Error('must not run'); });
  assert.equal(await guard({ path: '/connection' }), true);
  assert.equal(await guard({ path: '/login' }), true);
  assert.equal(calls.length, 0);
  const incomplete = role => guardFixture(null, () => ({ data: { id: 1, role, onboarding_done: false } })).guard;
  assert.equal(await incomplete('user')(target), '/onboarding');
  assert.equal(await incomplete('physician')({ path: '/reviews' }), true);
});

test('login return paths reject external sites and redirect loops', () => {
  for (const value of ['https://other.test', '//other.test', '/\\other.test', '/login?next=/login', '/connection', '/x\n', null, ['//other.test']]) {
    assert.equal(safeReturnPath(value), '/');
  }
  assert.equal(safeReturnPath(target.fullPath), target.fullPath);
});

test('API interceptor lets guards handle 401, and retains intended page for expired requests', async () => {
  const source = readFileSync(new URL('../src/api/client.js', import.meta.url), 'utf8')
    .replace(/^import .*;$/gm, '').replace(/export default api;/g, '').replace(/export /g, '');
  let interceptor, redirects = [];
  const cache = new Map([['ah_user', '{"id":1}'], ['ah_last_session', '42']]);
  vm.runInNewContext(source, {
    axios: { create: () => ({ interceptors: { response: { use: (ok, fail) => { interceptor = fail; } } } }) },
    loginDestination, URLSearchParams,
    localStorage: { getItem: key => cache.get(key), removeItem: key => cache.delete(key) },
    window: { location: { pathname: '/exercise', search: '?session_id=42', hash: '', replace: url => redirects.push(url) } },
  });
  await assert.rejects(interceptor({ response: { status: 401 }, config: { url: '/users/me', skipAuthRedirect: true } }));
  assert.equal(redirects.length, 0);
  assert.equal(cache.size, 2);
  await assert.rejects(interceptor({ response: { status: 401 }, config: { url: '/sessions/42' } }));
  assert.equal(cache.size, 0);
  assert.equal(redirects[0], '/login?next=%2Fexercise%3Fsession_id%3D42&expired=1');
});
