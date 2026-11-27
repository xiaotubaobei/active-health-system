<template>
  <div class="card">
    <h2>建立基本档案</h2>
    <p class="muted">先填写本人的基本资料。体测分数可以以后再补，不需要猜分，也不会用默认分数代填。</p>
    <p v-if="loading">正在读取档案…</p>
    <p v-if="loadErr" class="err" role="alert">{{ loadErr }}</p>
    <button v-if="loadErr || (!ready && !loading)" :disabled="loading || busy" @click="load">重新加载档案</button>
    <p v-if="catalogErr && !done" class="err" role="alert">{{ catalogErr }}</p>
    <button v-if="catalogErr && !done" type="button" class="secondary" :disabled="loading || catalogLoading || busy" @click="loadScales">重试加载评估项目</button>
    <p v-if="catalogLoading && !done" class="muted" role="status">正在读取评估项目…</p>
    <div v-if="done">
      <p class="ok" role="status">基本档案已建立。</p>
      <p v-if="baseline">首次录入分数汇总：{{ baseline.total_score }} 分（试验性加权汇总，不代表体适能达标）</p>
      <p v-else class="muted">尚未录入体测分数，没有体测基线；这不表示体适能正常。有完整的换算分后，可到体适能评估页补录。</p>
      <p v-if="message" class="muted">{{ message }}</p>
      <div class="row">
        <router-link to="/fitness"><button>{{ baseline ? '录入后续体测' : '补录已有体测分数' }}</button></router-link>
        <router-link to="/prescription"><button class="secondary">查看模板匹配与送审</button></router-link>
        <router-link to="/profile"><button class="secondary">修改基本资料</button></router-link>
      </div>
    </div>
    <form v-else-if="ready" novalidate @submit.prevent="submit">
      <fieldset :disabled="busy" style="border:0;padding:0;margin:0;min-width:0">
      <div class="row" style="margin:12px 0">
        <label>年龄组 <select id="onboarding-age" v-model="form.age_group" required :aria-invalid="Boolean(profileErrors.age_group)" aria-describedby="profile-age-error" @change="delete profileErrors.age_group"><option value="" disabled>请选择</option><option value="youth">青少年</option><option value="middle_age">中年</option><option value="elder">老年</option></select><span v-if="profileErrors.age_group" id="profile-age-error" class="err">{{ profileErrors.age_group }}</span></label>
        <label>身高（厘米）<input id="onboarding-height" v-model.number="form.height_cm" type="number" step="0.1" min="1" max="300" required :aria-invalid="Boolean(profileErrors.height_cm)" aria-describedby="profile-height-error" @input="delete profileErrors.height_cm" /><span v-if="profileErrors.height_cm" id="profile-height-error" class="err">{{ profileErrors.height_cm }}</span></label>
        <label>体重（公斤）<input id="onboarding-weight" v-model.number="form.weight_kg" type="number" step="0.1" min="1" max="700" required :aria-invalid="Boolean(profileErrors.weight_kg)" aria-describedby="profile-weight-error" @input="delete profileErrors.weight_kg" /><span v-if="profileErrors.weight_kg" id="profile-weight-error" class="err">{{ profileErrors.weight_kg }}</span></label>
      </div>
      <div class="row" style="margin:12px 0">
        <label>运动目标 <select id="onboarding-goal" v-model="form.goal" required :aria-invalid="Boolean(profileErrors.goal)" aria-describedby="profile-goal-error" @change="delete profileErrors.goal"><option value="" disabled>请选择</option><option value="fitness">日常健身</option><option value="medical">健康管理（需专业人员审核）</option></select><span v-if="profileErrors.goal" id="profile-goal-error" class="err">{{ profileErrors.goal }}</span></label>
        <label>已知健康标签（选填，用逗号分隔）<input v-model="tags" placeholder="仅填写已确认的情况，不要猜填" /></label>
      </div>
      <p class="muted">身高、体重请填写本人实际测量值。健康标签留空仅表示未提供，不代表确认没有疾病。方案尚需核对本人情况，标签匹配不等于适合训练。</p>
      <p><label><input v-model="includeAssessment" type="checkbox" /> 我已有整套体测的 0–100 换算分，现在一并录入（选填）</label></p>
      <div v-if="includeAssessment">
      <h3>{{ current?.name || '请先选择年龄组' }}</h3>
      <p class="muted">下方只能填写已有的换算分，不是体重、秒数或次数。当前尚未提供原始成绩换算标准；没有换算分请取消勾选，先保存档案。</p>
      <p v-if="scaleSwitchNotice" class="warn" role="status">{{ scaleSwitchNotice }}</p>
      <details><summary>我暂时没有体测换算分</summary><p class="muted">取消勾选即可先保存基本档案。没有体测分数不代表身体情况正常；训练方案仍需核对本人情况并审核。</p></details>
      <div v-for="item in current?.items || []" :key="item.key" class="score-field">
        <label :for="`score-${item.key}`">{{ item.name }} · 必填</label>
        <input :id="`score-${item.key}`" v-model.number="scores[item.key]" type="number" min="0" :max="maxScore(item)" step="any" required placeholder="输入换算分" :aria-invalid="Boolean(fieldErrors[item.key])" :aria-describedby="`score-help-${item.key} score-error-${item.key}`" @input="delete fieldErrors[item.key]; err = ''" />
        <p :id="`score-help-${item.key}`" class="muted field-help">有效范围：0–{{ maxScore(item) }} 分；量表权重 {{ item.weight }}</p>
        <p v-if="fieldErrors[item.key]" :id="`score-error-${item.key}`" class="err field-help" role="alert">{{ fieldErrors[item.key] }}</p>
      </div>
      </div>
      <p><label><input id="onboarding-consent" v-model="consent" type="checkbox" required :aria-invalid="Boolean(consentErr)" aria-describedby="onboarding-consent-error" @change="consentErr = ''" /> 我同意将上述资料、测评与训练记录用于本系统的个人档案；本系统提供运动健康建议，不构成医疗诊断或治疗。</label></p>
      <p v-if="consentErr" id="onboarding-consent-error" class="err" role="alert">{{ consentErr }}</p>
      <p v-if="err" class="err" role="alert">{{ err }}</p>
      <button type="submit" :disabled="busy || loading || (includeAssessment && (catalogLoading || !current))">{{ busy ? "正在保存…" : err ? "重试保存基本档案" : "保存基本档案" }}</button>
      </fieldset>
    </form>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import api, { errorMessage, getUser, setUser } from "../api/client";
