document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.querySelectorAll(".tab");
  const contents = document.querySelectorAll(".tab-content");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      contents.forEach(c => c.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.tab).classList.add("active");
      if (tab.dataset.tab === "history") loadHistory();
      if (tab.dataset.tab === "account") checkAuth();
      if (tab.dataset.tab === "settings") loadSettings();
    });
  });

  loadStats();

  document.getElementById("show-register").addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("login-form").style.display = "block";
    document.getElementById("register-form").style.display = "none";
  });

  document.getElementById("show-login").addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("register-form").style.display = "none";
    document.getElementById("login-form").style.display = "block";
  });

  document.getElementById("login-btn").addEventListener("click", () => {
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    if (!email || !password) return showError("Fill all fields");
    chrome.runtime.sendMessage({ type: "LOGIN", email, password }, (res) => {
      if (res.success) { hideForm(); checkAuth(); loadStats(); }
      else showError(res.error || "Login failed");
    });
  });

  document.getElementById("register-btn").addEventListener("click", () => {
    const name = document.getElementById("reg-name").value;
    const email = document.getElementById("reg-email").value;
    const password = document.getElementById("reg-password").value;
    if (!email || !password) return showError("Fill all fields");
    if (password.length < 6) return showError("Password too short");
    chrome.runtime.sendMessage({ type: "REGISTER", email, password, name }, (res) => {
      if (res.success) { hideForm(); checkAuth(); loadStats(); }
      else showError(res.error || "Registration failed");
    });
  });

  document.getElementById("logout-btn").addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "LOGOUT" }, () => {
      showLoginForm();
      loadStats();
    });
  });

  document.getElementById("save-settings").addEventListener("click", () => {
    const url = document.getElementById("api-url").value.trim();
    if (!url) return;
    chrome.runtime.sendMessage({ type: "SET_API_URL", url }, (res) => {
      const msg = document.getElementById("settings-msg");
      msg.textContent = "Saved";
      msg.style.display = "block";
      setTimeout(() => msg.style.display = "none", 2000);
    });
  });
});

function showError(msg) {
  const el = document.getElementById("auth-error");
  el.textContent = msg;
  el.style.display = "block";
  setTimeout(() => el.style.display = "none", 3000);
}

function showLoginForm() {
  document.getElementById("login-form").style.display = "block";
  document.getElementById("register-form").style.display = "none";
  document.getElementById("profile").style.display = "none";
  document.getElementById("auth-status").textContent = "";
}

function hideForm() {
  document.getElementById("login-form").style.display = "none";
  document.getElementById("register-form").style.display = "none";
  document.getElementById("profile").style.display = "block";
}

function checkAuth() {
  chrome.storage.local.get(["token", "userId", "userEmail"], (data) => {
    if (data.token) {
      document.getElementById("login-form").style.display = "none";
      document.getElementById("register-form").style.display = "none";
      document.getElementById("profile").style.display = "block";
      document.getElementById("profile-email").textContent = "Logged in: " + (data.userEmail || data.userId);
      document.getElementById("auth-status").textContent = "Signed in";
    } else {
      showLoginForm();
    }
  });
}

function loadSettings() {
  chrome.runtime.sendMessage({ type: "GET_API_URL" }, (res) => {
    document.getElementById("api-url").value = res?.url || "http://localhost:8000";
  });
}

async function loadStats() {
  chrome.runtime.sendMessage({ type: "GET_HISTORY" }, (res) => {
    const history = res?.history || [];
    document.getElementById("total-checked").textContent = history.length;
    const today = new Date().toISOString().slice(0, 10);
    const todayCount = history.filter(h => (h.created_at || "").startsWith(today)).length;
    document.getElementById("today-checked").textContent = todayCount;
  });
}

async function loadHistory() {
  chrome.runtime.sendMessage({ type: "GET_HISTORY" }, (res) => {
    const list = document.getElementById("history-list");
    const history = res?.history || [];
    if (history.length === 0) {
      list.innerHTML = '<p class="empty">No videos checked yet.</p>';
      return;
    }
    list.innerHTML = history.map(h => {
      const vc = `verdict-${h.verdict || "unverifiable"}`;
      const time = h.created_at ? new Date(h.created_at).toLocaleString() : "";
      return `<div class="history-item">
        <span class="history-verdict ${vc}">${h.verdict || "unknown"}</span>
        <div class="history-claim">${(h.claim || "").slice(0, 120)}</div>
        <div class="history-time">${time}</div>
      </div>`;
    }).join("");
  });
}
