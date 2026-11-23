import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
CANDIDATE_MODELS = [PRIMARY_MODEL, "gemini-3.5-flash", "gemini-3.5-flash-lite"]

if not API_KEY:
    raise RuntimeError("Gemini API key missing")

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(
        timeout=25000
    )
)


def generate_ai_response(prompt, max_retries=3):
    last_error = None

    for model in CANDIDATE_MODELS:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                if response and response.text:
                    return response.text
                raise RuntimeError("Gemini returned an empty response.")
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # If transient error (503, 504, overloaded, deadline), retry after backoff
                if any(x in err_str for x in ["503", "504", "deadline", "unavailable", "demand", "resource_exhausted"]):
                    time.sleep(1.0 * (attempt + 1))
                    continue
                # If model not found or permanent, switch to next model
                break

    raise RuntimeError(f"Gemini AI processing error: {last_error}")
