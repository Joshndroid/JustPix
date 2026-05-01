const form = document.getElementById("loginForm");
const error = document.getElementById("loginError");
const rootPath = document.body.dataset.rootPath || "";

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await fetch(form.action, {
    method: "POST",
    body: new FormData(form),
    redirect: "manual",
  });
  if (response.ok || response.type === "opaqueredirect" || response.status === 0) {
    window.location.href = `${rootPath}/browse/`;
    return;
  }
  const payload = await response.json().catch(() => ({ detail: "Login failed" }));
  error.textContent = payload.detail || "Login failed";
  error.hidden = false;
});
