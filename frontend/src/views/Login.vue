<template>
  <div class="card">
    <h2>{{ registering ? "注册个人账号" : "登录" }}</h2>
    <p class="muted">请使用个人账号登录；首次使用可注册。demo / 123456 仅在后端开启本地演示模式时可用。</p>
    <p v-if="route.query.expired" class="muted">登录已失效，请重新登录。</p>
    <p v-if="route.query.unavailable" class="err">暂时无法连接系统，请稍后重试。</p>
    <form @submit.prevent="submit">
      <div class="row" style="margin-top:12px">
        <label>用户名 <input v-model="username" autocomplete="username" minlength="2" maxlength="64" required /></label>
        <label>密码 <input v-model="password" type="password" :minlength="registering ? 8 : 1" maxlength="128" :autocomplete="registering ? 'new-password' : 'current-password'" required /></label>
      </div>
      <p v-if="registering"><label><input v-model="consent" type="checkbox" required /> 我同意将资料与训练记录用于本系统个人档案，并知悉运动健康建议不构成医疗诊断或治疗。</label></p>
      <div class="row" style="margin-top:12px">
        <button type="submit" :disabled="busy">{{ busy ? "正在处理…" : registering ? "注册并开始首次测评" : "进入系统" }}</button>
        <button class="secondary" type="button" :disabled="busy" @click="toggle">{{ registering ? "已有账号，去登录" : "注册新账号" }}</button>
      </div>
    </form>
    <p v-if="err" class="err" role="alert">{{ err }}</p>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import api, { errorMessage, setUser } from "../api/client";

const router = useRouter();
const route = useRoute();
const username = ref("");
const password = ref("");
const registering = ref(false);
const consent = ref(false);
const busy = ref(false);
const err = ref("");
function toggle() {
  registering.value = !registering.value;
  username.value = "";
  password.value = "";
  consent.value = false;
  err.value = "";
}
async function submit() {
  err.value = "";
  busy.value = true;
  try {
    const { data } = await api.post(registering.value ? "/auth/register" : "/auth/login", {
      username: username.value.trim(), password: password.value,
      ...(registering.value ? { privacy_consent: consent.value } : {}),
    });
    setUser(data.user);
    await router.push(data.user.onboarding_done ? "/" : "/onboarding");
  } catch (error) { err.value = errorMessage(error, "操作失败，请确认后端已启动。"); }
  finally { busy.value = false; }
}
</script>
