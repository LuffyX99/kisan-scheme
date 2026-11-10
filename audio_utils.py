"""Small PCM helpers for telephony clips and low-volume input."""
import array, io, math, wave

def pcm16_mono_rms(pcm: bytes) -> float:
    usable = pcm[:len(pcm)//2*2]
    samples = array.array("h"); samples.frombytes(usable)
    if not samples: return 0.0
    return math.sqrt(sum(x*x for x in samples)/len(samples))/32768

def normalize_pcm16(pcm: bytes, target_rms=0.08, max_gain=8.0) -> bytes:
    """Moderate gain for quiet recordings without hard-gating low-volume speech."""
    usable=pcm[:len(pcm)//2*2]; samples=array.array("h"); samples.frombytes(usable)
    rms=pcm16_mono_rms(usable)
    if rms < 1e-6: return usable
    gain=min(max_gain,target_rms/rms)
    for i,value in enumerate(samples): samples[i]=max(-32768,min(32767,int(value*gain)))
    return samples.tobytes()

def is_speech_frame(pcm: bytes, threshold=0.002) -> bool:
    # Conservative local VAD hint; low-level frames are still retained and sent.
    return pcm16_mono_rms(pcm) >= threshold

def prepare_wav(audio: bytes) -> bytes:
    """Validate a browser WAV, convert it to mono PCM16 and gently lift quiet audio."""
    with wave.open(io.BytesIO(audio), "rb") as reader:
        channels, width, rate = reader.getnchannels(), reader.getsampwidth(), reader.getframerate()
        frames=reader.readframes(reader.getnframes())
    if width != 2: raise ValueError("Expected 16-bit PCM WAV audio")
    if channels > 1:
        raw=array.array("h"); raw.frombytes(frames); mono=array.array("h")
        for i in range(0,len(raw)-channels+1,channels): mono.append(int(sum(raw[i:i+channels])/channels))
        frames=mono.tobytes()
    frames=normalize_pcm16(frames)
    out=io.BytesIO()
    with wave.open(out,"wb") as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(rate); writer.writeframes(frames)
    return out.getvalue()
