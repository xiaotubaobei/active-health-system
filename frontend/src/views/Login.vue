<template>
  <div class="card login-card">
    <header class="login-header">
      <p class="eyebrow">个人运动与健康管理</p>
      <h1>{{ registering ? "创建你的训练档案" : "欢迎回来" }}</h1>
      <p class="login-subtitle">
        {{ registering
          ? "注册后填写基础档案；体测可在准备好换算分后补充。"
          : "登录后查看训练计划、继续训练并回顾训练记录。" }}
      </p>
    </header>

    <div class="mode-switch" aria-label="账号入口">
      <button
        type="button"
        class="mode-button"
        :class="{ active: !registering }"
        :aria-pressed="!registering"
        :disabled="busy"
        @click="setMode(false)"
      >
        登录
      </button>
      <button
        type="button"
        class="mode-button"
        :class="{ active: registering }"
        :aria-pressed="registering"
        :disabled="busy"
        @click="setMode(true)"
      >
        注册新账号
      </button>
    </div>

    <p v-if="route.query.expired" class="form-notice" role="alert">
      登录状态已过期，请重新登录。
    </p>
    <p v-if="route.query.unavailable" class="form-notice error-notice" role="alert">
      暂时无法连接系统，请稍后重试。
    </p>

    <form class="login-form" :aria-busy="busy" @submit.prevent="submit">
      <label class="field-label" for="login-username">用户名</label>
      <input
        id="login-username"
        v-model="username"
        class="field-input"
        name="username"
        autocomplete="username"
        minlength="2"
        maxlength="64"
        required
        :disabled="busy"
      />

      <label class="field-label" for="login-password">密码</label>
      <input
        id="login-password"
        v-model="password"
        class="field-input"
        name="password"
        type="password"
        :minlength="registering ? 8 : 1"
        maxlength="128"
        :autocomplete="registering ? 'new-password' : 'current-password'"
        :aria-describedby="registering ? 'password-hint' : undefined"
        required
        :disabled="busy"
      />
      <p v-if="registering" id="password-hint" class="field-hint">密码长度为 8–128 个字符。</p>

      <div v-if="registering" class="consent-box">
        <label class="consent-label" for="privacy-consent">
          <input
            id="privacy-consent"
            v-model="consent"
            type="checkbox"
            required
            :disabled="busy"
            @invalid="onConsentInvalid"
            @change="clearConsentValidity"
          />
          <span>我同意将资料与训练记录用于本系统个人档案，并知悉运动健康建议不构成医疗诊断或治疗。</span>
        </label>
      </div>

      <p v-if="err" class="form-error" role="alert" aria-live="assertive">{{ err }}</p>

      <button class="submit-button" type="submit" :disabled="busy">
        {{ busy
          ? (registering ? "正在注册…" : "正在登录…")
          : (registering ? "注册并开始" : "进入我的训练") }}
      </button>
    </form>

    <details v-if="!registering" class="demo-account">
      <summary>体验账号</summary>
      <div class="demo-content">
        <p>仅在本地演示环境启用时可用，不会自动填入或登录。</p>
        <p><span>账号：demo</span><span>密码：123456</span></p>
      </div>
    </details>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import api, { setUser } from "../api/client";
import { safeReturnPath } from "../utils/authNavigation.js";

const router = useRouter();
const route = useRoute();
const username = ref("");
const password = ref("");
const registering = ref(false);
const consent = ref(false);
const busy = ref(false);
const err = ref("");

function setMode(nextRegistering) {
  if (busy.value || registering.value === nextRegistering) return;
  registering.value = nextRegistering;
  password.value = "";
  consent.value = false;
  err.value = "";
}

function onConsentInvalid(event) {
  event.target.setCustomValidity("请阅读并勾选隐私同意后再注册。");
}

function clearConsentValidity(event) {
  event.target.setCustomValidity("");
  if (consent.value && err.value.includes("隐私")) err.value = "";
}

function registrationValidationMessage(detail) {
  if (Array.isArray(detail)) {
    const fields = detail.map((item) => item?.loc?.at?.(-1));
    if (fields.includes("username")) return "用户名需为 2–64 个字符。";
    if (fields.includes("password")) return "密码需为 8–128 个字符。";
    if (fields.includes("privacy_consent")) return "请阅读并勾选隐私同意后再注册。";
    return "注册信息不符合要求，请检查后重试。";
  }
  if (typeof detail !== "string") return "操作没有完成，请稍后重试。";
  if (detail.includes("隐私") || detail.includes("同意")) {
    return "请阅读并勾选隐私同意后再注册。";
  }
  if (detail.includes("用户名已存在") || detail.includes("保留名称")) {
    return "这个用户名暂时无法使用，请更换后重试。";
  }
  if (detail.includes("用户名")) return "用户名需为 2–64 个字符。";
  if (detail.includes("密码")) return "密码需为 8–128 个字符。";
  return "注册信息不符合要求，请检查后重试。";
}

