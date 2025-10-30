import os
from dotenv import load_dotenv
from google import genai
from typing import Iterator, Optional, List

load_dotenv()

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

_base_client = genai.Client(api_key=API_KEY)


class LLMClient:
    """
    Per-agent LLM client wrapper. Keeps agent-specific metadata (name, model, tags)
    and exposes call/stream methods. By default reuses the base client but can be
    configured with a distinct api_key to create a truly separate client.
    """

    def __init__(self, agent_name: str, model: Optional[str] = None, api_key: Optional[str] = None, tags: Optional[List[str]] = None):
        self.agent_name = agent_name
        self.model = model or DEFAULT_MODEL
        self.tags = tags or []
        # create an independent client only if a specific api_key is provided
        self._client = genai.Client(api_key=api_key) if api_key else _base_client

    def call(self, prompt: str, model: Optional[str] = None) -> str:
        m = model or self.model
        resp = self._client.models.generate_content(model=m, contents=prompt)
        return getattr(resp, "text", str(resp))

    def stream(self, prompt: str, model: Optional[str] = None) -> Iterator[str]:
        m = model or self.model
        for chunk in self._client.models.generate_content_stream(model=m, contents=prompt):
            # handle variations in chunk shape defensively
            text = getattr(chunk, "text", None) or getattr(chunk, "content", None) or str(chunk)
            yield text


def call_model(prompt: str, model: Optional[str] = None) -> str:
    return LLMClient(agent_name="shared", model=model).call(prompt, model=model)


def stream_model(prompt: str, model: Optional[str] = None) -> Iterator[str]:
    yield from LLMClient(agent_name="shared", model=model).stream(prompt, model=model)