<template>
  <div class="card">
    <h2>体适能评估</h2>
    <p class="muted">此处只录入已有体测的换算分，可填小数；不是原始体重、次数或秒数。当前尚未提供原始成绩换算标准，没有换算分时请勿估填。</p>
    <p v-if="loadingScales && !scalesReady" role="status">正在加载测评量表…</p>
    <p v-if="loadErr" class="err" role="alert">{{ loadErr }}</p>
    <button v-if="loadErr" class="secondary" type="button" @click="loadScales" :disabled="loadingScales">
      {{ loadingScales ? "正在重新加载…" : "重试加载量表" }}
    </button>
    <template v-if="scalesReady">
      <form novalidate @submit.prevent="submit">
        <div class="scale-controls">
          <label for="fitness-scale">测评量表</label>
          <select id="fitness-scale" v-model="scaleId" :disabled="busy || loadingScales">
            <option v-for="s in applicableScales" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
          <button class="secondary" type="button" @click="loadScales" :disabled="busy || loadingScales">
            {{ loadingScales ? "正在加载…" : "重新加载量表" }}
          </button>
        </div>
        <p v-if="scaleSwitchNotice" class="warn" role="status">{{ scaleSwitchNotice }}</p>
        <p class="muted">没有体测换算分时，请先向项目人员确认测量及换算标准后再填写，不要自行估分。</p>
        <div v-if="current" class="score-list">
          <div
            v-for="item in current.items"
            :key="item.key"
            class="score-field"
            :class="{ 'has-error': fieldErrors[item.key] }"
          >
            <label :for="`fitness-${item.key}`">{{ item.name }} · 必填</label>
            <input
              :id="`fitness-${item.key}`"
              v-model.number="scores[item.key]"
              type="number"
              min="0"
              :max="maxScore(item)"
              step="any"
              :disabled="busy"
              :aria-invalid="Boolean(fieldErrors[item.key])"
              :aria-describedby="fieldErrors[item.key] ? `fitness-help-${item.key} fitness-error-${item.key}` : `fitness-help-${item.key}`"
              placeholder="输入换算分"
              @input="clearFieldError(item.key)"
            />
            <p :id="`fitness-help-${item.key}`" class="field-help muted">有效范围：0–{{ maxScore(item) }} 分；量表权重 {{ item.weight }}</p>
            <p v-if="fieldErrors[item.key]" :id="`fitness-error-${item.key}`" class="field-error" role="alert">{{ fieldErrors[item.key] }}</p>
          </div>
        </div>
        <p v-if="formErr" class="err" role="alert">{{ formErr }}</p>
        <button type="submit" :disabled="busy || loadingScales || !current">
          {{ busy ? "正在提交…" : formErr ? "重试提交" : "提交评估" }}
        </button>
      </form>
    </template>
    <div v-if="result" class="row" style="margin-top:16px">
      <div class="stat"><span>录入分数汇总（试验）</span><b>{{ result.total_score }}</b></div>
      <div class="stat"><span>量表</span><b style="font-size:14px">{{ resultScaleName }}</b></div>
    </div>
    <p v-if="result" class="muted">已保存本次录入。这是分数的加权汇总，评分标准与分档阈值尚未核验，不能据此判断是否达标或增加运动量。当前模板计划不会根据本次分数自动调整。</p>
    <router-link v-if="result" to="/prescription"><button type="button">查看训练计划</button></router-link>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import api, { errorMessage, getUser } from "../api/client";
import { validScale, maxScore, scoreError } from "../utils/assessmentScores";

const user = getUser();
const scales = ref([]);
const scaleId = ref("");
const scores = reactive({});
const fieldErrors = reactive({});
const result = ref(null);
const formErr = ref("");
const busy = ref(false);
const loadingScales = ref(false);
const scalesReady = ref(false);
const loadErr = ref("");
const scaleSwitchNotice = ref("");
const invalidKey = computed(() => Object.keys(fieldErrors)[0] || "");
const applicableScales = computed(() => scales.value.filter(s => s.id === (user.age_group === "youth" ? "youth" : "middle_elder")));
const current = computed(() => applicableScales.value.find(s => s.id === scaleId.value));
const resultScaleName = computed(() => scales.value.find(s => s.id === result.value?.scale_id)?.name || "体适能评测");

watch(scaleId, () => {
  for (const key of Object.keys(scores)) delete scores[key];
  clearErrors();
  result.value = null;
});
function clearErrors() {
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
  formErr.value = "";
}
function clearFieldError(key) {
  delete fieldErrors[key];
  formErr.value = "";
  result.value = null;
}
async function focusFirstInvalid(key) {
  await nextTick();
  const input = document.getElementById(`fitness-${key}`);
  input?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  input?.focus({ preventScroll: true });
}
async function loadScales() {
  if (loadingScales.value || busy.value) return;
  loadingScales.value = true;
  loadErr.value = "";
  try {
    const { data } = await api.get("/fitness/scales");
    const preferredId = user.age_group === "youth" ? "youth" : "middle_elder";
    if (!Array.isArray(data) || !validScale(data.find(s => s?.id === preferredId))) {
      throw new Error("当前年龄组的评估项目不完整");
    }
    const previous = current.value;
    const incoming = data.find(s => s.id === preferredId);
    // Keep drafts on a harmless refresh; do not reuse them if scoring rules changed.
    if (previous && JSON.stringify(previous.items) !== JSON.stringify(incoming.items)) {
      for (const key of Object.keys(scores)) delete scores[key];
      clearErrors();
      result.value = null;
      scaleSwitchNotice.value = "评估项目或规则有更新，请核对后重新填写分数。";
    }
    scales.value = data;
    scaleId.value = preferredId;
    scalesReady.value = true;
  } catch (error) {
    loadErr.value = errorMessage(error, "评估项目加载失败，请重新加载；已填写的分数会保留。");
  } finally { loadingScales.value = false; }
}
async function submit() {
  if (busy.value || loadingScales.value || !current.value || !validScale(current.value)) return;
  clearErrors();
  result.value = null;
  const payload = {};
  for (const item of current.value.items) {
    const message = scoreError(item, scores[item.key]);
    if (message) fieldErrors[item.key] = message;
    else payload[item.key] = Number(scores[item.key]);
  }
  if (invalidKey.value) {
    await focusFirstInvalid(invalidKey.value);
    return;
  }
  busy.value = true;
  try {
    const { data } = await api.post("/fitness/assess", { user_id: user.id, scale_id: scaleId.value, scores: payload });
    result.value = data;
  } catch (error) { formErr.value = errorMessage(error, "提交失败，请重试；已填写的分数会保留。"); }
  finally { busy.value = false; }
}
onMounted(loadScales);
</script>

<style scoped>
.scale-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 12px 0; }
.scale-controls select { min-width: min(100%, 240px); }
.score-list { display: grid; gap: 12px; margin: 16px 0; }
.score-field { display: grid; grid-template-columns: minmax(0, 1fr) minmax(150px, 240px); align-items: center; gap: 6px 16px; }
.score-field input { width: 100%; }
.field-help, .field-error { grid-column: 1 / -1; margin: 0; }
.field-error { color: var(--bad); }
.score-field.has-error input { border-color: var(--bad); }
@media (max-width: 600px) {
  .scale-controls { align-items: stretch; }
  .scale-controls select { flex: 1 1 100%; }
  .score-field { grid-template-columns: minmax(0, 1fr); gap: 6px; }
  .field-help, .field-error { grid-column: auto; }
}
</style>
