const state = {
  rootPath: document.body.dataset.rootPath || "",
  currentPath: "",
  sort: localStorage.getItem("justpix-sort") || "name_asc",
  page: 1,
  listing: null,
  media: [],
  activeIndex: 0,
  touchStartX: null,
};

const grid = document.getElementById("grid");
const breadcrumbs = document.getElementById("breadcrumbs");
const emptyState = document.getElementById("emptyState");
const sortSelect = document.getElementById("sortSelect");
const folderName = document.getElementById("folderName");
const folderStats = document.getElementById("folderStats");
const pageLabel = document.getElementById("pageLabel");
const prevPage = document.getElementById("prevPage");
const nextPage = document.getElementById("nextPage");
const lightbox = document.getElementById("lightbox");
const lightboxStage = document.getElementById("lightboxStage");
const lightboxCaption = document.getElementById("lightboxCaption");
const logoutForm = document.getElementById("logoutForm");
const adminLink = document.getElementById("adminLink");

sortSelect.value = state.sort;

function encodePath(path) {
  return path.split("/").filter(Boolean).map(encodeURIComponent).join("/");
}

function mediaUrl(prefix, path) {
  return `${state.rootPath}/${prefix}/${encodePath(path)}`;
}

function browseUrl(path) {
  const encoded = encodePath(path);
  return `${state.rootPath}/browse/${encoded}`;
}

function currentPathFromLocation() {
  const prefix = `${state.rootPath}/browse/`;
  if (!location.pathname.startsWith(prefix)) {
    return "";
  }
  return decodeURIComponent(location.pathname.slice(prefix.length));
}

async function loadFolder(path = state.currentPath, { push = false, page = 1 } = {}) {
  state.currentPath = path || "";
  state.page = page;
  const query = new URLSearchParams({ sort: state.sort, page: String(state.page) });
  const response = await fetch(`${browseUrl(state.currentPath)}?${query}`, {
    headers: { Accept: "application/json" },
  });
  if (response.status === 401) {
    location.href = `${state.rootPath}/login`;
    return;
  }
  if (!response.ok) {
    grid.innerHTML = "";
    emptyState.textContent = "Folder unavailable.";
    emptyState.hidden = false;
    return;
  }
  state.listing = await response.json();
  state.media = state.listing.media || [];
  if (push) {
    history.pushState({ path: state.currentPath }, "", browseUrl(state.currentPath));
  }
  render();
}

function render() {
  const listing = state.listing;
  folderName.textContent = listing.path ? listing.path.split("/").pop() : "Library";
  folderStats.textContent = ` ${listing.stats.folders} folders, ${listing.stats.images} images, ${listing.stats.videos} videos, ${listing.stats.audio} audio`;
  pageLabel.textContent = `Page ${listing.page}`;
  prevPage.disabled = !listing.has_previous;
  nextPage.disabled = !listing.has_next;
  logoutForm.hidden = !listing.app?.auth_enabled;
  adminLink.hidden = listing.app?.user?.role !== "admin";
  renderBreadcrumbs(listing.path);
  renderGrid(listing);
}

function renderBreadcrumbs(path) {
  breadcrumbs.innerHTML = "";
  const root = document.createElement("a");
  root.href = browseUrl("");
  root.dataset.path = "";
  root.textContent = "Library";
  breadcrumbs.append(root);

  let acc = "";
  for (const part of path.split("/").filter(Boolean)) {
    breadcrumbs.append(document.createTextNode("/"));
    acc = acc ? `${acc}/${part}` : part;
    const targetPath = acc;
    const link = document.createElement("a");
    link.href = browseUrl(targetPath);
    link.dataset.path = targetPath;
    link.textContent = part;
    breadcrumbs.append(link);
  }
}

function renderGrid(listing) {
  grid.innerHTML = "";
  const folderCards = (listing.folders || []).map(folderCard);
  const mediaCards = (listing.media || []).map((item, index) => mediaCard(item, index));
  for (const card of [...folderCards, ...mediaCards]) {
    grid.append(card);
  }
  emptyState.hidden = grid.children.length > 0;
  observeImages();
}

function folderCard(folder) {
  const card = document.createElement("a");
  card.className = "tile folder-tile";
  card.href = browseUrl(folder.path);
  card.addEventListener("click", (event) => navigate(event, folder.path));
  card.innerHTML = `
    <div class="folder-visual"><span></span></div>
    <div class="tile-meta">
      <strong>${escapeHtml(folder.name)}</strong>
      <small>${folder.item_count} items</small>
    </div>
  `;
  return card;
}

