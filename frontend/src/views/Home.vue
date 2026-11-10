<template>
  <div class="card">
    <h2>系统总览</h2>
    <p>
      对齐申请书图14：运动前 → 运动中 → 运动后闭环。当前用户
      <span class="tag">{{ user?.username }}</span>
      <span class="tag gray">{{ roleName }}</span>
    </p>
    <div class="steps">
      <span>1 档案/体适能</span>
      <span>2 个性化处方</span>
      <span>3 体型/手环</span>
      <span>4 离线/摄像头+姿态</span>
      <span>5 报告归档与历史记录</span>
    </div>
    <div class="row">
      <button @click="runDemo" :disabled="busy">{{ busy ? "演示生成中…" : "一键跑通演示闭环" }}</button>
      <router-link to="/history"><button class="secondary">查看训练历史</button></router-link>
      <router-link to="/fitness"><button class="secondary">从体适能开始</button></router-link>
      <router-link to="/exercise"><button class="secondary">离线 / 摄像头运动页</button></router-link>
    </div>
    <p v-if="msg" class="ok">{{ msg }}</p>
    <p v-if="err" class="err">{{ err }}</p>
    <p class="muted">
      一键演示生成样例报告并归档，不计入成绩、不自动调整处方；展示主线建议：<strong>运动页 → 离线视频 → RepCount 深蹲 → 播放看骨架 → 开会话出报告</strong>
      （姿态推理需启动 RTMPose 服务；CoT 文字仍为演示数据）。清单见 <code>docs/demo_1h_checklist.md</code>。
    </p>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import api, { getUser } from "../api/client";

const user = getUser();
const router = useRouter();
const busy = ref(false);
const msg = ref("");
const err = ref("");
const roleName = computed(() => ({
  user: "普通用户",
  prescription_specialist: "运动处方师",
  physician: "医师",
  admin: "管理员",
}[user?.role] || user?.role));

async function runDemo() {
  busy.value = true;
  msg.value = "";
  err.value = "";
  try {
    const { data } = await api.post("/demo/run-loop", {
      user_id: user.id,
      exercise_id: "squat",
      exercise_name: "深蹲",
    });
    localStorage.setItem("ah_last_session", String(data.session_id));
    msg.value = data.message;
    router.push("/report");
  } catch (e) {
    err.value = e?.response?.data?.detail || "演示失败，请确认后端与 AI 桩已启动";
  } finally {
    busy.value = false;
  }
}
</script>
