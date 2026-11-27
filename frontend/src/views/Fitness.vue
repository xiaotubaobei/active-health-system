<template>
  <div class="card">
    <h2>体适能评估</h2>
    <p class="muted">请填写各项体测结果换算后的分数，范围为 0–100 分，可填小数；不是原始体重、次数或秒数。提交后按量表权重计算总分。</p>
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
            <option v-for="s in scales" :key="s.id" :value="s.id">{{ s.name }}</option>
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
            <label :for="`fitness-score-${item.key}`">{{ item.name }} · 必填</label>
            <input
              :id="`fitness-score-${item.key}`"
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
      <div class="stat"><span>总分</span><b>{{ result.total_score }}</b></div>
      <div class="stat"><span>等级</span><b>{{ levelText(result.level) }}</b></div>
      <div class="stat"><span>量表</span><b style="font-size:14px">{{ resultScaleName }}</b></div>
    </div>
    <p v-if="result" class="ok">{{ advice }}</p>
    <router-link v-if="result" to="/prescription"><button type="button">查看训练计划</button></router-link>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import api, { errorMessage, getUser } from "../api/client";

const user = getUser();
const scales = ref([]);
const scaleId = ref("");
const scores = reactive({});
const scoreDrafts = reactive({});
const fieldErrors = reactive({});
const result = ref(null);
const formErr = ref("");
const busy = ref(false);
const loadingScales = ref(false);
const scalesReady = ref(false);
const loadErr = ref("");
const scaleSwitchNotice = ref("");

const current = computed(() => scales.value.find((s) => s.id === scaleId.value));
const resultScaleName = computed(() => scales.value.find((s) => s.id === result.value?.scale_id)?.name || "体适能评测");
const maxScore = (item) => item.max_score == null || !Number.isFinite(Number(item.max_score)) ? 100 : Number(item.max_score);
const advice = computed(() => {
  const lv = result.value?.level;
  if (lv === "excellent") return "体适能较好，可按处方保持并逐步进阶。";
  if (lv === "good") return "整体达标，建议按处方完成，关注柔韧与平衡短板。";
  if (lv === "average") return "中等水平，建议结合实际情况向专业人员咨询运动强度。";
  if (lv === "poor") return "基础较弱，建议医疗/医师审核后再加大运动量。";
  return "";
});

watch(scaleId, (nextScaleId, previousScaleId) => {
  if (!previousScaleId || nextScaleId === previousScaleId) return;
  scoreDrafts[previousScaleId] = { ...scores };
  for (const key of Object.keys(scores)) delete scores[key];
  Object.assign(scores, scoreDrafts[nextScaleId] || {});
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
  formErr.value = "";
  result.value = null;
  scaleSwitchNotice.value = "已切换测评量表；各量表的分数草稿分别保存，请核对当前项目后再提交。";
});

function clearFieldError(key) {
  delete fieldErrors[key];
  formErr.value = "";
  result.value = null;
}

async function focusFirstInvalid(key) {
  await nextTick();
  const input = document.getElementById(`fitness-score-${key}`);
  input?.scrollIntoView({ behavior: "smooth", block: "center" });
  input?.focus({ preventScroll: true });
}

async function loadScales() {
  loadingScales.value = true;
  loadErr.value = "";
  try {
    const { data } = await api.get("/fitness/scales");
    if (!Array.isArray(data) || !data.length) throw new Error("测评量表暂不可用，请稍后重试。");
    scales.value = data;
    const preferredId = user.age_group === "youth" ? "youth" : "middle_elder";
    if (!data.some((scale) => scale.id === scaleId.value)) {
      scaleId.value = data.find((scale) => scale.id === preferredId)?.id || data[0].id;
    }
    scalesReady.value = true;
  } catch (error) {
    loadErr.value = errorMessage(error, "量表加载失败，请重试。");
  } finally {
    loadingScales.value = false;
  }
}

function levelText(lv) {
  return { excellent: "优秀", good: "良好", average: "一般", poor: "较弱" }[lv] || "未评级";
}

async function submit() {
  formErr.value = "";
  result.value = null;
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
  const items = current.value?.items || [];
  const payload = {};
  let firstInvalidKey = "";
  for (const item of items) {
    const v = scores[item.key];
    const limit = maxScore(item);
    if (v === undefined || v === null || v === "") {
      fieldErrors[item.key] = `请填写「${item.name}」的体测换算分，不能留空。`;
    } else if (!Number.isFinite(Number(v))) {
      fieldErrors[item.key] = `「${item.name}」请输入有效数字，可填小数。`;
    } else if (Number(v) < 0 || Number(v) > limit) {
      fieldErrors[item.key] = `「${item.name}」须在 0–${limit} 分之间，包含 0 分和 ${limit} 分。`;
    } else {
      payload[item.key] = Number(v);
    }
    if (fieldErrors[item.key]) {
      if (!firstInvalidKey) firstInvalidKey = item.key;
    }
  }
  if (firstInvalidKey) {
    await focusFirstInvalid(firstInvalidKey);
    return;
  }
  busy.value = true;
  try {
    const { data } = await api.post("/fitness/assess", {
      user_id: user.id,
      scale_id: scaleId.value,
      scores: payload,
    });
    result.value = data;
  } catch (e) {
    formErr.value = errorMessage(e, "提交失败");
  } finally {
    busy.value = false;
  }
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
