"""Gnani Timbre v2.5 realtime audio chunks over WebSocket."""
import base64, json, os

async def synthesize_chunks(text: str, language="hi-IN", speed=1.0):
    key = os.getenv("GNANI_API_KEY", "")
    if not key: raise RuntimeError("GNANI_API_KEY is required for real TTS")
    try: import websockets
    except ImportError as exc: raise RuntimeError("Install the optional websockets dependency for live TTS") from exc
    headers = {"X-API-Key-ID":key}
    async with websockets.connect(os.getenv("GNANI_TTS_WS_URL","wss://api.vachana.ai/api/v1/tts"), additional_headers=headers, max_size=2**22) as ws:
        await ws.send(json.dumps({"text":text,"voice":"Nalini","model":"timbre-v2.5","language":language,"speed":speed,"audio_config":{"sample_rate":16000,"num_channels":1,"sample_width":2,"encoding":"linear_pcm","container":"raw"}}))
        async for raw in ws:
            event = json.loads(raw)
            payload = event.get("data", {})
            if event.get("type") == "error": raise RuntimeError(event.get("message", "TTS synthesis failed"))
            audio = payload.get("audio") or event.get("audio") or event.get("audio_chunk")
            if audio: yield base64.b64decode(audio)
            if event.get("type") == "complete" or payload.get("is_final") or event.get("is_final"): break
