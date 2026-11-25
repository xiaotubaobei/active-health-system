import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { computed, reactive, ref, watch, nextTick } from 'vue';

function page({ status = {}, fail = false } = {}) {
  const calls = [], saved = [], routes = [];
  const source = readFileSync(new URL('../src/views/Onboarding.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/import .*;\r?\n/g, '');
  const context = vm.createContext({
    computed, reactive, ref, watch, onMounted: () => {},
    getUser: () => ({ id: 1, age_group: 'middle_age', height_cm: 170, weight_kg: 65, goal: 'fitness', onboarding_done: false }),
    setUser: user => saved.push(user),
    useRouter: () => ({ push: async route => routes.push(route) }),
    errorMessage: (_, fallback) => fallback,
    api: {
      get: async url => ({ data: url === '/fitness/scales'
        ? [{ id: 'middle_elder', items: [{ key: 'bmi', name: '测试项目', weight: 100 }] }]
        : { onboarding_done: false, privacy_consent: true, baseline: null, ...status } }),
      post: async (url, body) => {
        calls.push({ url, body: JSON.parse(JSON.stringify(body)) });
        if (fail) throw new Error('offline');
        return { data: { user: { ...body, id: 1, onboarding_done: true },
          baseline: body.scores ? { total_score: 63.5 } : null,
          prescription_message: '可到方案页查看模板匹配情况' } };
      },
    },
  });
  vm.runInContext(source + '\nglobalThis.check = { form, consent, scores, current, load, submit, err, includeAssessment, done, baseline, message };', context);
  return { ...context.check, calls, saved, routes };
}

test('registration placeholders never prefill a first measurement or select a scale', async () => {
  const c = page();
  await c.load();
  assert.deepEqual(JSON.parse(JSON.stringify(c.form)), { age_group: '', height_cm: '', weight_kg: '', goal: '' });
  assert.equal(c.current.value, null);
  assert.equal(c.consent.value, false);
  await c.submit();
  assert.equal(c.calls.length, 0);
});

test('first profile sends the explicitly entered measurements and scores unchanged', async () => {
  const c = page();
  await c.load();
  Object.assign(c.form, { age_group: 'middle_age', height_cm: 161.7, weight_kg: 54.2, goal: 'fitness' });
  await nextTick();
  c.scores.bmi = 63.5;
  c.includeAssessment.value = true;
  c.consent.value = true;
  await c.submit();
  assert.equal(c.calls.length, 1);
  const { body } = c.calls[0];
  assert.equal(body.height_cm, 161.7);
  assert.equal(body.weight_kg, 54.2);
  assert.deepEqual(body.scores, { bmi: 63.5 });
  assert.equal(body.scale_id, 'middle_elder');
  assert.equal(c.saved.at(-1).onboarding_done, true);
  assert.equal(body.generate_prescription, false);
  assert.equal(c.done.value, true);
  assert.equal(c.baseline.value.total_score, 63.5);
  assert.deepEqual(c.routes, []);
});

test('a missing measured score is never replaced with a default', async () => {
  const c = page();
  await c.load();
  Object.assign(c.form, { age_group: 'middle_age', height_cm: 161.7, weight_kg: 54.2, goal: 'fitness' });
  await nextTick();
  c.includeAssessment.value = true;
  c.consent.value = true;
  await c.submit();
  assert.equal(c.calls.length, 0);
  assert.match(c.err.value, /测试项目/);
  assert.equal(c.scores.bmi, undefined);
});

test('without scores a user can save a profile, and only a later explicit action generates a draft', async () => {
  const c = page();
  await c.load();
  Object.assign(c.form, { age_group: 'middle_age', height_cm: 161.7, weight_kg: 54.2, goal: 'fitness' });
  c.consent.value = true;
  assert.equal(c.includeAssessment.value, false);
  await c.submit();
  assert.equal(c.calls.length, 1);
  assert.equal(c.calls[0].body.scale_id, undefined);
  assert.equal(c.calls[0].body.scores, undefined);
  assert.equal(c.calls[0].body.generate_prescription, false);
  assert.equal(c.done.value, true);
  assert.equal(c.baseline.value, null);
  assert.match(c.message.value, /方案页/);
  await c.submit();
  assert.equal(c.calls.length, 1);
});

test('deselecting score entry does not send abandoned partial scores', async () => {
  const c = page();
  await c.load();
  Object.assign(c.form, { age_group: 'middle_age', height_cm: 161.7, weight_kg: 54.2, goal: 'fitness' });
  await nextTick();
  c.includeAssessment.value = true;
  c.scores.bmi = 20;
  c.includeAssessment.value = false;
  c.consent.value = true;
  await c.submit();
  assert.equal(c.calls[0].body.scores, undefined);
});

test('after refresh a completed profile without assessment stays completed without a fake baseline', async () => {
  const c = page({ status: { onboarding_done: true } });
  await c.load();
  assert.equal(c.done.value, true);
  assert.equal(c.baseline.value, null);
  assert.equal(c.saved.at(-1).onboarding_done, true);
});

test('failed profile save keeps values and does not claim completion', async () => {
  const c = page({ fail: true });
  await c.load();
  Object.assign(c.form, { age_group: 'middle_age', height_cm: 161.7, weight_kg: 54.2, goal: 'fitness' });
  c.consent.value = true;
  await c.submit();
  assert.equal(c.done.value, false);
  assert.equal(c.form.weight_kg, 54.2);
  assert.match(c.err.value, /保存失败/);
  assert.equal(c.message.value, '');
});
