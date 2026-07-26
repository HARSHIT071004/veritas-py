const API_BASE = "http://localhost:8000/api/v1";

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ userId: "user_" + Date.now() });
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "ANALYZE") {
    analyzeVideo(msg.videoId, msg.metadata, sender.tab?.id).then(sendResponse);
    return true;
  }
  if (msg.type === "GET_HISTORY") {
    getHistory().then(sendResponse);
    return true;
  }
  if (msg.type === "SUBMIT_FEEDBACK") {
    submitFeedback(msg.videoId, msg.rating).then(sendResponse);
    return true;
  }
});

async function analyzeVideo(videoId, metadata, tabId) {
  const { userId } = await chrome.storage.local.get("userId");
  try {
    const res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": userId
      },
      body: JSON.stringify({ video_id: videoId, ...metadata })
    });
    const data = await res.json();
    if (tabId) {
      chrome.tabs.sendMessage(tabId, {
        type: "RESULT_READY",
        videoId,
        result: data.result || data
      });
    }
    return data;
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function getHistory() {
  const { userId } = await chrome.storage.local.get("userId");
  try {
    const res = await fetch(`${API_BASE}/history`, {
      headers: { "X-User-Id": userId }
    });
    return await res.json();
  } catch (err) {
    return { history: [] };
  }
}

async function submitFeedback(videoId, rating) {
  const { userId } = await chrome.storage.local.get("userId");
  try {
    const res = await fetch(`${API_BASE}/feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": userId
      },
      body: JSON.stringify({ video_id: videoId, rating })
    });
    return await res.json();
  } catch (err) {
    return { success: false };
  }
}
