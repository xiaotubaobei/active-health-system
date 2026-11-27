<template>
  <div class="card">
    <h2>首次测评与运动档案</h2>
    <p class="muted">填写个人资料和已有体测的项目得分，保存为首次基线，并生成一份模板处方供查看。</p>
    <p v-if="loading && !ready" role="status">正在读取档案和测评量表…</p>
    <p v-if="loadErr" class="err" role="alert">{{ loadErr }}</p>
    <button v-if="loadErr" class="secondary" type="button" @click="load" :disabled="loading">
      {{ loading ? "正在重新加载…" : "重新加载" }}
    </button>
    <div v-if="done">
      <p class="ok">首次测评已完成。后续测评请进入「体适能评估」。</p>
      <template v-if="baseline">
        <p>首次基线：{{ baseline.total_score ?? "—" }} 分（{{ levelName(baseline.level) }}）</p>
        <p class="muted">量表：{{ current?.name || "体适能评测" }}</p>
      </template>
      <p v-else class="muted">没有找到可展示的首次测评结果。</p>
      <div class="row">
        <router-link to="/prescription"><button type="button">查看训练计划</button></router-link>
        <router-link to="/fitness"><button class="secondary" type="button">后续体适能评估</button></router-link>
      </div>
    </div>
    <form v-else-if="ready" novalidate @submit.prevent="submit">
      <div class="row" style="margin:12px 0">
        <label>年龄组 <select v-model="form.age_group"><option value="youth">青少年</option><option value="middle_age">中年</option><option value="elder">老年</option></select></label>
        <label>身高（厘米）<input v-model.number="form.height_cm" type="number" step="0.1" min="1" max="300" required /></label>
        <label>体重（公斤）<input v-model.number="form.weight_kg" type="number" step="0.1" min="1" max="700" required /></label>
      </div>
      <div class="row" style="margin:12px 0">
        <label>运动目标 <select v-model="form.goal"><option value="fitness">日常健身</option><option value="medical">健康管理（需专业人员审核）</option></select></label>
        <label>慢病标签（选填，用逗号分隔）<input v-model="tags" placeholder="如 hypertension, diabetes" /></label>
      </div>
      <h3>{{ current?.name || "体适能评测" }}</h3>
      <p class="muted">
        各项填写已按正式体测标准换算出的分数，不是次数、秒数或体重。当前页面不提供原始成绩换算规则；没有换算分时请先向项目人员确认测量方法和标准。系统不会估算或自动补分。
      </p>
      <p v-if="scaleSwitchNotice" class="warn" role="status">{{ scaleSwitchNotice }}</p>
      <details class="score-help">
        <summary>我暂时没有体测换算分</summary>
        <p class="muted">请先按项目确认的测评标准完成测量并取得换算分。如不清楚测量或换算标准，请联系项目人员确认。首次测评完成前暂不能开始训练；系统不会代填或估算分数。</p>
      </details>
      <div class="score-list">
        <div
          v-for="item in current?.items || []"
          :key="item.key"
          class="score-field"
          :class="{ 'has-error': fieldErrors[item.key] }"
        >
          <label :for="`score-${item.key}`">{{ item.name }} · 必填</label>
          <input
            :id="`score-${item.key}`"
            v-model.number="scores[item.key]"
            type="number"
            min="0"
            :max="maxScore(item)"
            step="any"
            :aria-invalid="Boolean(fieldErrors[item.key])"
            :aria-describedby="fieldErrors[item.key] ? `score-help-${item.key} score-error-${item.key}` : `score-help-${item.key}`"
            placeholder="输入换算分"
            @input="clearFieldError(item.key)"
          />
          <p :id="`score-help-${item.key}`" class="field-help muted">有效范围：0–{{ maxScore(item) }} 分；量表权重 {{ item.weight }}</p>
          <p v-if="fieldErrors[item.key]" :id="`score-error-${item.key}`" class="field-error" role="alert">{{ fieldErrors[item.key] }}</p>
        </div>
      </div>
      <p>
        <label for="onboarding-consent">
          <input id="onboarding-consent" v-model="consent" type="checkbox" :aria-invalid="Boolean(consentErr)" :aria-describedby="consentErr ? 'onboarding-consent-error' : undefined" @change="consentErr = ''" />
          我同意将上述资料、测评与训练记录用于本系统的个人档案；本系统提供运动健康建议，不构成医疗诊断或治疗。
        </label>
      </p>
      <p v-if="consentErr" id="onboarding-consent-error" class="field-error" role="alert">{{ consentErr }}</p>
      <p v-if="submitErr" class="err" role="alert">{{ submitErr }}</p>
      <button type="submit" :disabled="busy || loading || !current">
        {{ busy ? "正在保存…" : submitErr ? "重试保存" : "保存首次测评并生成模板处方" }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import api, { errorMessage, getUser, setUser } from "../api/client";

const router = useRouter();
const user = getUser();
const form = reactive({ age_group: user.age_group || "middle_age", height_cm: user.height_cm || 170, weight_kg: user.weight_kg || 65, goal: user.goal || "fitness" });
const tags = ref((user.chronic_tags || []).join(", "));
const consent = ref(false);
const consentErr = ref("");
const scores = reactive({});
const scales = ref([]);
const scoreDrafts = reactive({});
const fieldErrors = reactive({});
const done = ref(false);
const baseline = ref(null);
const loading = ref(false);
const ready = ref(false);
const busy = ref(false);
const loadErr = ref("");
const submitErr = ref("");
const current = computed(() => scales.value.find((s) => s.id === (form.age_group === "youth" ? "youth" : "middle_elder")));
const scaleSwitchNotice = ref("");
const levelName = (level) => ({ excellent: "优秀", good: "良好", average: "一般", poor: "较弱" }[level] || "未评级");
const maxScore = (item) => item.max_score == null || !Number.isFinite(Number(item.max_score)) ? 100 : Number(item.max_score);

watch(() => form.age_group, (ageGroup, previousAgeGroup) => {
  const previousScaleId = previousAgeGroup === "youth" ? "youth" : "middle_elder";
  const nextScaleId = ageGroup === "youth" ? "youth" : "middle_elder";
  scoreDrafts[previousScaleId] = { ...scores };
  for (const key of Object.keys(scores)) delete scores[key];
  Object.assign(scores, scoreDrafts[nextScaleId] || {});
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
  scaleSwitchNotice.value = "已切换测评量表；各量表的分数草稿分别保存，请核对当前项目后再提交。";
});

function clearFieldError(key) {
  delete fieldErrors[key];
  submitErr.value = "";
}

async function focusFirstInvalid(key) {
  await nextTick();
  const input = document.getElementById(`score-${key}`);
  input?.scrollIntoView({ behavior: "smooth", block: "center" });
  input?.focus({ preventScroll: true });
}

async function load() {
  loading.value = true;
  loadErr.value = "";
  try {
    const [status, catalog] = await Promise.all([
      api.get("/onboarding/status", { params: { user_id: user.id } }), api.get("/fitness/scales"),
    ]);
    done.value = status.data.onboarding_done;
    baseline.value = status.data.baseline;
    scales.value = catalog.data;
    setUser({ ...getUser(), onboarding_done: done.value, privacy_consent: status.data.privacy_consent });
    ready.value = true;
  } catch (error) {
    loadErr.value = errorMessage(error, "无法读取测评状态，请确认后端已启动后重新加载。");
  } finally { loading.value = false; }
}

async function submit() {
  submitErr.value = "";
  consentErr.value = "";
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
  const payload = {};
  let firstInvalidKey = "";
  for (const item of current.value?.items || []) {
    const value = scores[item.key];
    const limit = maxScore(item);
    if (value === "" || value == null) {
      fieldErrors[item.key] = `请填写「${item.name}」的体测换算分，不能留空。`;
    } else if (!Number.isFinite(Number(value))) {
      fieldErrors[item.key] = `「${item.name}」请输入有效数字，可填小数。`;
    } else if (Number(value) < 0 || Number(value) > limit) {
      fieldErrors[item.key] = `「${item.name}」须在 0–${limit} 分之间，包含 0 分和 ${limit} 分。`;
    } else {
      payload[item.key] = Number(value);
    }
    if (fieldErrors[item.key]) {
      if (!firstInvalidKey) firstInvalidKey = item.key;
    }
  }
  if (firstInvalidKey) {
    await focusFirstInvalid(firstInvalidKey);
    return;
  }
  if (!current.value) return;
  if (!consent.value) {
    consentErr.value = "请先同意资料使用与运动健康免责声明后再提交。";
    await nextTick();
    document.getElementById("onboarding-consent")?.focus();
    return;
  }
  busy.value = true;
  try {
    const { data } = await api.post("/onboarding/complete", {
      ...form, user_id: user.id, scale_id: current.value.id, scores: payload,
      chronic_tags: tags.value.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean),
      privacy_consent: true, generate_prescription: true,
    });
    setUser(data.user);
    await router.push("/prescription");
  } catch (error) { submitErr.value = errorMessage(error, "保存失败，请检查资料和分数后重试。"); }
  finally { busy.value = false; }
}
onMounted(load);
</script>

<style scoped>
.score-help { margin: 12px 0; }
.score-help summary { cursor: pointer; padding: 8px 0; }
.score-list { display: grid; gap: 12px; margin: 16px 0; }
.score-field { display: grid; grid-template-columns: minmax(0, 1fr) minmax(150px, 240px); align-items: center; gap: 6px 16px; }
.score-field input { width: 100%; }
.field-help, .field-error { grid-column: 1 / -1; margin: 0; }
.field-error { color: var(--bad); }
.score-field.has-error input { border-color: var(--bad); }
@media (max-width: 600px) {
  .score-field { grid-template-columns: minmax(0, 1fr); gap: 6px; }
  .field-help, .field-error { grid-column: auto; }
}
</style>
