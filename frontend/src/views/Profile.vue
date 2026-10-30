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
      <label>身高(cm) <input type="number" v-model.number="form.height_cm" /></label>
      <label>体重(kg) <input type="number" v-model.number="form.weight_kg" /></label>
      <label>目标
        <select v-model="form.goal">
          <option value="fitness">健身</option>
          <option value="medical">医疗</option>
        </select>
      </label>
      <label>慢性病标签（逗号分隔）
        <input v-model="chronicText" placeholder="cardio_risk,joint" />
      </label>
      <button @click="save" :disabled="busy">{{ busy ? "保存中…" : "保存" }}</button>
    </div>
    <p v-if="msg" class="ok">{{ msg }}</p>
    <p v-if="err" class="err">{{ err }}</p>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import api, { getUser, setUser } from "../api/client";

const user = getUser();
const form = reactive({
  age_group: user?.age_group || "middle_age",
  height_cm: user?.height_cm || 170,
  weight_kg: user?.weight_kg || 65,
  goal: user?.goal || "fitness",
});
const chronicText = ref((user?.chronic_tags || []).join(","));
const msg = ref("");
const err = ref("");
const busy = ref(false);

async function save() {
  msg.value = "";
  err.value = "";
  busy.value = true;
  try {
    const { data } = await api.put(`/users/me?user_id=${user.id}`, {
      ...form,
      chronic_tags: chronicText.value
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    });
    setUser({ ...user, ...data });
    msg.value = "档案已保存，可用于体适能与处方生成。";
  } catch (e) {
    err.value = e?.response?.data?.detail || "保存失败";
  } finally {
    busy.value = false;
  }
}
</script>
