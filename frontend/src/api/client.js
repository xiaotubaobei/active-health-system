import axios from "axios";
import { loginDestination } from "../utils/authNavigation";

const configuredBaseURL = String(import.meta.env.VITE_API_BASE_URL || "/api").trim();

const api = axios.create({
  baseURL: configuredBaseURL.replace(/\/+$/, "") || "/api",
  timeout: 30000,
  withCredentials: true,
  headers: { "X-Requested-With": "ActiveHealth" },
});

api.interceptors.response.use(response => response, error => {
  if (error?.response?.status === 401 && !error.config?.skipAuthRedirect && !["/auth/login", "/auth/register"].includes(error.config?.url)) {
    const destination = loginDestination(window.location.pathname + window.location.search + window.location.hash, !!getUser());
    clearUser();
    if (window.location.pathname !== "/login") window.location.replace(`/login?${new URLSearchParams(destination.query)}`);
  }
  return Promise.reject(error);
});

export function getUser() {
  const raw = localStorage.getItem("ah_user");
  try {
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setUser(user) {
  if (getUser()?.id !== user.id) localStorage.removeItem("ah_last_session");
  localStorage.setItem("ah_user", JSON.stringify(user));
}

export function clearUser() {
  localStorage.removeItem("ah_user");
  localStorage.removeItem("ah_last_session");
}

export function errorMessage(error, fallback = "操作失败，请稍后重试") {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    const names = { height_cm: "身高", weight_kg: "体重", waist_cm: "腰围", hip_cm: "臀围", age_group: "年龄组", goal: "运动目标", body_fat: "体脂率" };
    const fields = [...new Set(detail.map(item => names[item.loc?.at(-1)]).filter(Boolean))];
    return fields.length ? `请检查${fields.join("、")}：填写有效数值或选项后重试。` : fallback;
  }
  return typeof detail === "string" ? detail : fallback;
}

export default api;
