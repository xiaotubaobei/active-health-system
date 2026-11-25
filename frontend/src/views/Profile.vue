<template>
  <div class="card">
    <h2>用户档案</h2>
    <div class="row">
      <label>年龄段
        <select v-model="form.age_group">
          <option value="youth">青少年</option>
          <option value="middle_age">中年</option>
          <option value="elder">老年</option>
        </select>
      </label>
      <label>身高（厘米） <input type="number" min="0.1" max="300" step="0.1" v-model.number="form.height_cm" /></label>
      <label>体重（公斤） <input type="number" min="0.1" max="700" step="0.1" v-model.number="form.weight_kg" /></label>
      <label>目标
        <select v-model="form.goal">
          <option value="fitness">健身</option>
          <option value="medical">健康管理（需专业人员审核）</option>
        </select>
      </label>
      <label>慢性病标签（逗号分隔）
        <input v-model="chronicText" placeholder="cardio_risk,joint" />
      </label>
      <button @click="save" :disabled="busy">{{ busy ? "保存中…" : "保存" }}</button>
    </div>
    <p class="muted">请按本人实际情况填写。更新档案不会自动修改已生成的计划或历史测量记录。当前计划仍按年龄组和标签匹配模板，尚未结合身高体重、测评和训练反馈制定个人运动量。</p>
    <p v-if="msg" class="ok">{{ msg }}</p>
    <p v-if="err" class="err">{{ err }}</p>
  </div>
  <AccountSecurity />
</template>

<script setup>
import { reactive, ref } from "vue";
import AccountSecurity from "../components/AccountSecurity.vue";
import api, { errorMessage, getUser, setUser } from "../api/client";

const user = getUser();
const form = reactive({
  age_group: user?.age_group || "middle_age",
  height_cm: user?.height_cm ?? "",
  weight_kg: user?.weight_kg ?? "",
  goal: user?.goal || "fitness",
});
const chronicText = ref((user?.chronic_tags || []).join(","));
const msg = ref("");
const err = ref("");
const busy = ref(false);

async function save() {
  if (busy.value) return;
  msg.value = "";
  err.value = "";
  busy.value = true;
  try {
    const { data } = await api.put(`/users/me?user_id=${user.id}`, {
      ...form,
      chronic_tags: chronicText.value
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean),
    });
    setUser({ ...user, ...data });
    msg.value = "档案已保存。已有计划和历史记录未重新计算。";
  } catch (e) {
    err.value = errorMessage(e, "保存失败，请检查连接后重试");
  } finally {
    busy.value = false;
  }
}
</script>
