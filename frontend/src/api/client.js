import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
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
  return typeof detail === "string" ? detail : fallback;
}

export default api;
