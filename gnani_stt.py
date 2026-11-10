"""Gnani Prisma v2.5 adapters. WebSocket stream accepts raw mono PCM16 frames."""
import json, os, io, wave

async def transcribe_audio(audio_bytes: bytes, filename="farmer.wav", language="hi-IN") -> tuple[str, float]:
    """Stream a buffered browser utterance to the Prisma v2.5 realtime endpoint."""
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("Prisma streaming expects mono PCM16 WAV")
        rate = wav.getframerate()
        if rate not in (8000,16000): raise ValueError("Prisma streaming expects 8 kHz or 16 kHz audio")
        pcm = wav.readframes(wav.getnframes())
    async def frames():
        for offset in range(0,len(pcm),1024):
            chunk=pcm[offset:offset+1024]
            yield chunk + bytes(1024-len(chunk)) if len(chunk)<1024 else chunk
    import time
    started=time.perf_counter(); transcript=""
    async for event in transcribe_pcm_stream(frames(), language_code=language, sample_rate=rate):
        if event.get("type")=="transcript": transcript=event.get("text",transcript)
        elif event.get("type")=="error": raise RuntimeError(event.get("message","Prisma transcription failed"))
    return transcript, round(time.perf_counter()-started,3)

async def transcribe_pcm_stream(frames, language_code="indic-auto", sample_rate=16000):
    """Yield transcript events. Frames are 1024-byte PCM16 mono chunks, sent at real-time cadence."""
    key = os.getenv("GNANI_API_KEY", "")
    if not key: raise RuntimeError("GNANI_API_KEY is required for real STT")
    try: import websockets
    except ImportError as exc: raise RuntimeError("Install the optional websockets dependency for streaming STT") from exc
    headers = {"x-api-key-id":key,"model":"prisma-v2.5","language_code":language_code,"x-sample-rate":str(sample_rate),"x-vad-threshold":"0.35","x-min-silence-ms":"450"}
    async with websockets.connect(os.getenv("GNANI_STT_WS_URL","wss://api.vachana.ai/stt/v3/stream"), additional_headers=headers, max_size=2**20) as ws:
        async def sender():
            async for frame in frames:
                await ws.send(frame)
                import asyncio
                await asyncio.sleep(512/sample_rate)
            await ws.send(json.dumps({"type":"commit"}))
        import asyncio
        task = asyncio.create_task(sender())
        try:
            while True:
                raw=await asyncio.wait_for(ws.recv(),timeout=30)
                event=json.loads(raw)
                if event.get("type") in ("transcript","error"): yield event
                if event.get("type")=="error" or (event.get("type")=="transcript" and event.get("is_final",True)): break
        finally: await task
