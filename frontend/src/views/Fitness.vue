<template>
  <div class="card">
    <h2>体适能评估</h2>
    <p class="muted">请按体测结果填写 0–100 分（不再使用默认分）。提交后按申请书量表权重计算总分。</p>
    <div class="row">
      <select v-model="scaleId">
        <option v-for="s in scales" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <button @click="submit" :disabled="busy">提交评估</button>
    </div>
    <div v-if="current" style="margin-top:12px">
      <div v-for="item in current.items" :key="item.key" class="row" style="margin:8px 0">
        <span style="width:200px">{{ item.name }}</span>
        <input
          type="number"
          v-model.number="scores[item.key]"
          min="0"
          max="100"
          :placeholder="'0-100，权重 ' + item.weight"
        />
        <span class="muted">权重 {{ item.weight }}</span>
      </div>
    </div>
    <p v-if="formErr" class="err">{{ formErr }}</p>
    <div v-if="result" class="row" style="margin-top:16px">
      <div class="stat"><span>总分</span><b>{{ result.total_score }}</b></div>
      <div class="stat"><span>等级</span><b>{{ levelText(result.level) }}</b></div>
      <div class="stat"><span>量表</span><b style="font-size:14px">{{ result.scale_id }}</b></div>
    </div>
    <p v-if="result" class="ok">{{ advice }}</p>
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
const advice = computed(() => {
  const lv = result.value?.level;
  if (lv === "excellent") return "体适能较好，可按处方保持并逐步进阶。";
  if (lv === "good") return "整体达标，建议按处方完成，关注柔韧与平衡短板。";
  if (lv === "average") return "中等水平，建议结合实际情况向专业人员咨询运动强度。";
  if (lv === "poor") return "基础较弱，建议医疗/医师审核后再加大运动量。";
  return "";
});

watch(current, (s) => {
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

function levelText(lv) {
  return { excellent: "优秀", good: "良好", average: "一般", poor: "较弱" }[lv] || lv;
}

async function submit() {
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
