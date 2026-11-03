import base64
import json
import os
import re
from typing import Any, Dict, Optional, Tuple
from dotenv import load_dotenv
from sarvamai import SarvamAI

# Load .env configuration
load_dotenv()

# Language map for Sarvam BCP 47 codes
LANGUAGE_CODE_MAP = {
    "hindi": "hi-IN",
    "marathi": "mr-IN",
    "bengali": "bn-IN",
    "tamil": "ta-IN",
    "telugu": "te-IN",
    "kannada": "kn-IN",
    "gujarati": "gu-IN",
    "punjabi": "pa-IN",
    "malayalam": "ml-IN",
    "odia": "od-IN",
    "english": "en-IN",
}

def get_sarvam_client() -> SarvamAI:
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise ValueError("SARVAM_API_KEY environment variable is not set.")
    return SarvamAI(api_subscription_key=api_key)

def resolve_language_code(language_name: str) -> str:
    cleaned = (language_name or "").strip().lower()
    for name, code in LANGUAGE_CODE_MAP.items():
        if name in cleaned:
            return code
    return "hi-IN" # Default fallback for pan-Indian voice advisories

def transcribe_audio(audio_path: str, model: str = "saaras:v3") -> str:
    """
    Transcribes regional audio recordings (missed calls / voice memos) using Sarvam Saaras STT.
    """
    client = get_sarvam_client()
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found at: {audio_path}")
    
    with open(audio_path, "rb") as audio_file:
        response = client.speech_to_text.transcribe(
            file=audio_file,
            model=model,
            mode="transcribe"
        )
        return (response.transcript or "").strip()

def triage_report(raw_text: str) -> Dict[str, Any]:
    """
    Analyzes raw emergency SMS or voice transcription using Sarvam 105B.
    Extracts structured emergency metadata: category, urgency, location, casualties, and safety advice.
    """
    client = get_sarvam_client()
    
    prompt = f"""You are an emergency disaster response triage AI operating on raw citizen reports.
Analyze the following emergency message which may be in Hindi, Marathi, Bengali, Tamil, Telugu, Hinglish, or other Indian languages.

Citizen Message:
\"\"\"{raw_text}\"\"\"

Output ONLY a valid JSON object with the following fields:
{{
  "category": "flood" | "fire" | "medical" | "building_collapse" | "landslide" | "trapped" | "other",
  "urgency": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  "location": "<extracted village, town, landmark or street, or 'Unknown'>",
  "affected_count": <estimated number of affected people as integer, default 1>,
  "detected_language": "<e.g. Hindi, Marathi, Bengali, Tamil, English, etc.>",
  "english_summary": "<clear, concise 1-2 sentence emergency summary in English for the disaster control room>",
  "regional_safety_advice": "<immediate life-saving 1-2 sentence safety instructions for the citizen in English>"
}}
Do not include any commentary or explanation outside the JSON."""

    completion = client.chat.completions(
        model="sarvam-105b-conversations",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )
    
    content = completion.choices[0].message.content.strip()
    
    # Strip markdown code fences if present
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except Exception:
            pass

    # Fallback structure if parsing fails
    return {
        "category": "emergency_general",
        "urgency": "HIGH",
        "location": "Reported Area",
        "affected_count": 1,
        "detected_language": "Hindi",
        "english_summary": raw_text[:120],
        "regional_safety_advice": "Stay in a safe location, keep communication lines open, and await emergency response teams."
    }

def translate_to_regional(text: str, target_language_code: str) -> str:
    """
    Translates emergency advice into the caller's regional language via Sarvam Translate.
    """
    if target_language_code == "en-IN":
        return text
        
    client = get_sarvam_client()
    try:
        res = client.text.translate(
            input=text,
            source_language_code="en-IN",
            target_language_code=target_language_code
        )
        return (res.translated_text or text).strip()
    except Exception as e:
        print(f"Warning: Sarvam translation failed: {e}. Falling back to original text.")
        return text

def synthesize_voice_advisory(text: str, language_code: str, output_filepath: str) -> bool:
    """
    Converts regional safety instructions into natural spoken voice using Sarvam Bulbul TTS.
    Saves audio to output_filepath.
    """
    client = get_sarvam_client()
    try:
        res = client.text_to_speech.convert(
            text=text,
            language_code=language_code
        )
        if res.audios and len(res.audios) > 0:
            audio_bytes = base64.b64decode(res.audios[0])
            os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
            with open(output_filepath, "wb") as f:
                f.write(audio_bytes)
            return True
        return False
    except Exception as e:
        print(f"Warning: Sarvam TTS failed: {e}")
        return False

