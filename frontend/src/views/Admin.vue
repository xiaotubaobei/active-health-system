<template>
  <div class="card">
    <h2>管理端</h2>
    <p class="muted">对应申请书图14：服务供给 / 服务管理 / 数据管理占位。处方师改模板，医师写健康计划。</p>
    <div class="row">
      <button @click="loadScales">体适能量表</button>
      <button class="secondary" @click="loadTemplates">处方模板</button>
      <button class="secondary" @click="postBracelet">模拟手环上报</button>
    </div>
    <div v-if="bracelet" class="row" style="margin-top:12px">
      <div class="stat"><span>心率</span><b>{{ bracelet.payload?.hr }}</b></div>
      <div class="stat"><span>步数</span><b>{{ bracelet.payload?.steps }}</b></div>
      <div class="stat"><span>血氧</span><b>{{ bracelet.payload?.spo2 }}</b></div>
    </div>
    <div v-if="scaleNames.length" class="tpl-grid" style="margin-top:12px">
      <div class="tpl" v-for="n in scaleNames" :key="n"><b>{{ n }}</b></div>
    </div>
    <div v-if="tplNames.length" class="tpl-grid" style="margin-top:12px">
      <div class="tpl" v-for="n in tplNames" :key="n"><b>{{ n }}</b></div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import api, { getUser } from "../api/client";

const user = getUser();
const bracelet = ref(null);
const scaleNames = ref([]);
const tplNames = ref([]);

async function loadScales() {
  const data = (await api.get("/fitness/scales")).data;
  scaleNames.value = data.map((s) => s.name);
  tplNames.value = [];
}
async function loadTemplates() {
  const data = (await api.get("/prescriptions/templates")).data;
  tplNames.value = [
    ...(data.fitness?.templates || []).map((t) => "健身 · " + t.name),
    ...(data.medical?.templates || []).map((t) => "医疗 · " + t.name),
  ];
  scaleNames.value = [];
}
async function postBracelet() {
  bracelet.value = (
    await api.post("/devices/readings", {
      user_id: user.id,
      device_type: "bracelet",
      payload: { hr: 78, steps: 3200, spo2: 98 },
    })
  ).data;
}
</script>
