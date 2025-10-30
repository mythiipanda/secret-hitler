import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")
client = genai.Client(api_key=API_KEY)

def call_model(prompt: str, model: str | None = None) -> str:
    m = model or DEFAULT_MODEL
    resp = client.models.generate_content(model=m, contents=prompt)
    return resp.text