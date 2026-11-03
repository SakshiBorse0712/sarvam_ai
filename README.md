# 🚨 Offline-First Citizen Reporter & Emergency Fusion Board
> **Powered by Sarvam AI Indic STT, Sarvam-105B Triage, Translate, and Bulbul TTS**

An end-to-end disaster reporting system designed for low-bandwidth and network-dead zones across India.

---

## 🌟 Key Features

1. **Offline-First Edge Storage (Zero Internet Required)**
   - When a citizen or field reporter is in a network-dead zone, emergency SMS reports and voice memos are safely stored in a local SQLite database (`offline_emergency.db`).
   - Reports are stamped with status `QUEUED` and retain local integrity until connectivity is re-established.

2. **Automatic Reconnection & Sync Engine**
   - Background worker detects signal reconnection (simulated or real).
   - Queued reports are dispatched in order to the central Emergency Fusion Board.

3. **Multilingual Sarvam AI Intelligence Pipeline**
   - **Speech-to-Text (Saaras STT):** Transcribes regional voice memos and missed call recordings into text across 22+ Indic languages.
   - **Incident Triage & Entity Extraction (Sarvam 105B Conversations):** Analyzes raw messages (e.g. Marathi, Hindi, Bengali, Tamil, Hinglish) and extracts structured metadata:
     - Incident Category (`Flood`, `Landslide`, `Fire`, `Medical`, `Structural Collapse`, etc.)
     - Urgency Rating (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
     - Extracted Landmark / Geolocation
     - Estimated Affected Citizen Count
     - English Summary for Central Disaster Control Rooms
   - **Language Translation (Sarvam Translate):** Translates life-saving directives from control room English into the caller's native regional language.
   - **Voice Advisory Synthesis (Bulbul TTS):** Automatically synthesizes regional spoken voice alerts (`.wav`) in the caller's regional tongue for immediate playback over cellular IVR or phone speakers.

4. **Emergency Fusion Board & Control Room UI**
   - Real-time incident triage metrics.
   - Dual audio players for incoming citizen voice memos and generated outbound regional voice advisories.
   - Incident lifecycle tracking (`NEW` ➔ `ASSIGNED` ➔ `DISPATCHED` ➔ `RESOLVED`).
   - One-click targeted regional advisory broadcast modal.

---

## 🏗️ Architecture

```
[ Citizen in Dead Zone / 2G ]
      │ (SMS / Missed Call Voice Memo)
      ▼
[ Local SQLite Queue (Offline) ]  ─── (Network Restored) ───►  [ Sync Engine ]
                                                                     │
            ┌────────────────────────────────────────────────────────┴─────────────────────┐
            ▼                                                        ▼                     ▼
   [ Sarvam Saaras STT ]                                    [ Sarvam 105B Triage ]     [ Sarvam Translate ]
 (Transcribe Regional Audio)                              (Category, Urgency, Geo)    (English -> Indic)
            │                                                        │                     │
            └─────────────────────────┬──────────────────────────────┘                     ▼
                                      ▼                                          [ Sarvam Bulbul TTS ]
                        [ Emergency Fusion Board ]                              (Regional Voice WAV)
                     (Live Incident Command Center)                                        │
                                      ▲                                                    ▼
                                      └──────────────────────────────────────── [ Outbound Advisory ]
                                                                               (Delivered to Citizen)
```

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- Installed packages: `sarvamai`, `fastapi`, `uvicorn`, `python-dotenv`
- A valid `SARVAM_API_KEY` in `.env`

### 2. Launching the Application
Run the launcher script:
```powershell
python run.py
```
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

### 3. Running Automated Pipeline Tests
To verify all database triggers, offline simulation, Sarvam 105B triage, translation, and Bulbul TTS:
```powershell
python test_prototype.py
```

---

## 🧪 Interactive Testing Walkthrough in the Web UI

1. **Simulate a Network-Dead Zone:**
   - In the top header bar, click **"Simulate Signal Loss (Go Offline)"**.
   - Notice the status pill turns red: `🔴 Offline (0 Queued on Edge)`.

2. **Submit an Emergency Report While Disconnected:**
   - On the left panel under **Citizen Reporter Device**, select a regional scenario (e.g. *Marathi Chiplun Flood* or *Hindi Kedarnath Landslide*).
   - Click **"Send Emergency SMS (Queue & Sync)"** or submit a voice memo.
   - Notice the report is immediately saved in the **Local Edge Queue** with badge `QUEUED ⏳`.
   - The Emergency Fusion Board on the right remains empty, proving zero data loss during network blackouts.

3. **Restore Connection:**
   - Click **"Restore Signal (Auto-Sync)"** in the top bar.
   - The sync engine instantly wakes up:
     1. Calls Sarvam 105B to extract urgency, location, and casualties.
     2. Calls Sarvam Translate to generate localized safety instructions.
     3. Calls Sarvam Bulbul TTS to synthesize a `.wav` voice advisory.
   - The card appears live on the **Emergency Fusion Board** with audio players and control room metadata!
   - The citizen's inbox receives the translated advisory and spoken voice audio.

