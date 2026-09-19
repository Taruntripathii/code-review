import json
import os
from abc import ABC, abstractmethod

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from backend.app.schemas import LLMFinding

load_dotenv()


class ReviewLLM(ABC):
    @abstractmethod
    def analyze(self, prompt: str) -> str: ...


class OllamaLLM(ReviewLLM):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=60.0, follow_redirects=True)

    def analyze(self, prompt: str) -> str:
        resp = self._client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()
        return resp.json()["response"]


class OpenAICompatibleLLM(ReviewLLM):
    """Works with any OpenAI-compatible API (e.g. api.iamhc.cn, vLLM, etc.)."""

    def __init__(self, base_url: str, model: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.model = model
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(timeout=60.0, follow_redirects=True, headers=headers)

    def analyze(self, prompt: str) -> str:
        resp = self._client.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def build_default_llm() -> ReviewLLM:
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    model = os.getenv("LLM_MODEL", "llama3")
    if "localhost" in base_url or "127.0.0.1" in base_url:
        return OllamaLLM(base_url=base_url, model=model)
    return OpenAICompatibleLLM(
        base_url=base_url,
        model=model,
        api_key=os.environ.get("LLM_API_KEY", ""),
    )


PROMPT_TEMPLATE = """You are a senior code reviewer. You will see ONLY the added lines of a diff chunk.

Rules:
- Only comment on lines that are actually shown below.
- Every finding must cite an exact line number from the "new_line" values given.
- Describe a CONCRETE failure scenario, not a vague style preference.
- If nothing in this chunk is worth flagging, return an empty list: []
- Do not invent issues to have something to say.

Output ONLY a JSON array, each item shaped like:
{{"file_path": "...", "line": <int>, "category": "bug|style|security", "explanation": "...", "confidence": <0.0-1.0>}}

File: {file_path}
Added lines:
{added_lines}
"""


def build_prompt(file_path: str, added_lines: list[dict]) -> str:
    lines_text = "\n".join(f"  new_line={line_data['new_line']}: {line_data['content']}" for line_data in added_lines)
    return PROMPT_TEMPLATE.format(file_path=file_path, added_lines=lines_text)


def parse_llm_output(raw: str, file_path: str) -> list[LLMFinding]:
    raw = raw.strip()
    if "\\n" in raw:
        raw = raw.replace("\\n", "\n").replace('\\"', '"')
    import re

    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    if fence_match:
        raw = fence_match.group(1).strip()

    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []  # malformed output → treat as "no findings"

    findings = []
    for item in items:
        try:
            findings.append(LLMFinding(**item))
        except ValidationError:
            continue
    return findings
