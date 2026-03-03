"""
Shared configuration for all agents.
"""

import os
import ssl

import certifi
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL: str = os.environ.get("AGENTS_GEMINI_MODEL", "gemini-2.5-flash")

PORT: int = int(os.environ.get("AGENTS_PORT", 4001))

# Path to the SQLite database file (sits next to this module)
DB_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents.db")

CORS_HEADERS: dict = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

# SSL context shared across all async HTTP clients
ssl_ctx = ssl.create_default_context(cafile=certifi.where())
