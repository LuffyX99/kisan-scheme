import json, os
import httpx
from backend.prompts import SLOT_SYSTEM_PROMPT, RESULT_SYSTEM_PROMPT

async def _chat(system: str, user: str) -> str:
    base = os.getenv("EVON_BASE_URL", "").rstrip("/")
    if not base: raise RuntimeError("Set EVON_BASE_URL to an Evon-compatible endpoint")
    headers = {"Authorization": f"Bearer {os.getenv('EVON_API_KEY') or os.getenv('GNANI_API_KEY', '')}"}
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(f"{base}/chat/completions", headers=headers, json={"model":os.getenv("EVON_MODEL", "gnani/gnani-evon-v3.3-30B-A3B"),"temperature":0,"messages":[{"role":"system","content":system},{"role":"user","content":user}]})
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

async def extract_slots(text: str) -> dict:
    raw = await _chat(SLOT_SYSTEM_PROMPT, text)
    raw = raw.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(raw)

async def rephrase_approved_facts(language: str, facts: dict) -> str:
    return await _chat(RESULT_SYSTEM_PROMPT, json.dumps({"language":language,"approved_facts":facts}, ensure_ascii=False))