import { validScale, maxScore, scoreError } from "../utils/assessmentScores";

const user = getUser();
// 注册时的历史占位值不是用户确认过的测量值，首次填写必须由本人输入。
const form = reactive({ age_group: "", height_cm: "", weight_kg: "", goal: "" });
const tags = ref((user.chronic_tags || []).join(", "));
const consent = ref(false);
const includeAssessment = ref(false);
const message = ref("");
const scores = reactive({});
const scales = ref([]);
const done = ref(false);
const baseline = ref(null);
const loading = ref(false);
const ready = ref(false);
const busy = ref(false);
const err = ref("");
const loadErr = ref("");
const catalogErr = ref("");
const catalogLoading = ref(false);
const consentErr = ref("");
const fieldErrors = reactive({});
const profileErrors = reactive({});
const scaleSwitchNotice = ref("");
const current = computed(() => form.age_group ? scales.value.find((s) => s.id === (form.age_group === "youth" ? "youth" : "middle_elder")) : null);
// 暂存本页已输入的分数；不同年龄组各自保存，避免错用同名项目。
const scoreDrafts = new Map();
watch(() => form.age_group, (age, previous) => {
  if (previous) scoreDrafts.set(previous, { ...scores });
  for (const key of Object.keys(scores)) delete scores[key];
  Object.assign(scores, scoreDrafts.get(age) || {});
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
  err.value = "";
  if (previous) scaleSwitchNotice.value = "已切换年龄组；各年龄组的分数分别暂存，请核对当前项目。";
});

async function loadScales() {
  if (busy.value || catalogLoading.value) return;
  catalogLoading.value = true;
  catalogErr.value = "";
  try {
    const { data } = await api.get("/fitness/scales");
    if (!Array.isArray(data) || !data.length || !data.every(validScale)) throw new Error("量表不完整");
    if (scales.value.length && JSON.stringify(scales.value) !== JSON.stringify(data)) {
      scoreDrafts.clear();
      for (const key of Object.keys(scores)) delete scores[key];
      for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
      scaleSwitchNotice.value = "评估项目或规则有更新，请重新核对并填写分数。";
    }
    scales.value = data;
  } catch (error) {
    catalogErr.value = errorMessage(error, "评估项目加载失败，可重试，也可以不录体测分数先保存基本档案。");
  } finally { catalogLoading.value = false; }
}

