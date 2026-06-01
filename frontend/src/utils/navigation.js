export function redirectToLogin() {
  if (typeof window !== "undefined") {
    window.location.assign("/main/login");
  }
}
