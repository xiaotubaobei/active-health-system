import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function page(post) {
  const source = readFileSync(new URL('../src/views/BodyParse.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0]
    .replace(/import .*;\r?\n/g, '');
  const context = vm.createContext({
    ref: value => ({ value }), computed: fn => ({ get value() { return fn(); } }),
    getUser: () => ({ id: 1 }), api: { post },
    errorMessage: (e, fallback) => e.response?.data?.detail || fallback,
  });
  vm.runInContext(source + '\n globalThis.check = { run, waist, hip, busy, err, msg, current };', context);
  return context.check;
}

test('empty, zero, negative and excessive circumference never send a save request', async () => {
  let count = 0;
  const c = page(async () => { count++; });
  assert.equal(c.waist.value, '');
  assert.equal(c.hip.value, '');
  for (const value of ['', 0, -10, 301, Infinity, NaN]) {
    c.waist.value = value; c.hip.value = 95;
    await c.run();
    assert.match(c.err.value, /腰围、臀围/);
    assert.equal(c.busy.value, false);
  }
  c.waist.value = 80; c.hip.value = 0;
  await c.run();
  assert.equal(count, 0);
});

test('failed saves show an error, clear stale success, and can retry', async () => {
  let fail = true;
  const c = page(async () => {
    if (fail) throw new Error('offline');
    return { data: { current: { bmi: 22.49, whr: .847 } } };
  });
  c.waist.value = 80.5; c.hip.value = 95;
  c.current.value = { bmi: 999 }; c.msg.value = 'old success';
  await c.run();
  assert.equal(c.current.value, null);
  assert.equal(c.msg.value, '');
  assert.match(c.err.value, /保存失败/);
  assert.equal(c.busy.value, false);
  fail = false;
  await c.run();
  assert.equal(c.current.value.whr, .847);
  assert.equal(c.err.value, '');
  assert.match(c.msg.value, /已保存/);
});

test('repeated clicks during saving create only one record request', async () => {
  let resolve, count = 0;
  const c = page(() => { count++; return new Promise(r => { resolve = r; }); });
  c.waist.value = 80; c.hip.value = 95;
  const pending = c.run();
  await c.run();
  assert.equal(count, 1);
  assert.equal(c.busy.value, true);
  resolve({ data: { current: { bmi: 22.49 } } });
  await pending;
  assert.equal(c.busy.value, false);
});
