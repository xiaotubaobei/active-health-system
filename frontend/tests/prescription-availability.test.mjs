import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { computed, ref } from 'vue';

function page({ matched = false, failLoad = false, rejectGenerate = false } = {}) {
  const posts = [];
  const original = { id: 12, version: 1, status: 'pre_prescription' };
  const source = readFileSync(new URL('../src/views/Prescription.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/import .*;\r?\n/g, '');
  const context = vm.createContext({
    computed, ref, onMounted: () => {}, getUser: () => ({ id: 1 }),
    errorMessage: e => e.response?.data?.detail || '读取失败',
    formatTime: () => '', reviewStatus: {}, roleLabel: {},
    api: {
      get: async url => {
        if (url === '/prescriptions/availability') {
          if (failLoad) throw new Error('offline');
          return { data: { matched, reason: matched ? '仅匹配目录' : '暂无匹配模板，需要专业评估' } };
        }
        if (url.startsWith('/prescriptions/current')) return { data: original };
        return { data: { items: [], total: 0 } };
      },
      post: async (url, body) => {
        posts.push({ url, body });
        if (rejectGenerate) throw { response: { status: 422, data: { detail: '资料已变化，暂无匹配模板' } } };
        return { data: {} };
      },
    },
  });
  vm.runInContext(source + '\nglobalThis.check = { load, generate, current, availability, loaded, error, success };', context);
  return { ...context.check, posts, original };
}

test('unmatched profiles retain historical plan and cannot generate a replacement', async () => {
  const c = page();
  await c.load();
  assert.equal(c.loaded.value, true);
  assert.equal(c.current.value.id, c.original.id);
  assert.match(c.availability.value.reason, /暂无匹配/);
  await c.generate();
  assert.equal(c.posts.length, 0);
});

test('availability outage blocks generation instead of assuming a matching plan', async () => {
  const c = page({ failLoad: true });
  await c.load();
  assert.equal(c.loaded.value, false);
  assert.equal(c.availability.value, null);
  assert.match(c.error.value, /读取失败/);
  await c.generate();
  assert.equal(c.posts.length, 0);
});

test('a server rejection after profile changes keeps current plan and displays the reason', async () => {
  const c = page({ matched: true, rejectGenerate: true });
  await c.load();
  await c.generate();
  assert.equal(c.posts.length, 1);
  assert.equal(c.current.value.id, c.original.id);
  assert.equal(c.success.value, '');
  assert.match(c.error.value, /资料已变化/);
});
