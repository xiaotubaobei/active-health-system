<template>
  <div class="card">
    <h2>体适能评估</h2>
    <p class="muted">此处录入已有体测的 0–100 换算分，再按项目权重汇总。当前尚未提供原始成绩换算标准；没有已换算成绩时请勿估填，也不要填写次数、秒数或体重。</p>
    <div class="row">
      <select v-model="scaleId" :disabled="busy">
        <option v-for="s in applicableScales" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <button @click="submit" :disabled="busy || !current">提交分数</button>
    </div>
    <div v-if="current" style="margin-top:12px">
      <div v-for="item in current.items" :key="item.key" class="row" style="margin:8px 0">
        <span style="width:200px">{{ item.name }}</span>
        <input
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
    <p v-if="formErr" class="err">{{ formErr }}</p>
    <div v-if="result" class="row" style="margin-top:16px">
      <div class="stat"><span>录入分数汇总（试验）</span><b>{{ result.total_score }}</b></div>
      <div class="stat"><span>项目组</span><b style="font-size:14px">{{ scales.find(s => s.id === result.scale_id)?.name || '未识别项目组' }}</b></div>
    </div>
    <p v-if="result" class="muted">已保存本次录入。这是分数的加权汇总，评分标准与分档阈值尚未核验，不能据此判断是否达标、诊断身体问题或增加运动量。当前模板计划不会根据本次分数自动调整。</p>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import api, { errorMessage, getUser } from "../api/client";

const user = getUser();
const scales = ref([]);
const scaleId = ref("");
const scores = reactive({});
const result = ref(null);
const formErr = ref("");
const busy = ref(false);

const current = computed(() => scales.value.find((s) => s.id === scaleId.value));
const applicableScales = computed(() => scales.value.filter((s) => s.id === (user.age_group === 'youth' ? 'youth' : 'middle_elder')));

watch(current, (s) => {
  result.value = null;
  if (!s) return;
  for (const key of Object.keys(scores)) delete scores[key];
});

onMounted(async () => {
  try {
    const { data } = await api.get("/fitness/scales");
    scales.value = data;
    scaleId.value = data.find((s) => s.id === (user.age_group === "youth" ? "youth" : "middle_elder"))?.id || "";
  } catch (error) { formErr.value = errorMessage(error, "量表加载失败，请刷新页面重试。"); }
});

async function submit() {
  if (busy.value || !current.value) return;
  formErr.value = "";
  const items = current.value?.items || [];
  const payload = {};
  for (const item of items) {
    const v = scores[item.key];
    if (v === undefined || v === null || v === "" || !Number.isFinite(Number(v)) || v < 0 || v > 100) {
      formErr.value = `请填写「${item.name}」的有效分数（0–100）`;
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
