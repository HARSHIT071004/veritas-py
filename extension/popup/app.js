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
    });
  });

  loadStats();
  loadHistory();
});

async function loadStats() {
  chrome.runtime.sendMessage({ type: "GET_HISTORY" }, (res) => {
    const history = res?.history || [];
    document.getElementById("total-checked").textContent = history.length;

    const today = new Date().toISOString().slice(0, 10);
    const todayCount = history.filter(h =>
      (h.created_at || "").startsWith(today)
    ).length;
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
      const time = h.created_at
        ? new Date(h.created_at).toLocaleString()
        : "";
      return `
        <div class="history-item">
          <span class="history-verdict ${vc}">${h.verdict || "unknown"}</span>
          <div class="history-claim">${(h.claim || "").slice(0, 120)}</div>
          <div class="history-time">${time}</div>
        </div>
      `;
    }).join("");
  });
}