async function load() {
  if (loading.value || busy.value) return;
  loading.value = true;
  loadErr.value = "";
  try {
    const [status] = await Promise.all([
      api.get("/onboarding/status", { params: { user_id: user.id } }), loadScales(),
    ]);
    done.value = status.data.onboarding_done;
    baseline.value = status.data.baseline;
    setUser({ ...getUser(), onboarding_done: done.value, privacy_consent: status.data.privacy_consent });
    ready.value = true;
  } catch (error) {
    loadErr.value = errorMessage(error, "无法读取档案状态，请检查连接后重新加载。");
  } finally { loading.value = false; }
}

async function submit() {
  if (busy.value || loading.value || (includeAssessment.value && catalogLoading.value) || done.value || !ready.value) return;
  err.value = "";
  consentErr.value = "";
  for (const key of Object.keys(profileErrors)) delete profileErrors[key];
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
  if (!["youth", "middle_age", "elder"].includes(form.age_group)) profileErrors.age_group = "请选择本人的年龄组。";
  if (!Number.isFinite(Number(form.height_cm)) || Number(form.height_cm) < 1 || Number(form.height_cm) > 300) profileErrors.height_cm = "请填写实际身高（1–300 厘米）。";
  if (!Number.isFinite(Number(form.weight_kg)) || Number(form.weight_kg) < 1 || Number(form.weight_kg) > 700) profileErrors.weight_kg = "请填写实际体重（1–700 公斤）。";
  if (!["fitness", "medical"].includes(form.goal)) profileErrors.goal = "请选择运动目标。";
  if (Object.keys(profileErrors).length) {
    err.value = "请选择年龄组、运动目标，并填写本人实际测量的身高和体重。";
    const ids = { age_group: "age", height_cm: "height", weight_kg: "weight", goal: "goal" };
    await focusField(`onboarding-${ids[Object.keys(profileErrors)[0]]}`);
    return;
  }
  const payload = {};
  if (includeAssessment.value && !validScale(current.value)) {
    err.value = "当前年龄组的量表未加载，请重试；也可以先不录体测分数。";
    return;
  }
  for (const item of includeAssessment.value ? current.value.items : []) {
    const value = scores[item.key];
    const message = scoreError(item, value);
    if (message) fieldErrors[item.key] = message;
    else payload[item.key] = Number(value);
  }
  if (Object.keys(fieldErrors).length) {
    const first = Object.keys(fieldErrors)[0];
    err.value = fieldErrors[first];
    await focusField(`score-${first}`);
    return;
  }
  if (!consent.value) {
    err.value = "请先阅读并同意个人档案的使用说明。";
    consentErr.value = err.value;
    await focusField("onboarding-consent");
    return;
  }
  busy.value = true;
  try {
    const { data } = await api.post("/onboarding/complete", {
      ...form, user_id: user.id,
      ...(includeAssessment.value ? { scale_id: current.value.id, scores: payload } : {}),
      chronic_tags: tags.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      privacy_consent: true, generate_prescription: false,
    });
    setUser(data.user);
    baseline.value = data.baseline || null;
    message.value = data.prescription_message || "基本档案已保存。可继续补录体测，或到方案页查看模板匹配情况。";
    done.value = true;
  } catch (error) { err.value = errorMessage(error, "保存失败，请检查资料和分数后重试。"); }
  finally { busy.value = false; }
}
async function focusField(id) {
  await nextTick();
  const input = document.getElementById(id);
  input?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  input?.focus({ preventScroll: true });
}
onMounted(load);
</script>

<style scoped>
.score-field { display: grid; grid-template-columns: minmax(0, 1fr) minmax(150px, 240px); align-items: center; gap: 6px 16px; margin: 12px 0; }
.score-field input { width: 100%; }
.field-help { grid-column: 1 / -1; margin: 0; }
[aria-invalid="true"] { border-color: var(--bad); }
@media (max-width: 600px) {
  .score-field { grid-template-columns: minmax(0, 1fr); }
}
</style>
