const setupForm = document.getElementById("setupForm");
const setupError = document.getElementById("setupError");
const setupRootPath = document.body.dataset.rootPath || "";

setupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await fetch(setupForm.action, {
    method: "POST",
    body: new FormData(setupForm),
    redirect: "manual",
  });
  if (response.ok || response.type === "opaqueredirect" || response.status === 0) {
    window.location.href = `${setupRootPath}/browse/`;
    return;
  }
  const payload = await response.json().catch(() => ({ detail: "Setup failed" }));
  setupError.textContent = payload.detail || "Setup failed";
  setupError.hidden = false;
});
