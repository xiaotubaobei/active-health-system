// Only keep local application destinations; never redirect a login to another site.
export function safeReturnPath(value, fallback = "/") {
  if (typeof value !== "string" || !value.startsWith("/") || /^\/[/\\]/.test(value) || /[\\\s\u0000-\u001f]/.test(value)) return fallback;
  const path = value.split(/[?#]/)[0];
  if (["/login", "/connection"].includes(path)) return fallback;
  return value;
}

export function loginDestination(path, expired = false) {
  return { path: "/login", query: { next: safeReturnPath(path), ...(expired ? { expired: "1" } : {}) } };
}

export function createAuthGuard({ api, getUser, setUser, clearUser }) {
  return async to => {
    if (["/login", "/connection"].includes(to.path)) return true;
    const hadUser = !!getUser();
    try {
      // The guard handles this probe itself, without a competing full-page redirect.
      const { data: user } = await api.get("/users/me", { timeout: 5000, skipAuthRedirect: true });
      setUser(user);
      const reviewerPage = to.path === "/reviews" && ["physician", "prescription_specialist"].includes(user.role);
      if (to.path !== "/onboarding" && !reviewerPage && !user.onboarding_done) return "/onboarding";
    } catch (error) {
      if ([401, 404].includes(error?.response?.status)) {
        clearUser();
        return loginDestination(to.fullPath, hadUser);
      }
      // A network failure says nothing about whether the cookie is still valid.
      return { path: "/connection", query: { next: safeReturnPath(to.fullPath) } };
    }
    return true;
  };
}
