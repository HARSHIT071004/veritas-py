const API_BASE = "http://localhost:8000";

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(["token", "userId"], (data) => {
    if (!data.userId) {
      chrome.storage.local.set({ userId: "anon_" + Date.now() });
    }
  });
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  switch (msg.type) {
    case "ANALYZE":
      analyzeVideo(msg.videoId, msg.metadata, sender.tab?.id).then(sendResponse);
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
      chrome.storage.local.remove(["token", "userId"]);
      sendResponse({ success: true });
      return true;
    case "GET_AUTH":
      chrome.storage.local.get(["token", "userId"], (data) => {
        sendResponse(data);
      });
      return true;
  }
});

async function getHeaders() {
  const headers = { "Content-Type": "application/json" };
  const { token } = await chrome.storage.local.get("token");
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function analyzeVideo(videoId, metadata, tabId) {
  try {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/api/v1/analyze`, {
      method: "POST",
      headers,
      body: JSON.stringify({ video_id: videoId, ...metadata })
    });
    const data = await res.json();
    if (tabId && data.success) {
      chrome.tabs.sendMessage(tabId, {
        type: "RESULT_READY",
        videoId,
        result: data.result
      });
    }
    return data;
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function getHistory() {
  try {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/api/v1/history`, { headers });
    return await res.json();
  } catch (err) {
    return { history: [] };
  }
}

async function submitFeedback(videoId, rating) {
  try {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/api/v1/feedback`, {
      method: "POST",
      headers,
      body: JSON.stringify({ video_id: videoId, rating })
    });
    return await res.json();
  } catch (err) {
    return { success: false };
  }
}

async function login(email, password) {
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (data.success) {
      chrome.storage.local.set({ token: data.token, userId: data.user_id });
    }
    return data;
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function register(email, password, name) {
  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name })
    });
    const data = await res.json();
    if (data.success) {
      chrome.storage.local.set({ token: data.token, userId: data.user_id });
    }
    return data;
  } catch (err) {
    return { success: false, error: err.message };
  }
}
