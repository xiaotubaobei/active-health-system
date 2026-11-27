<template>
  <div class="card">
    <h2>体适能评估</h2>
    <p class="muted">此处录入已有体测的 0–100 换算分，再按项目权重汇总。当前尚未提供原始成绩换算标准；没有已换算成绩时请勿估填，也不要填写次数、秒数或体重。</p>
    <p v-if="loading" role="status">正在读取评估项目…</p>
    <p v-if="loadErr" class="err" role="alert">{{ loadErr }}</p>
    <button v-if="loadErr" class="secondary" :disabled="loading" @click="loadScales">重新加载评估项目</button>
    <form @submit.prevent="submit">
    <div class="row">
      <select v-model="scaleId" aria-label="评估项目组" :disabled="busy || loading">
        <option v-for="s in applicableScales" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <button type="submit" :disabled="busy || loading || !current">{{ busy ? '正在保存…' : '提交分数' }}</button>
    </div>
    <div v-if="current" style="margin-top:12px">
      <div v-for="item in current.items" :key="item.key" class="row" style="margin:8px 0">
        <label :for="`fitness-${item.key}`" style="width:200px">{{ item.name }}</label>
        <input
          :id="`fitness-${item.key}`"
          :aria-invalid="invalidKey === item.key ? 'true' : undefined"
          :aria-describedby="invalidKey === item.key ? 'fitness-error' : undefined"
          @input="invalidKey = ''; formErr = ''; result = null"
          type="number"
          v-model.number="scores[item.key]"
          min="0"
          max="100"
          step="0.1"
          :disabled="busy"
          :placeholder="'0-100，权重 ' + item.weight"
        />
        <span class="muted">权重 {{ item.weight }}</span>
      </div>
    </div>
    <p v-if="formErr" id="fitness-error" class="err" role="alert">{{ formErr }}</p>
    </form>
    <div v-if="result" class="row" style="margin-top:16px">
      <div class="stat"><span>录入分数汇总（试验）</span><b>{{ result.total_score }}</b></div>
      <div class="stat"><span>项目组</span><b style="font-size:14px">{{ scales.find(s => s.id === result.scale_id)?.name || '未识别项目组' }}</b></div>
    </div>
    <p v-if="result" class="muted">已保存本次录入。这是分数的加权汇总，评分标准与分档阈值尚未核验，不能据此判断是否达标、诊断身体问题或增加运动量。当前模板计划不会根据本次分数自动调整。</p>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import api, { errorMessage, getUser } from "../api/client";

const user = getUser();
const scales = ref([]);
const scaleId = ref("");
const scores = reactive({});
const result = ref(null);
const formErr = ref("");
const busy = ref(false);
const loading = ref(false);
const loadErr = ref("");
const invalidKey = ref("");

const current = computed(() => scales.value.find((s) => s.id === scaleId.value));
const applicableScales = computed(() => scales.value.filter((s) => s.id === (user.age_group === 'youth' ? 'youth' : 'middle_elder')));

watch(current, (s) => {
  result.value = null;
  if (!s) return;
  for (const key of Object.keys(scores)) delete scores[key];
});

async function loadScales() {
  if (loading.value) return;
  loading.value = true;
  loadErr.value = "";
  try {
    const { data } = await api.get("/fitness/scales");
    if (!Array.isArray(data)) throw new Error("Invalid scale catalog");
    scales.value = data;
    scaleId.value = data.find((s) => s.id === (user.age_group === "youth" ? "youth" : "middle_elder"))?.id || "";
    if (!scaleId.value) loadErr.value = "未找到当前年龄组的评估项目，请重新加载。";
  } catch (error) { loadErr.value = errorMessage(error, "评估项目加载失败，请检查网络后重试。"); }
  finally { loading.value = false; }
}
onMounted(loadScales);

async function submit() {
  if (busy.value || loading.value || !current.value) return;
  formErr.value = "";
  invalidKey.value = "";
  result.value = null;
  const items = current.value?.items || [];
  const payload = {};
  for (const item of items) {
    const v = scores[item.key];
    if (v === undefined || v === null || v === "" || !Number.isFinite(Number(v)) || v < 0 || v > 100) {
      formErr.value = `请填写「${item.name}」的有效分数（0–100）`;
      invalidKey.value = item.key;
      await nextTick();
      document.getElementById(`fitness-${item.key}`)?.focus();
      return;
    }
    payload[item.key] = Number(v);
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
</script>
