# What's Still Left to Connect

1. **RAG seed knowledge** — 15 docs only, needs proper KB with chunking pipeline
2. **FFmpeg dependency** — Whisper fix needs FFmpeg on server (yt-dlp audio extract)
3. **Real frame extraction** — Still using YouTube thumbnails, not actual video keyframes
4. **PaddleOCR self-hosted** — Missing, still on Gemini API only
5. **Self-hosted Whisper GPU** — Missing, still on OpenAI API
6. **PostgreSQL upgrade** — SQLite works for 1K users, PG needed beyond
7. **Redis in production** — Code exists but disabled by default
8. **CI/CD pipeline** — No GitHub Actions, no auto-deploy
9. **Monitoring stack** — Logging exists, but Sentry/Grafana missing
10. **Background job queue** — Analysis still blocks HTTP request
11. **WebSocket delivery** — No real-time push, only sync HTTP
12. **Chrome Web Store assets** — Icons are .gitkeep, permissions unchecked
13. **Claim extraction** — Still uses video title, no LLM extraction step
14. **Multi-language** — English only, no i18n
15. **Extension auth token refresh** — Token expiry not handled in content.js

---

### Q1: FFmpeg issue — why not download it? How to fix?

**Why:** yt-dlp needs FFmpeg to extract audio from YouTube videos (convert from webm/opus to mp3). It's an external binary, not a Python package.

**How to fix (3 options):**
- **Windows:** Download `ffmpeg.exe` from `ffmpeg.org`, place it in project root or add to PATH. yt-dlp auto-detects it.
- **Docker:** Add `RUN apt-get install -y ffmpeg` to Dockerfile. Works out of the box.
- **Skip FFmpeg:** Use `--extract-audio --audio-format wav` instead of mp3 (wav doesn't need FFmpeg with some formats). Or use `format="bestaudio"` without postprocessing — send raw opus bytes to Whisper (Whisper accepts multiple formats).

**Recommended fix for MVP:** Add to Dockerfile: `RUN apt-get update && apt-get install -y ffmpeg`. That's it.

### Q2: How far are we from making the Chrome extension actually work?

**What works now:**
- Extension detects YouTube Shorts (content.js via MutationObserver)
- Local risk detector flags high-risk videos by keywords
- "Verify" button appears overlay on the video
- Popup with Dashboard, History, and Account tabs
- Register/Login flow works end-to-end

**What's missing before a user can use it:**
1. **Real API keys** — .env needs valid OPENAI_API_KEY and GEMINI_API_KEY
2. **FFmpeg installed** — for Whisper audio extraction (or remove Whisper fallback)
3. **Extension loaded in Chrome** — go to `chrome://extensions`, enable Developer mode, Load unpacked, select `extension/` folder
4. **Backend URL config** — extension currently points to `http://localhost:8000`, needs to match your deployed backend
5. **Icons** — `icons/` folder has .gitkeep, needs real 16/48/128 PNGs (Chrome rejects submission without them)

**Effort to get a working demo:**
- 10 min: add icons, load unpacked extension
- 20 min: set API keys + install FFmpeg
- Done. The extension is ready to test locally right now.
