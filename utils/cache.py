import sqlite3
import hashlib
from typing import Optional

DB_FILE = "video_cache.db"

def init_cache():
    """Initialize the cache database table."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS video_cache (
            url_hash TEXT PRIMARY KEY,
            file_id TEXT,
            original_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_url_hash(url: str) -> str:
    """Generate a consistent hash for a URL."""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def get_cached_file_id(url: str) -> Optional[str]:
    """Retrieve a file_id if it exists in the cache."""
    url_hash = get_url_hash(url)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT file_id FROM video_cache WHERE url_hash = ?', (url_hash,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def save_to_cache(url: str, file_id: str):
    """Save a file_id to the cache."""
    url_hash = get_url_hash(url)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        'INSERT OR REPLACE INTO video_cache (url_hash, file_id, original_url) VALUES (?, ?, ?)',
        (url_hash, file_id, url)
    )
    conn.commit()
    conn.close()
