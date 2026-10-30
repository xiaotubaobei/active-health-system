<template>
  <div class="card">
    <h2>体型 / 人体解析</h2>
    <p class="muted">运动前体型评估：BMI、腰臀比 + 开集解析桩（点击交互占位）。</p>
    <div class="row">
      <label>腰围(cm) <input type="number" v-model.number="waist" /></label>
      <label>臀围(cm) <input type="number" v-model.number="hip" /></label>
      <button class="secondary" @click="addClick(true)">正点击</button>
      <button class="secondary" @click="addClick(false)">负点击</button>
      <button @click="run">开始解析</button>
    </div>
    <p class="muted">已记录交互点击 {{ clicks.length }} 次（框架阶段用随机坐标模拟）</p>
    <div v-if="current" class="row" style="margin-top:12px">
      <div class="stat"><span>BMI</span><b>{{ current.bmi }}</b></div>
      <div class="stat"><span>腰臀比</span><b>{{ current.whr }}</b></div>
      <div class="stat"><span>体型判断</span><b style="font-size:16px">{{ bmiLabel }}</b></div>
    </div>
    <p v-if="parts.length" class="ok">解析部位：{{ parts.join("、") }}</p>
    <p v-if="msg" class="ok">{{ msg }}</p>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import api, { getUser } from "../api/client";

const user = getUser();
const waist = ref(80);
const hip = ref(95);
const clicks = ref([]);
const current = ref(null);
const msg = ref("");

const bmiLabel = computed(() => {
  const b = current.value?.bmi || 0;
  if (b < 18.5) return "偏瘦";
  if (b < 24) return "正常";
  if (b < 28) return "超重";
  return "肥胖";
});
const parts = computed(() => current.value?.parsing_result?.parts || []);

function addClick(pos) {
  clicks.value.push({
    x: Math.round(Math.random() * 100) / 100,
    y: Math.round(Math.random() * 100) / 100,
    label: pos ? "pos" : "neg",
  });
}

async function run() {
  const { data } = await api.post("/body/parse", {
    user_id: user.id,
    clicks: clicks.value,
    waist_cm: waist.value,
    hip_cm: hip.value,
  });
  current.value = data.current;
  msg.value = "已写入体型档案，可用于后续处方条件。";
}
</script>
