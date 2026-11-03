import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "offline_emergency.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Local Offline Queue (simulates device / edge gateway storage)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS offline_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_type TEXT NOT NULL,         -- 'sms', 'voice', 'missed_call'
        caller_phone TEXT NOT NULL,
        raw_content TEXT,                  -- SMS text or audio transcript note
        audio_filename TEXT,               -- relative path in audio_storage
        status TEXT DEFAULT 'QUEUED',       -- 'QUEUED', 'SYNCING', 'SYNCED', 'FAILED'
        error_message TEXT,
        created_at TEXT NOT NULL,
        synced_at TEXT
    );
    """)

    # 2. Emergency Fusion Board Incidents (central command records)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        queue_id INTEGER,
        caller_phone TEXT NOT NULL,
        report_type TEXT NOT NULL,
        category TEXT NOT NULL,            -- 'flood', 'fire', 'medical', 'structural', 'trapped', 'other'
        urgency TEXT NOT NULL,             -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
        location TEXT,
        affected_count INTEGER DEFAULT 1,
        detected_language TEXT,
        original_text TEXT NOT NULL,
        english_summary TEXT NOT NULL,
        regional_advisory_text TEXT,
        advisory_audio_file TEXT,          -- path to generated regional TTS wav
        caller_audio_file TEXT,            -- path to caller's original voice memo
        status TEXT DEFAULT 'NEW',         -- 'NEW', 'ASSIGNED', 'DISPATCHED', 'RESOLVED'
        created_at TEXT NOT NULL,
        FOREIGN KEY (queue_id) REFERENCES offline_queue(id)
    );
    """)

    # 3. Outgoing Automated Advisories Log (delivered back to citizen)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS advisories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER,
        caller_phone TEXT NOT NULL,
        channel TEXT NOT NULL,             -- 'SMS', 'VOICE_IVR', 'BOTH'
        language TEXT NOT NULL,
        message_text TEXT NOT NULL,
        audio_file TEXT,
        status TEXT DEFAULT 'DELIVERED',   -- 'DELIVERED', 'PLAYED'
        created_at TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES incidents(id)
    );
    """)

    conn.commit()
    conn.close()

# Queue Operations
def add_to_queue(report_type: str, caller_phone: str, raw_content: str = "", audio_filename: Optional[str] = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO offline_queue (report_type, caller_phone, raw_content, audio_filename, status, created_at)
        VALUES (?, ?, ?, ?, 'QUEUED', ?)
    """, (report_type, caller_phone, raw_content, audio_filename, created_at))
    queue_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return queue_id

def get_pending_queue() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM offline_queue WHERE status = 'QUEUED' ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def update_queue_status(queue_id: int, status: str, error_message: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    synced_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if status == 'SYNCED' else None
    cursor.execute("""
        UPDATE offline_queue 
        SET status = ?, error_message = ?, synced_at = ?
        WHERE id = ?
    """, (status, error_message, synced_at, queue_id))
    conn.commit()
    conn.close()

def get_all_queue() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM offline_queue ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

# Incident Operations
def create_incident(
    queue_id: int,
    caller_phone: str,
    report_type: str,
    category: str,
    urgency: str,
    location: str,
    affected_count: int,
    detected_language: str,
    original_text: str,
    english_summary: str,
    regional_advisory_text: str,
    advisory_audio_file: Optional[str],
    caller_audio_file: Optional[str]
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO incidents (
            queue_id, caller_phone, report_type, category, urgency, location,
            affected_count, detected_language, original_text, english_summary,
            regional_advisory_text, advisory_audio_file, caller_audio_file, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEW', ?)
    """, (
        queue_id, caller_phone, report_type, category, urgency, location,
        affected_count, detected_language, original_text, english_summary,
        regional_advisory_text, advisory_audio_file, caller_audio_file, created_at
    ))
    incident_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return incident_id

def get_all_incidents() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def update_incident_status(incident_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE incidents SET status = ? WHERE id = ?", (status, incident_id))
    conn.commit()
    conn.close()

# Advisory Operations
def add_advisory(incident_id: int, caller_phone: str, channel: str, language: str, message_text: str, audio_file: Optional[str] = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO advisories (incident_id, caller_phone, channel, language, message_text, audio_file, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'DELIVERED', ?)
    """, (incident_id, caller_phone, channel, language, message_text, audio_file, created_at))
    advisory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return advisory_id

def get_all_advisories() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM advisories ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

