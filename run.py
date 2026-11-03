import sys
import uvicorn

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    print("=====================================================================")
    print(" [OFFLINE-FIRST CITIZEN REPORTER & EMERGENCY FUSION BOARD]")
    print(" Powered by Sarvam AI (Indic STT, 105B Triage, Translate & Bulbul TTS)")
    print(" Server launching at: http://127.0.0.1:8000")
    print("=====================================================================")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")
