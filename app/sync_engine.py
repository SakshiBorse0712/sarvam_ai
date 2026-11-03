import os
import threading
import time
from typing import Any, Dict, List
from . import database, sarvam_service

AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio_storage")

class SyncEngine:
    def __init__(self):
        # Default state: simulated Online
        self._is_online: bool = True
        self._is_syncing: bool = False
        self._lock = threading.Lock()

    def set_online(self, online: bool):
        self._is_online = online
        if self._is_online:
            # Trigger background sync when reconnected
            threading.Thread(target=self.sync_pending_reports, daemon=True).start()

    def is_online(self) -> bool:
        return self._is_online

    def is_syncing(self) -> bool:
        return self._is_syncing

    def sync_pending_reports(self) -> List[int]:
        """
        Synchronizes all offline queued reports with Sarvam AI services
        and populates the Emergency Fusion Board.
        """
        if not self._is_online:
            return []

        with self._lock:
            self._is_syncing = True

        synced_incident_ids = []
        try:
            pending_items = database.get_pending_queue()
            for item in pending_items:
                if not self._is_online:
                    break

                queue_id = item["id"]
                database.update_queue_status(queue_id, "SYNCING")

                try:
                    raw_text = item["raw_content"] or ""
                    audio_filename = item["audio_filename"]
                    caller_audio_path = None

                    # Step 1: Transcribe Voice / Missed Call memo if voice report
                    if item["report_type"] in ["voice", "missed_call"] and audio_filename:
                        caller_audio_path = os.path.join(AUDIO_DIR, audio_filename)
                        if os.path.exists(caller_audio_path):
                            print(f"[SyncEngine] Transcribing audio memo for queue #{queue_id}...")
                            transcript = sarvam_service.transcribe_audio(caller_audio_path)
                            if transcript:
                                raw_text = transcript
                                print(f"[SyncEngine] Transcribed: {transcript}")

                    if not raw_text.strip():
                        raw_text = "Emergency assistance requested. Caller unable to speak."

                    # Step 2: Sarvam 105B AI Triage & Entity Extraction
                    print(f"[SyncEngine] Triaging report #{queue_id} with Sarvam 105B...")
                    triage = sarvam_service.triage_report(raw_text)
                    
                    category = triage.get("category", "emergency")
                    urgency = triage.get("urgency", "HIGH")
                    location = triage.get("location", "Unknown Location")
                    affected_count = triage.get("affected_count", 1)
                    detected_language = triage.get("detected_language", "Hindi")
                    english_summary = triage.get("english_summary", raw_text)
                    safety_advice_en = triage.get("regional_safety_advice", "Please remain calm and move to safe higher ground.")

                    # Step 3: Regional Language Translation (Sarvam Translate)
                    lang_code = sarvam_service.resolve_language_code(detected_language)
                    print(f"[SyncEngine] Translating safety advice to {detected_language} ({lang_code})...")
                    regional_advisory_text = sarvam_service.translate_to_regional(safety_advice_en, lang_code)

                    # Step 4: Regional Voice Synthesis (Sarvam Bulbul TTS)
                    advisory_audio_filename = f"advisory_{queue_id}_{int(time.time())}.wav"
                    advisory_audio_path = os.path.join(AUDIO_DIR, advisory_audio_filename)
                    print(f"[SyncEngine] Synthesizing voice advisory via Bulbul TTS...")
                    tts_success = sarvam_service.synthesize_voice_advisory(
                        regional_advisory_text,
                        lang_code,
                        advisory_audio_path
                    )
                    saved_advisory_audio = advisory_audio_filename if tts_success else None

                    # Step 5: Store in Fusion Board Incidents
                    incident_id = database.create_incident(
                        queue_id=queue_id,
                        caller_phone=item["caller_phone"],
                        report_type=item["report_type"],
                        category=category,
                        urgency=urgency,
                        location=location,
                        affected_count=affected_count,
                        detected_language=detected_language,
                        original_text=raw_text,
                        english_summary=english_summary,
                        regional_advisory_text=regional_advisory_text,
                        advisory_audio_file=saved_advisory_audio,
                        caller_audio_file=audio_filename
                    )

                    # Step 6: Log Automated Regional Advisory back to Caller
                    database.add_advisory(
                        incident_id=incident_id,
                        caller_phone=item["caller_phone"],
                        channel="BOTH" if saved_advisory_audio else "SMS",
                        language=detected_language,
                        message_text=regional_advisory_text,
                        audio_file=saved_advisory_audio
                    )

                    database.update_queue_status(queue_id, "SYNCED")
                    synced_incident_ids.append(incident_id)
                    print(f"[SyncEngine] Successfully synced queue #{queue_id} -> Incident #{incident_id}")

                except Exception as e:
                    print(f"[SyncEngine] Error syncing queue #{queue_id}: {e}")
                    database.update_queue_status(queue_id, "FAILED", error_message=str(e))

        finally:
            with self._lock:
                self._is_syncing = False

        return synced_incident_ids

# Global SyncEngine instance
engine = SyncEngine()