function userErrorMessage(error) {
  const status = error?.response?.status;
  if (status === 429) return "尝试次数较多，请稍后再试。";
  if (error?.code === "ECONNABORTED" || /timeout/i.test(error?.message || "") || [408, 504].includes(status)) {
    return "连接时间过长，请稍后重试。";
  }
  if (!error?.response || status >= 500) {
    return "暂时无法连接系统，请稍后重试。";
  }
  if (!registering.value && status === 401) {
    return "用户名或密码不正确，请重新输入。";
  }
  if (registering.value && [400, 409, 422].includes(status)) {
    return registrationValidationMessage(error.response.data?.detail);
  }
  return "操作没有完成，请稍后重试。";
}

async function submit() {
  if (busy.value) return;
  err.value = "";
  if (registering.value && !consent.value) {
    err.value = "请阅读并勾选隐私同意后再注册。";
    return;
  }
  busy.value = true;
  try {
    const { data } = await api.post(registering.value ? "/auth/register" : "/auth/login", {
      username: username.value.trim(),
      password: password.value,
      ...(registering.value ? { privacy_consent: consent.value } : {}),
    });
    setUser(data.user);
    const reviewer = ["physician", "prescription_specialist"].includes(data.user.role);
    const next = safeReturnPath(route.query.next);
    await router.push(reviewer ? (next === "/" ? "/reviews" : next) : data.user.onboarding_done ? next : "/onboarding");
  } catch (error) {
    err.value = userErrorMessage(error);
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.login-card {
  box-sizing: border-box;
  width: 100%;
  max-width: 460px;
  margin: 0 auto;
  padding: 34px;
}

.login-header { text-align: center; }
.eyebrow {
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 0.88rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.login-header h1 { margin: 0; font-size: 1.8rem; line-height: 1.25; }
.login-subtitle {
  margin: 12px auto 0;
  max-width: 390px;
  color: var(--muted);
  line-height: 1.7;
}
.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin: 26px 0 20px;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.035);
}
.mode-button {
  border-color: transparent;
  background: transparent;
  color: var(--muted);
  font-weight: 600;
}
.mode-button.active { background: var(--accent); color: #fff; }
.mode-button:focus-visible,
.submit-button:focus-visible,
.demo-account summary:focus-visible,
.field-input:focus-visible,
.consent-label input:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--accent) 38%, transparent);
  outline-offset: 2px;
}
.form-notice,
.form-error {
  padding: 10px 12px;
  border-radius: 8px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.form-notice {
  margin: 0 0 16px;
  border: 1px solid color-mix(in srgb, var(--warn) 45%, transparent);
  background: color-mix(in srgb, var(--warn) 10%, transparent);
  color: var(--warn);
}
.error-notice,
.form-error {
  border: 1px solid color-mix(in srgb, var(--bad) 42%, transparent);
  background: color-mix(in srgb, var(--bad) 9%, transparent);
  color: var(--bad);
}
.login-form { display: flex; flex-direction: column; }
.field-label { margin: 0 0 7px; font-weight: 650; }
.field-label:not(:first-child) { margin-top: 17px; }
.field-input {
  box-sizing: border-box;
  width: 100%;
  min-height: 44px;
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
}
.field-input:disabled { opacity: 0.65; }
.field-hint { margin: 7px 0 0; color: var(--muted); font-size: 0.88rem; }
.consent-box {
  margin-top: 20px;
  padding: 13px 14px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.025);
}
.consent-label {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: 0.92rem;
  line-height: 1.65;
}
.consent-label input { flex: 0 0 auto; margin-top: 5px; }
.form-error { margin: 16px 0 0; }
.submit-button {
  width: 100%;
  min-height: 46px;
  margin-top: 20px;
  font-weight: 700;
}
.demo-account {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.9rem;
}
.demo-account summary { width: fit-content; cursor: pointer; font-weight: 600; }
.demo-content {
  margin-top: 10px;
  padding: 11px 13px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.025);
  line-height: 1.6;
}
.demo-content p { margin: 0; }
.demo-content p + p { display: flex; gap: 18px; margin-top: 6px; }
</style>
