<template>
  <div class="card">
    <h2>登录</h2>
    <p class="muted">演示账号：demo / specialist / physician / admin，密码 123456</p>
    <div class="row" style="margin-top:12px">
      <input v-model="username" placeholder="用户名" />
      <input v-model="password" type="password" placeholder="密码" />
      <button @click="login">进入系统</button>
    </div>
    <p v-if="err" style="color:#b42318">{{ err }}</p>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import api, { setUser } from "../api/client";

const router = useRouter();
const username = ref("demo");
const password = ref("123456");
const err = ref("");

async function login() {
  err.value = "";
  try {
    const { data } = await api.post("/auth/login", {
      username: username.value,
      password: password.value,
    });
    setUser(data.user);
    router.push("/");
  } catch (e) {
    err.value = e?.response?.data?.detail || "登录失败，请确认后端已启动";
  }
}
</script>
