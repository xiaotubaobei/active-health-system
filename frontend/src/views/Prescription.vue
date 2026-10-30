<template>
  <div class="card">
    <h2>运动处方</h2>
    <div class="row">
      <button @click="generate">生成/更新处方</button>
      <button class="secondary" @click="load">刷新</button>
      <button class="secondary" v-if="current" @click="advance">推进状态</button>
    </div>
    <div class="steps">
      <span v-for="s in flow" :key="s" :class="{ on: current?.status === s }">{{ label(s) }}</span>
    </div>
    <div v-if="current">
      <p>
        版本 <b>v{{ current.version }}</b>
        <span class="tag">{{ label(current.status) }}</span>
        <span class="tag gray">{{ current.library === "medical" ? "医疗处方" : "健身处方" }}</span>
      </p>
      <div class="row">
        <div class="stat"><span>方式</span><b style="font-size:16px">{{ current.mode }}</b></div>
        <div class="stat"><span>强度</span><b style="font-size:16px">{{ current.intensity }}</b></div>
        <div class="stat"><span>频次</span><b style="font-size:16px">{{ current.frequency }}</b></div>
        <div class="stat"><span>时长</span><b style="font-size:16px">{{ current.duration }}</b></div>
        <div class="stat"><span>周期</span><b style="font-size:16px">{{ current.cycle }}</b></div>
      </div>
      <h3>动作安排</h3>
      <ul class="ex-list">
        <li v-for="e in current.exercises || []" :key="e.id + e.name">
          <span>{{ e.name }} <span class="tag gray">{{ e.category || "训练" }}</span></span>
          <span>{{ e.sets }}组 × {{ e.reps }}{{ e.unit || "次" }}</span>
        </li>
      </ul>
      <h3>综合健康计划（医师占位）</h3>
      <p>
        饮食 <span class="tag">{{ current.health_plan?.diet || "—" }}</span>
        睡眠 <span class="tag">{{ current.health_plan?.sleep || "—" }}</span>
        用药 <span class="tag gray">{{ current.health_plan?.medication || "无" }}</span>
        心理 <span class="tag gray">{{ current.health_plan?.psychology || "无" }}</span>
      </p>
      <p class="muted">{{ current.notes }}</p>
    </div>
    <p v-else class="muted">尚未生成处方，可点上方按钮，或回总览使用一键演示。</p>
  </div>
  <div class="card">
    <h3>处方模板库（申请书表10/11骨架）</h3>
    <div class="tpl-grid" v-if="templates">
      <div class="tpl" v-for="t in allTemplates" :key="t.id">
        <b>{{ t.name }}</b>
        <p class="muted">{{ t.mode }} · {{ t.intensity }} · {{ t.frequency }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import api, { getUser } from "../api/client";

const LABELS = {
  clinical_intake: "临床/病史",
  fitness_assessed: "体适能评估",
  pre_prescription: "预处方",
  monitoring: "监测预效果",
  formal_prescription: "正式处方",
  implementing: "实施中",
  feedback: "监督反馈",
};
const flow = [
  "clinical_intake",
  "fitness_assessed",
  "pre_prescription",
  "monitoring",
  "formal_prescription",
  "implementing",
  "feedback",
];
const user = getUser();
const current = ref(null);
const templates = ref(null);
const allTemplates = computed(() => [
  ...(templates.value?.fitness?.templates || []),
  ...(templates.value?.medical?.templates || []),
]);

function label(s) {
  return LABELS[s] || s;
}

async function load() {
  try {
    current.value = (await api.get(`/prescriptions/current?user_id=${user.id}`)).data;
  } catch {
    current.value = null;
  }
}
async function generate() {
  current.value = (await api.post("/prescriptions/generate", { user_id: user.id })).data;
}
async function advance() {
  current.value = (await api.post(`/prescriptions/${current.value.id}/advance`)).data;
}
onMounted(async () => {
  templates.value = (await api.get("/prescriptions/templates")).data;
  await load();
});
</script>