function mediaCard(item, index) {
  const button = document.createElement("button");
  button.className = `tile media-tile ${item.media_type}`;
  button.type = "button";
  button.addEventListener("click", () => openLightbox(index));

  const thumb = document.createElement("img");
  thumb.alt = "";
  thumb.loading = "lazy";
  thumb.dataset.src = mediaUrl("thumb", item.path);
  button.append(thumb);

  const badge = document.createElement("span");
  badge.className = "kind-badge";
  badge.textContent = item.media_type;
  button.append(badge);

  const meta = document.createElement("span");
  meta.className = "tile-meta";
  meta.innerHTML = `<strong>${escapeHtml(item.name)}</strong><small>${formatSize(item.size)}</small>`;
  button.append(meta);
  return button;
}

function observeImages() {
  const images = grid.querySelectorAll("img[data-src]");
  if (!("IntersectionObserver" in window)) {
    images.forEach(loadImage);
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        loadImage(entry.target);
        observer.unobserve(entry.target);
      }
    }
  }, { rootMargin: "400px" });
  images.forEach((image) => observer.observe(image));
}

function loadImage(image) {
  image.src = image.dataset.src;
  image.removeAttribute("data-src");
}

function navigate(event, path) {
  event.preventDefault();
  loadFolder(path, { push: true, page: 1 });
}

function openLightbox(index) {
  state.activeIndex = index;
  renderLightbox();
  lightbox.showModal();
}

function stopLightboxMedia() {
  lightboxStage.querySelectorAll("audio, video").forEach((element) => {
    element.pause();
    element.removeAttribute("src");
    element.load();
  });
}

function renderLightbox() {
  const item = state.media[state.activeIndex];
  if (!item) {
    return;
  }
  stopLightboxMedia();
  lightboxStage.innerHTML = "";
  const src = mediaUrl("media", item.path);
  let element;
  if (item.media_type === "image") {
    element = document.createElement("img");
    element.src = src;
    element.alt = item.name;
  } else if (item.media_type === "video") {
    element = document.createElement("video");
    element.src = src;
    element.controls = true;
    element.autoplay = true;
  } else {
    element = document.createElement("audio");
    element.src = src;
    element.controls = true;
    element.autoplay = true;
  }
  lightboxStage.append(element);
  lightboxCaption.textContent = item.name;
}

function stepLightbox(delta) {
  if (!state.media.length) {
    return;
  }
  state.activeIndex = (state.activeIndex + delta + state.media.length) % state.media.length;
  renderLightbox();
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = bytes / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unit]}`;
}

sortSelect.addEventListener("change", () => {
  state.sort = sortSelect.value;
  localStorage.setItem("justpix-sort", state.sort);
  loadFolder(state.currentPath, { page: 1 });
});

prevPage.addEventListener("click", () => loadFolder(state.currentPath, { page: Math.max(1, state.page - 1) }));
nextPage.addEventListener("click", () => loadFolder(state.currentPath, { page: state.page + 1 }));
document.getElementById("closeLightbox").addEventListener("click", () => lightbox.close());
document.getElementById("prevItem").addEventListener("click", () => stepLightbox(-1));
document.getElementById("nextItem").addEventListener("click", () => stepLightbox(1));
lightbox.addEventListener("close", stopLightboxMedia);
breadcrumbs.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-path]");
  if (!link || !breadcrumbs.contains(link)) {
    return;
  }
  navigate(event, link.dataset.path);
});

document.addEventListener("keydown", (event) => {
  if (!lightbox.open) return;
  if (event.key === "Escape") lightbox.close();
  if (event.key === "ArrowLeft") stepLightbox(-1);
  if (event.key === "ArrowRight") stepLightbox(1);
});

lightbox.addEventListener("touchstart", (event) => {
  state.touchStartX = event.changedTouches[0].screenX;
}, { passive: true });
lightbox.addEventListener("touchend", (event) => {
  if (state.touchStartX === null) return;
  const delta = event.changedTouches[0].screenX - state.touchStartX;
  if (Math.abs(delta) > 50) stepLightbox(delta > 0 ? -1 : 1);
  state.touchStartX = null;
}, { passive: true });

window.addEventListener("popstate", () => loadFolder(currentPathFromLocation(), { page: 1 }));

loadFolder(currentPathFromLocation(), { page: 1 });
