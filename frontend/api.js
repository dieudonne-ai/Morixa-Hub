/**
 * MedHub — Centralized API layer
 * Features:
 *  - Auth guard (redirects to /login.html if no token)
 *  - JWT token injection in every request
 *  - Centralized error handling
 *  - User session helpers
 */

const API_BASE =
  window.location.hostname === "localhost"
    ? "http://localhost:5000/api"
    : "https://morixa-hub-api.onrender.com/api";

// ── Pages that don't require authentication ──────────────────
const PUBLIC_PAGES = ["/login.html"];

// ── Auth guard ───────────────────────────────────────────────
(function authGuard() {
  const path = window.location.pathname;
  const isPublic = PUBLIC_PAGES.some(p => path.endsWith(p));
  const token = localStorage.getItem("medhub_token");
  if (!isPublic && !token) {
    window.location.href = "/login.html";
  }
})();

// ── Token helpers ────────────────────────────────────────────
function getToken()   { return localStorage.getItem("medhub_token"); }
function getUser()    { return JSON.parse(localStorage.getItem("medhub_user") || "{}"); }
function getUserId()  { return getUser().id || null; }
function isLoggedIn() { return !!getToken(); }

function logout() {
  localStorage.removeItem("medhub_token");
  localStorage.removeItem("medhub_user");
  window.location.href = "/login.html";
}

// ── Core fetch wrapper ───────────────────────────────────────

async function apiFetch(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(getToken() ? { "Authorization": `Bearer ${getToken()}` } : {}),
    ...(options.headers || {}),
  };

  let res;
  try {
    res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  } catch(e) {
    throw { error: "Server unreachable. Please check your connection." };
  }

  // Token expired → redirect to login
  if (res.status === 401) { logout(); return; }

  // Try to parse JSON, fallback to text
  let data;
  try {
    data = await res.json();
  } catch(_) {
    data = { error: `Server error ${res.status}` };
  }

  if (!res.ok) throw data;
  return data;
}

