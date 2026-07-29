const RISK_KEYWORDS = [
  "miracle cure", "they don't want you to know", "big pharma",
  "suppressed", "hidden truth", "mainstream media won't tell you",
  "natural cure", "detox", "immune booster", "shocking truth",
  "what they're not telling you", "doctors hate this", "secret",
  "cure", "conspiracy", "exposed", "fake news", "woke",
  "government hiding", "100% effective", "guaranteed results"
];

const TRUSTED_CHANNELS = [
  "medcram", "doctor mike", "veritasium", "kurzgesagt",
  "scishow", "healthcare triage", "vox", "bbc news",
  "reuters", "associated press", "crash course"
];

const PROGRESS_STAGES = [
  "Preparing video",
  "Fetching transcript",
  "Analyzing claims",
  "Generating verdict",
  "Finalizing result"
];

let observer = null;
let backgroundTimer = null;

function init() {
  const existing = document.getElementById("clearlens-badge");
  if (existing) existing.remove();

  injectBadge();
  observeNavigation();
}

function observeNavigation() {
  if (observer) observer.disconnect();
  observer = new MutationObserver(() => {
    if (window.location.pathname.includes("/shorts/")) {
      setTimeout(checkCurrentShort, 800);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

function checkCurrentShort() {
  const pathParts = window.location.pathname.split("/");
  const videoId = pathParts[pathParts.length - 1];
  if (!videoId || videoId.length < 5) return;

  chrome.storage.local.get(["analyzed_" + videoId, "bg_enabled"], (data) => {
    if (data["analyzed_" + videoId]) return;

    chrome.runtime.sendMessage({ type: "PREFETCH", videoId });
    showVerifyBadge(videoId);

    if (data.bg_enabled !== false) {
      if (backgroundTimer) clearTimeout(backgroundTimer);
      backgroundTimer = setTimeout(() => {
        chrome.runtime.sendMessage({ type: "PREFETCH", videoId, background: true });
      }, 3000);
    }
  });
}

function showVerifyBadge(videoId) {
  const existing = document.getElementById("clearlens-badge");
  if (existing) existing.remove();

  const title = document.title || "";
  const channel = document.querySelector("#owner #text a")?.textContent || "";

  const risk = assessRisk(title, channel);
  if (risk === "low") return;

  const badge = document.createElement("div");
  badge.id = "clearlens-badge";
  badge.innerHTML = `<button id="clearlens-verify-btn">${risk === "high" ? "⚠" : "?"} Verify</button>`;

  Object.assign(badge.style, {
    position: "fixed", bottom: "20px", right: "20px",
    zIndex: "99999", fontFamily: "Arial, sans-serif"
  });

  const btn = badge.querySelector("button");
  Object.assign(btn.style, {
    background: risk === "high" ? "#ff4444" : "#ffaa00",
    color: "white", border: "none", borderRadius: "20px",
    padding: "8px 16px", fontSize: "14px", cursor: "pointer",
    fontWeight: "bold", boxShadow: "0 2px 8px rgba(0,0,0,0.3)"
  });

  btn.onmouseenter = () => { btn.style.opacity = "0.9"; };
  btn.onmouseleave = () => { btn.style.opacity = "1"; };

  btn.onclick = async () => {
    if (backgroundTimer) clearTimeout(backgroundTimer);

    btn.textContent = "Analyzing claims...";
    btn.disabled = true;
    btn.style.background = "#3b82f6";

    const metadata = {
      title,
      description: document.querySelector("#description-inline")?.textContent?.trim() || "",
      channel,
      hashtags: (title.match(/#\w+/g) || []).map(h => h.slice(1))
    };

    const progressInterval = startProgressAnimation(btn);

    chrome.runtime.sendMessage({
      type: "ANALYZE_ASYNC",
      videoId,
      metadata
    }, (response) => {
      if (response?.success && response.job_id) {
        clearInterval(progressInterval);
        btn.textContent = "Waiting for result...";
        startPollingWithProgress(videoId, response.job_id, btn, progressInterval);
      } else if (response?.success && response.result) {
        clearInterval(progressInterval);
        showResultCard(response.result);
        chrome.storage.local.set({ ["analyzed_" + videoId]: true });
        badge.remove();
      } else {
        clearInterval(progressInterval);
        btn.textContent = "Error - Try Again";
        btn.disabled = false;
        btn.style.background = "#ff4444";
      }
    });
  };

  document.body.appendChild(badge);
}

function startProgressAnimation(btn) {
  let stage = 1;
  return setInterval(() => {
    if (stage < PROGRESS_STAGES.length) {
      btn.textContent = PROGRESS_STAGES[stage] + "...";
      stage++;
    }
  }, 3000);
}

function startPollingWithProgress(videoId, jobId, btn, progressInterval) {
  chrome.runtime.sendMessage({
    type: "POLL_RESULT",
    jobId,
    tabId: undefined
  });
}

function assessRisk(title, channel) {
  const lower = title.toLowerCase();
  const channelLower = channel.toLowerCase();

  if (TRUSTED_CHANNELS.some(tc => channelLower.includes(tc))) {
    return "low";
  }

  const matchCount = RISK_KEYWORDS.filter(k => lower.includes(k)).length;
  if (matchCount >= 2) return "high";
  if (matchCount === 1) return "medium";
  return "low";
}

function startPolling(videoId, jobId, btn) {
  chrome.runtime.sendMessage({
    type: "POLL_RESULT",
    jobId,
    tabId: undefined
  });
}

function showResultCard(result) {
  const existing = document.getElementById("clearlens-result");
  if (existing) existing.remove();

  const verdictColors = {
    "true": "#22c55e",
    "false": "#ef4444",
    "misleading": "#f59e0b",
    "unverifiable": "#6b7280"
  };

  const color = verdictColors[result.verdict] || "#6b7280";

  const card = document.createElement("div");
  card.id = "clearlens-result";

  const confidenceBar = Math.round((result.confidence || 0) * 100);

  card.innerHTML = `
    <div style="background:white;border-radius:12px;padding:16px;width:340px;
                box-shadow:0 4px 24px rgba(0,0,0,0.15);font-family:Arial,sans-serif;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <span style="font-weight:bold;font-size:16px;color:#111;">ClearLens</span>
        <span style="background:${color};color:white;padding:4px 12px;border-radius:12px;
                     font-size:12px;font-weight:bold;text-transform:uppercase;">
          ${result.verdict}
        </span>
      </div>
      <div style="margin-bottom:12px;">
        <div style="font-size:11px;color:#666;margin-bottom:4px;">Confidence</div>
        <div style="background:#e5e7eb;border-radius:4px;height:6px;">
          <div style="background:${color};width:${confidenceBar}%;height:6px;border-radius:4px;"></div>
        </div>
        <div style="font-size:11px;color:#666;margin-top:2px;text-align:right;">${confidenceBar}%</div>
      </div>
      <div style="font-size:13px;color:#333;margin-bottom:12px;line-height:1.4;">
        ${result.explanation || "No explanation available."}
      </div>
      <div style="font-size:11px;color:#888;margin-bottom:8px;">
        ${(result.sources || []).slice(0, 2).map(s => `• ${s}`).join("<br>")}
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;">
        <button data-rating="helpful" style="flex:1;padding:6px;border:1px solid #d1d5db;
                border-radius:8px;background:white;cursor:pointer;font-size:12px;">Helpful</button>
        <button data-rating="not_helpful" style="flex:1;padding:6px;border:1px solid #d1d5db;
                border-radius:8px;background:white;cursor:pointer;font-size:12px;">Not helpful</button>
        <button id="clearlens-close" style="padding:6px 10px;border:1px solid #d1d5db;
                border-radius:8px;background:white;cursor:pointer;font-size:12px;">Close</button>
      </div>
    </div>
  `;

  Object.assign(card.style, {
    position: "fixed", bottom: "80px", right: "20px",
    zIndex: "99999"
  });

  card.querySelectorAll("[data-rating]").forEach(btn => {
    btn.onclick = () => {
      chrome.runtime.sendMessage({
        type: "SUBMIT_FEEDBACK",
        videoId: result.video_id || "",
        rating: btn.dataset.rating
      });
      btn.style.background = "#e5e7eb";
    };
  });

  card.querySelector("#clearlens-close").onclick = () => card.remove();

  document.body.appendChild(card);
}

function injectBadge() {
  const style = document.createElement("style");
  style.textContent = `
    @keyframes clearlens-fade-in {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    #clearlens-result { animation: clearlens-fade-in 0.3s ease; }
    #clearlens-badge { animation: clearlens-fade-in 0.3s ease; }
  `;
  document.head.appendChild(style);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}