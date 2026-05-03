const adminRootPath = document.body.dataset.rootPath || "";
const createUserForm = document.getElementById("createUserForm");
const adminMessage = document.getElementById("adminMessage");
const userList = document.getElementById("userList");

async function loadUsers() {
  const response = await fetch(`${adminRootPath}/admin/users`, {
    headers: { Accept: "application/json" },
  });
  if (response.status === 401) {
    window.location.href = `${adminRootPath}/login`;
    return;
  }
  if (!response.ok) {
    userList.textContent = "Unable to load users.";
    return;
  }
  const payload = await response.json();
  renderUsers(payload.users || []);
}

function renderUsers(users) {
  userList.innerHTML = "";
  for (const user of users) {
    const row = document.createElement("article");
    row.className = "user-row";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(user.display_name || user.username)}</strong>
        <small>${escapeHtml(user.username)}</small>
      </div>
      <span>${escapeHtml(user.role)}</span>
    `;
    userList.append(row);
  }
}

createUserForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  adminMessage.hidden = true;
  const response = await fetch(createUserForm.action, {
    method: "POST",
    body: new FormData(createUserForm),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Unable to add user" }));
    adminMessage.textContent = payload.detail || "Unable to add user";
    adminMessage.hidden = false;
    return;
  }
  createUserForm.reset();
  await loadUsers();
});

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

loadUsers();