// ── File upload (multipart) ──────────────────────────────────
async function apiUpload(endpoint, formData) {
  let res;
  try {
    res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${getToken()}` },
      body: formData,
    });
  } catch (e) {
    throw { error: "Server unreachable." };
  }
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

// ════════════════════════════════════════════════════════════
// AUTH
// ════════════════════════════════════════════════════════════
const Auth = {
  async login(email, password) {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem("medhub_token", data.token);
    localStorage.setItem("medhub_user",  JSON.stringify(data.user));
    return data;
  },

  async register(payload) {
    return apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  logout,
};

// ════════════════════════════════════════════════════════════
// POSTS
// ════════════════════════════════════════════════════════════
const Posts = {
  list(params = {}) {
    return apiFetch("/posts/?" + new URLSearchParams(params));
  },

  create(payload) {
    return apiFetch("/posts/", {
      method: "POST",
      body: JSON.stringify({ user_id: getUserId(), ...payload }),
    });
  },

  like(postId) {
    return apiFetch(`/posts/${postId}/like`, {
      method: "POST",
      body: JSON.stringify({ user_id: getUserId() }),
    });
  },

  comment(postId, body) {
    return apiFetch(`/posts/${postId}/comment`, {
      method: "POST",
      body: JSON.stringify({ user_id: getUserId(), body }),
    });
  },
};

// ════════════════════════════════════════════════════════════
// REPOSITORIES
// ════════════════════════════════════════════════════════════
const Repos = {
  list(params = {}) {
    return apiFetch("/repos/?" + new URLSearchParams(params));
  },

  create(payload) {
    return apiFetch("/repos/", {
      method: "POST",
      body: JSON.stringify({ user_id: getUserId(), ...payload }),
    });
  },

  star(repoId) {
    return apiFetch(`/repos/${repoId}/star`, {
      method: "POST",
      body: JSON.stringify({ user_id: getUserId() }),
    });
  },
};

// ════════════════════════════════════════════════════════════
// FILES
// ════════════════════════════════════════════════════════════
const Files = {
  upload(file, { postId = null, repoId = null } = {}) {
    const fd = new FormData();
    fd.append("file",    file);
    fd.append("user_id", getUserId());
    if (postId) fd.append("post_id", postId);
    if (repoId) fd.append("repo_id", repoId);
    return apiUpload("/files/upload", fd);
  },

  listForPost(postId) {
    return apiFetch(`/files/post/${postId}`);
  },

  listForRepo(repoId) {
    return apiFetch(`/files/repo/${repoId}`);
  },
};

// ════════════════════════════════════════════════════════════
// MESSAGES
// ════════════════════════════════════════════════════════════
const Messages = {
  send(receiverId, body) {
    return apiFetch("/messages/", {
      method: "POST",
      body: JSON.stringify({ sender_id: getUserId(), receiver_id: receiverId, body }),
    });
  },

  conversation(otherUserId) {
    return apiFetch(`/messages/conversation/${getUserId()}/${otherUserId}`);
  },

  inbox() {
    return apiFetch(`/messages/inbox/${getUserId()}`);
  },
};

// ════════════════════════════════════════════════════════════
// USERS
// ════════════════════════════════════════════════════════════
const Users = {
  leaderboard() {
    return apiFetch("/users/leaderboard");
  },

  myPoints() {
    return apiFetch(`/users/${getUserId()}/points`);
  },

  profile(userId) {
    return apiFetch(`/users/${userId}`);
  },

  notifications() {
    return apiFetch(`/users/${getUserId()}/notifications`);
  },

  markNotifRead(notifId) {
    return apiFetch(`/users/notifications/${notifId}/read`, { method: "POST" });
  },
};

// ════════════════════════════════════════════════════════════
// UI HELPERS
// ════════════════════════════════════════════════════════════

/**
 * Inject current user info into navbar elements.
 * Expects elements with ids: nav-avatar, nav-username (optional).
 */
function injectNavUser() {
  const u = getUser();
  if (!u.full_name) return;
  const parts = u.full_name.trim().split(" ");
  const initials = parts.map(p => p[0]).join("").toUpperCase().slice(0, 2);
  const avatarEl = document.getElementById("nav-avatar");
  if (avatarEl) avatarEl.textContent = initials;
  const nameEl = document.getElementById("nav-username");
  if (nameEl) nameEl.textContent = u.full_name;
}

/**
 * Show a toast notification.
 * @param {string} msg
 * @param {'success'|'error'|'info'} type
 */
function showToast(msg, type = "success") {
  const colors = {
    success: { bg: "#E1F5EE", color: "#0F6E56", icon: "ti-circle-check" },
    error:   { bg: "#FAECE7", color: "#993C1D", icon: "ti-alert-circle" },
    info:    { bg: "#E6F1FB", color: "#185FA5", icon: "ti-info-circle" },
  };
  const c = colors[type] || colors.info;
  const toast = document.createElement("div");
  toast.style.cssText = `
    position:fixed; bottom:24px; right:24px; z-index:9999;
    background:${c.bg}; color:${c.color}; border-radius:8px;
    padding:12px 18px; font-size:13px; font-weight:500;
    display:flex; align-items:center; gap:8px;
    box-shadow:0 4px 16px rgba(0,0,0,0.12);
    animation: slideIn 0.2s ease;
  `;
  toast.innerHTML = `<i class="ti ${c.icon}" style="font-size:16px"></i> ${msg}`;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

/**
 * Format a number: 1200 → 1.2k
 */
function formatNum(n) {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(".0", "") + "k";
  return n.toString();
}

/**
 * Relative time: "2 hours ago"
 */
function timeAgo(dateStr) {
  const diff = (Date.now() - new Date(dateStr)) / 1000;
  if (diff < 60)   return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}


async function downloadFile(fileId, fileName) {
  try {
    const res = await fetch(`${API_BASE}/files/download/${fileId}`, {
      headers: { "Authorization": `Bearer ${getToken()}` }
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: "Download failed" }));
      return showToast(err.error || "Download failed", "error");
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = fileName;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    showToast("Could not download file.", "error");
  }
}


function renderVerifBadge(level) {
  const badges = {
    none:     { icon: "ti-user-question", label: "Unverified",          cls: "badge-none"     },
    email:    { icon: "ti-mail-check",    label: "Email Verified",       cls: "badge-email"    },
    document: { icon: "ti-clock",         label: "Pending Review",       cls: "badge-document" },
    verified: { icon: "ti-shield-check",  label: "Verified Physician",   cls: "badge-verified" },
    registry: { icon: "ti-certificate",   label: "Registry Verified",    cls: "badge-registry" },
  };
  const b = badges[level] || badges.none;
  return `<span class="verif-badge ${b.cls}">
    <i class="ti ${b.icon}"></i>${b.label}
  </span>`;
}


// Auto-inject nav user on DOM ready
document.addEventListener("DOMContentLoaded", injectNavUser);
