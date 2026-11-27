<template>
  <div v-if="isLogin" class="main login-shell">
    <router-view />
  </div>
  <div v-else class="layout">
    <aside class="side">
      <h1>主动健康智能服务系统</h1>
      <p class="side-subtitle">个人运动与健康管理</p>
      <button class="nav-toggle secondary" :aria-expanded="menuOpen" aria-controls="main-nav" @click="menuOpen = !menuOpen">{{ menuOpen ? "收起导航" : "展开导航" }}</button>
      <nav id="main-nav" :class="{ open: menuOpen }" aria-label="功能导航" @click="onNavClick">
        <section class="nav-section" aria-labelledby="primary-nav-title">
          <p id="primary-nav-title" class="nav-label">主要功能</p>
          <router-link to="/" :class="{ 'nav-active': route.path === '/' }">首页</router-link>
          <router-link to="/prescription" :class="{ 'nav-active': route.path === '/prescription' }">训练计划</router-link>
          <router-link to="/exercise" :class="{ 'nav-active': route.path === '/exercise' }">开始训练</router-link>
          <router-link to="/history" :class="{ 'nav-active': route.path === '/history' }">训练记录</router-link>
          <router-link to="/report" :class="{ 'nav-active': route.path === '/report' }">训练报告</router-link>
          <router-link to="/profile" :class="{ 'nav-active': route.path === '/profile' }">个人档案</router-link>
        </section>

        <section class="nav-section secondary-nav" aria-labelledby="secondary-nav-title">
          <p id="secondary-nav-title" class="nav-label">更多功能</p>
          <router-link to="/fitness" :class="{ 'nav-active': route.path === '/fitness' }">体适能评估</router-link>
          <details class="experiment-nav" :open="route.path === '/body'">
            <summary>
              <span>实验功能</span>
              <small>测试中</small>
            </summary>
            <router-link to="/body" :class="{ 'nav-active': route.path === '/body' }">体型分析</router-link>
          </details>
        </section>

        <section v-if="canReview || isAdmin" class="nav-section work-nav" aria-labelledby="work-nav-title">
          <p id="work-nav-title" class="nav-label">工作入口</p>
          <router-link v-if="canReview" to="/reviews" :class="{ 'nav-active': route.path === '/reviews' }">处方审核</router-link>
          <router-link v-if="isAdmin" to="/admin" :class="{ 'nav-active': route.path === '/admin' }">系统管理</router-link>
        </section>
      </nav>

      <div class="side-account">
        <p>{{ user?.username ? `当前账号：${user.username}` : "当前账号" }}</p>
        <button class="secondary" @click="logout">退出登录</button>
        <p v-if="logoutError" class="logout-error" role="alert">{{ logoutError }}</p>
      </div>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import api, { clearUser, errorMessage, getUser } from "./api/client";

const route = useRoute();
const menuOpen = ref(false);
const logoutError = ref("");
const user = ref(getUser());
const router = useRouter();
const isLogin = computed(() => route.path === "/login");
const canReview = computed(() => ["physician", "prescription_specialist"].includes(user.value?.role));
const isAdmin = computed(() => user.value?.role === "admin");

watch(
  () => route.fullPath,
  () => {
    user.value = getUser();
    menuOpen.value = false;
  },
  { immediate: true },
);

function onNavClick(event) {
  if (event.target.closest("a")) menuOpen.value = false;
}

async function logout() {
  logoutError.value = "";
  try {
    await api.post("/auth/logout");
    clearUser();
    user.value = null;
    await router.push("/login");
  } catch (error) {
    if (error?.response?.status !== 401) logoutError.value = errorMessage(error, "退出失败，请检查连接后重试");
  }
}
</script>
