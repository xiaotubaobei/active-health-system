import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

export function getUser() {
  const raw = localStorage.getItem("ah_user");
  return raw ? JSON.parse(raw) : null;
}

export function setUser(user) {
  localStorage.setItem("ah_user", JSON.stringify(user));
}

export function clearUser() {
  localStorage.removeItem("ah_user");
}

export default api;
