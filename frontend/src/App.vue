<template>
  <div v-if="isLogin" class="main" style="max-width:480px;margin:10vh auto">
    <router-view />
  </div>
  <div v-else class="layout">
    <aside class="side">
      <h1>主动健康智能服务系统</h1>
      <p>初版演示 · 申请书图14全周期</p>
      <button class="nav-toggle secondary" :aria-expanded="menuOpen" aria-controls="main-nav" @click="menuOpen = !menuOpen">{{ menuOpen ? "收起导航" : "展开导航" }}</button>
      <nav id="main-nav" :class="{ open: menuOpen }" aria-label="主导航" @click="menuOpen = false">
      <router-link to="/">总览</router-link>
      <router-link to="/profile">用户档案</router-link>
      <router-link to="/onboarding">首次测评</router-link>
      <router-link to="/fitness">体适能评估</router-link>
      <router-link to="/body">体型解析</router-link>
      <router-link to="/prescription">运动处方</router-link>
      <router-link to="/exercise">运动中监测</router-link>
      <router-link to="/report">运动后报告/CoT</router-link>
      <router-link to="/history">训练历史与知识库</router-link>
      <router-link to="/admin">管理端</router-link>
      <button class="secondary" style="margin-top:20px;width:100%" @click="logout">退出</button>
      <p v-if="logoutError" role="alert">{{ logoutError }}</p>
      </nav>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import api, { clearUser, errorMessage } from "./api/client";

const route = useRoute();
const menuOpen = ref(false);
const logoutError = ref("");
const router = useRouter();
const isLogin = computed(() => route.path === "/login");

async function logout() {
  logoutError.value = "";
  try {
    await api.post("/auth/logout");
    clearUser();
    await router.push("/login");
  } catch (error) {
    if (error?.response?.status !== 401) logoutError.value = errorMessage(error, "退出失败，请检查连接后重试");
  }
}
</script>
