<template>
  <div class="card">
    <h2>体型记录</h2>
    <p class="muted">BMI 根据档案中的身高、体重计算；腰臀比根据下方围度计算。请填写实际测量值，单位为厘米。</p>
    <form class="row" @submit.prevent="run" novalidate>
      <label>腰围（厘米） <input type="number" min="0.1" max="300" step="any" v-model.number="waist" :disabled="busy" required /></label>
      <label>臀围（厘米） <input type="number" min="0.1" max="300" step="any" v-model.number="hip" :disabled="busy" required /></label>
      <button :disabled="busy">{{ busy ? '正在保存…' : '保存体型记录' }}</button>
    </form>
    <p v-if="err" class="err" role="alert">{{ err }}</p>
    <div v-if="current" class="row" style="margin-top:12px">
      <div class="stat"><span>BMI</span><b>{{ current.bmi }}</b></div>
      <div class="stat"><span>腰臀比</span><b>{{ current.whr }}</b></div>
    </div>
    <p v-if="msg" class="ok" role="status">{{ msg }}</p>
    <details style="margin-top:16px">
      <summary>实验功能：人体部位解析演示</summary>
      <p class="muted">此处使用模拟点击与示例部位，尚未提供真实图片识别，不能作为体型分析结果。</p>
      <div class="row">
        <button type="button" class="secondary" :disabled="busy" @click="addClick(true)">模拟选中部位</button>
        <button type="button" class="secondary" :disabled="busy" @click="addClick(false)">模拟排除部位</button>
      </div>
      <p>已记录 {{ clicks.length }} 次模拟点击；下次保存时一并提交。</p>
      <p v-if="parts.length">示例部位（演示数据）：{{ parts.join("、") }}</p>
    </details>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import api, { errorMessage, getUser } from "../api/client";

const user = getUser();
const waist = ref("");
const hip = ref("");
const clicks = ref([]);
const current = ref(null);
const msg = ref("");
const err = ref("");
const busy = ref(false);
const parts = computed(() => current.value?.parsing_result?.parts || []);

function addClick(pos) {
  clicks.value.push({
    x: Math.round(Math.random() * 100) / 100,
    y: Math.round(Math.random() * 100) / 100,
    label: pos ? "pos" : "neg",
  });
}

async function run() {
  if (busy.value) return;
  msg.value = "";
  err.value = "";
  current.value = null;
  if (![waist.value, hip.value].every(value => typeof value === 'number' && Number.isFinite(value) && value > 0 && value <= 300)) {
    err.value = "腰围、臀围请填写大于0且不超过300的数值，单位为厘米。";
    return;
  }
  busy.value = true;
  try {
    const { data } = await api.post("/body/parse", {
      user_id: user.id, clicks: clicks.value, waist_cm: waist.value, hip_cm: hip.value,
    });
    current.value = data.current;
    msg.value = "体型记录已保存。BMI 和腰臀比是计算值，不能代替专业评估。";
  } catch (error) { err.value = errorMessage(error, "保存失败，请检查网络后重试。"); }
  finally { busy.value = false; }
}
</script>
