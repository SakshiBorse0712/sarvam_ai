import os
import shutil
import time
from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import database, sarvam_service
from .sync_engine import AUDIO_DIR, engine

# Initialize SQLite database
database.init_db()

app = FastAPI(title="Offline-First Citizen Reporter", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# Preset Voice Scenarios for Instant Testing
VOICE_PRESETS = {
    "flood_marathi": {
        "title": "🌧️ Chiplun Flood Rescue (Marathi)",
        "phone": "+91 98201 12345",
        "text": "चिपळूण बाजार पेठेत पुराचे पाणी शिरले आहे, आम्ही घराच्या छतावर अडकलो आहोत, ४ लोक आहेत. मदत त्वरित पाठवा.",
        "lang_code": "mr-IN"
    },
    "landslide_hindi": {
        "title": "⛰️ Kedarnath Landslide Alert (Hindi)",
        "phone": "+91 94120 54321",
        "text": "केदारनाथ मार्ग पर भूस्खलन हुआ है, पत्थर गिरने से रास्ता बंद है और 15 लोग फंसे हैं, जल्दी सहायता भेजें।",
        "lang_code": "hi-IN"
    },
    "cyclone_bengali": {
        "title": "🌪️ Sundarbans Embankment Breach (Bengali)",
        "phone": "+91 93300 78901",
        "text": "সুন্দরবনের বাঁধ ভেঙে গ্রামে নোনা জল ঢুকছে, বহু পরিবার গৃহহীন হয়েছে, উদ্ধারকারী নৌকা পাঠান।",
        "lang_code": "bn-IN"
    },
    "medical_tamil": {
        "title": "🩺 Tambaram Submerged Hospital (Tamil)",
        "phone": "+91 94440 67890",
        "text": "தாம்பரம் மருத்துவமனை பகுதியில் வெள்ள நீர் சூழ்ந்துள்ளது, அவசர ஆம்புலன்ஸ் மற்றும் படகு தேவை.",
        "lang_code": "ta-IN"
    }
}

class SMSReportRequest(BaseModel):
    phone: str
    message: str

class AdvisoryRequest(BaseModel):
    message_en: str

class StatusUpdateRequest(BaseModel):
    status: str

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Offline-First Citizen Reporter Backend Ready</h1>"

@app.get("/api/network-status")
async def get_network_status():
    queue_items = database.get_all_queue()
    pending = [q for q in queue_items if q["status"] == "QUEUED"]
    incidents = database.get_all_incidents()
    advisories = database.get_all_advisories()
    
    return {
        "online": engine.is_online(),
        "is_syncing": engine.is_syncing(),
        "pending_count": len(pending),
        "total_queue": len(queue_items),
        "total_incidents": len(incidents),
        "total_advisories": len(advisories)
    }

@app.post("/api/network-toggle")
async def toggle_network():
    new_state = not engine.is_online()
    engine.set_online(new_state)
    return {"online": engine.is_online()}

@app.post("/api/citizen/sms")
async def submit_sms_report(data: SMSReportRequest):
    if not data.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    phone = data.phone.strip() or "+91 98000 00000"
    queue_id = database.add_to_queue(
        report_type="sms",
        caller_phone=phone,
        raw_content=data.message.strip(),
        audio_filename=None
    )
    
    # If online, sync immediately in background
    if engine.is_online():
        import threading
        threading.Thread(target=engine.sync_pending_reports, daemon=True).start()

    return {
        "success": True,
        "queue_id": queue_id,
        "online": engine.is_online(),
        "status": "QUEUED" if not engine.is_online() else "SYNCING"
    }

@app.post("/api/citizen/voice")
async def submit_voice_report(
    phone: str = Form("+91 98000 00000"),
    file: UploadFile = File(...)
):
    extension = os.path.splitext(file.filename or "")[1] or ".wav"
    audio_filename = f"caller_{int(time.time())}_{file.filename}"
    save_path = os.path.join(AUDIO_DIR, audio_filename)
    
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    queue_id = database.add_to_queue(
        report_type="voice",
        caller_phone=phone,
        raw_content="[Voice Memo Recorded]",
        audio_filename=audio_filename
    )

    if engine.is_online():
        import threading
        threading.Thread(target=engine.sync_pending_reports, daemon=True).start()

    return {
        "success": True,
        "queue_id": queue_id,
        "audio_filename": audio_filename,
        "online": engine.is_online()
    }

@app.post("/api/citizen/preset-voice")
async def submit_preset_voice(preset_key: str = Form(...)):
    if preset_key not in VOICE_PRESETS:
        raise HTTPException(status_code=400, detail="Invalid preset key")

    preset = VOICE_PRESETS[preset_key]
    audio_filename = f"preset_{preset_key}_{int(time.time())}.wav"
    save_path = os.path.join(AUDIO_DIR, audio_filename)

    # Synthesize realistic regional distress audio using Sarvam TTS
    tts_ok = sarvam_service.synthesize_voice_advisory(
        text=preset["text"],
        language_code=preset["lang_code"],
        output_filepath=save_path
    )

    queue_id = database.add_to_queue(
        report_type="voice",
        caller_phone=preset["phone"],
        raw_content=preset["text"],
        audio_filename=audio_filename if tts_ok else None
    )

    if engine.is_online():
        import threading
        threading.Thread(target=engine.sync_pending_reports, daemon=True).start()

    return {
        "success": True,
        "queue_id": queue_id,
        "title": preset["title"],
        "audio_filename": audio_filename if tts_ok else None,
        "online": engine.is_online()
    }

@app.post("/api/sync")
async def trigger_sync():
    if not engine.is_online():
        raise HTTPException(status_code=400, detail="Cannot sync while in offline mode. Reconnect first.")
    
    synced_ids = engine.sync_pending_reports()
    return {"success": True, "synced_incidents": synced_ids}

@app.get("/api/queue")
async def get_queue():
    return database.get_all_queue()

@app.get("/api/incidents")
async def get_incidents():
    return database.get_all_incidents()

@app.get("/api/advisories")
async def get_advisories():
    return database.get_all_advisories()

@app.post("/api/incident/{incident_id}/status")
async def update_status(incident_id: int, data: StatusUpdateRequest):
    database.update_incident_status(incident_id, data.status)
    return {"success": True, "incident_id": incident_id, "new_status": data.status}

@app.post("/api/incident/{incident_id}/send-advisory")
async def broadcast_custom_advisory(incident_id: int, data: AdvisoryRequest):
    incidents = database.get_all_incidents()
    target = next((inc for inc in incidents if inc["id"] == incident_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Incident not found")

    detected_lang = target["detected_language"]
    lang_code = sarvam_service.resolve_language_code(detected_lang)
    
    # Translate English responder message into caller's regional language
    regional_text = sarvam_service.translate_to_regional(data.message_en, lang_code)
    
    # Generate Voice via Bulbul TTS
    advisory_audio_filename = f"custom_advisory_{incident_id}_{int(time.time())}.wav"
    advisory_path = os.path.join(AUDIO_DIR, advisory_audio_filename)
    tts_ok = sarvam_service.synthesize_voice_advisory(
        regional_text,
        lang_code,
        advisory_path
    )
    
    saved_audio = advisory_audio_filename if tts_ok else None
    
    advisory_id = database.add_advisory(
        incident_id=incident_id,
        caller_phone=target["caller_phone"],
        channel="BOTH" if saved_audio else "SMS",
        language=detected_lang,
        message_text=regional_text,
        audio_file=saved_audio
    )
    
    return {
        "success": True,
        "advisory_id": advisory_id,
        "regional_text": regional_text,
        "audio_file": saved_audio
    }

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    file_path = os.path.join(AUDIO_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Audio file not found")

