const DEFAULT_API = "http://localhost:8000";

async function getApiBase() {
  const { apiUrl } = await chrome.storage.local.get("apiUrl");
  return apiUrl || DEFAULT_API;
}

async function getHeaders() {
  const headers = { "Content-Type": "application/json" };
  const { token } = await chrome.storage.local.get("token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function refreshToken() {
  const { refreshToken: rt } = await chrome.storage.local.get("refreshToken");
  if (!rt) return;
  try {
    const base = await getApiBase();
    const res = await fetch(`${base}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${rt}` },
    });
    const data = await res.json();
    if (data.success) {
      await chrome.storage.local.set({ token: data.access_token, refreshToken: data.refresh_token });
    }
  } catch (err) {
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(["userId"], (data) => {
    if (!data.userId) chrome.storage.local.set({ userId: "anon_" + Date.now() });
  });
  chrome.alarms.create("tokenRefresh", { periodInMinutes: 5 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "tokenRefresh") refreshToken();
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  switch (msg.type) {
    case "ANALYZE":
      analyzeVideo(msg.videoId, msg.metadata, sender.tab?.id).then(sendResponse);
      return true;
    case "ANALYZE_ASYNC":
      analyzeVideoAsync(msg.videoId, msg.metadata, sender.tab?.id).then(sendResponse);
      return true;
    case "POLL_RESULT":
      pollResult(msg.jobId, msg.tabId).then(sendResponse);
      return true;
    case "GET_HISTORY":
      getHistory().then(sendResponse);
      return true;
    case "SUBMIT_FEEDBACK":
      submitFeedback(msg.videoId, msg.rating).then(sendResponse);
      return true;
    case "LOGIN":
      login(msg.email, msg.password).then(sendResponse);
      return true;
    case "REGISTER":
      register(msg.email, msg.password, msg.name).then(sendResponse);
      return true;
    case "LOGOUT":
      chrome.storage.local.remove(["token", "refreshToken", "userId"]);
      sendResponse({ success: true });
      return true;
    case "GET_AUTH":
      chrome.storage.local.get(["token", "userId"], (data) => sendResponse(data));
      return true;
    case "SET_API_URL":
      chrome.storage.local.set({ apiUrl: msg.url });
      sendResponse({ success: true });
      return true;
    case "GET_API_URL":
      getApiBase().then((url) => sendResponse({ url }));
      return true;
  }
});

async function analyzeVideo(videoId, metadata, tabId) {
  try {
    const base = await getApiBase();
    const headers = await getHeaders();
    const res = await fetch(`${base}/api/v1/analyze`, {
      method: "POST",
      headers,
      body: JSON.stringify({ video_id: videoId, ...metadata }),
    });
    const data = await res.json();
    if (tabId && data.success) {
      chrome.tabs.sendMessage(tabId, { type: "RESULT_READY", videoId, result: data.result });
    }
    return data;
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function analyzeVideoAsync(videoId, metadata, tabId) {
  try {
    const base = await getApiBase();
    const headers = await getHeaders();
    const res = await fetch(`${base}/api/v1/analyze/async`, {
      method: "POST",
      headers,
      body: JSON.stringify({ video_id: videoId, ...metadata }),
    });
    const data = await res.json();
    if (data.success && data.job_id) {
      pollUntilDone(data.job_id, videoId, tabId);
      return { success: true, job_id: data.job_id, status: "queued" };
    }
    return data;
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function pollUntilDone(jobId, videoId, tabId) {
  const base = await getApiBase();
  const headers = await getHeaders();
  const maxAttempts = 60;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 2000));
    try {
      const res = await fetch(`${base}/api/v1/result/${jobId}`, { headers });
      const data = await res.json();
      if (data.status === "completed" && data.result) {
        if (tabId) {
          chrome.tabs.sendMessage(tabId, { type: "RESULT_READY", videoId, result: data.result });
        }
        chrome.storage.local.set({ ["analyzed_" + videoId]: true });
        return;
      }
      if (data.status === "failed") {
        if (tabId) {
          chrome.tabs.sendMessage(tabId, { type: "RESULT_ERROR", videoId, error: data.error || "Analysis failed" });
        }
        return;
      }
    } catch (err) {
    }
  }
  if (tabId) {
    chrome.tabs.sendMessage(tabId, { type: "RESULT_ERROR", videoId, error: "Timed out waiting for result" });
  }
}

async function pollResult(jobId, tabId) {
  await pollUntilDone(jobId, null, tabId);
  return { polled: true };
}

async function getHistory() {
  try {
    const base = await getApiBase();
    const headers = await getHeaders();
    const res = await fetch(`${base}/api/v1/history`, { headers });
    return await res.json();
  } catch (err) {
    return { history: [] };
  }
}

async function submitFeedback(videoId, rating) {
  try {
    const base = await getApiBase();
    const headers = await getHeaders();
    const res = await fetch(`${base}/api/v1/feedback`, {
      method: "POST",
      headers,
      body: JSON.stringify({ video_id: videoId, rating }),
    });
    return await res.json();
  } catch (err) {
    return { success: false };
  }
}

async function login(email, password) {
  try {
    const base = await getApiBase();
    const res = await fetch(`${base}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (data.success) {
      await chrome.storage.local.set({ token: data.access_token, refreshToken: data.refresh_token, userEmail: email, userId: data.user_id });
    }
    return data;
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function register(email, password, name) {
  try {
    const base = await getApiBase();
    const res = await fetch(`${base}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    });
    const data = await res.json();
    if (data.success) {
      await chrome.storage.local.set({ token: data.access_token, refreshToken: data.refresh_token, userEmail: email, userId: data.user_id });
    }
    return data;
  } catch (err) {
    return { success: false, error: err.message };
  }
}
