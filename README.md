# Kisan Mitra

Voice-first Indian government scheme finder demo for the Gnani AI Great Indian AI Internship Challenge. The demo runs in **mock mode without API keys**. The eligibility engine is deterministic Python over local JSON; Evon cannot choose schemes or eligibility.

## Run locally

Requirements: Python 3.11+ and a modern mobile/desktop browser. Microphone access requires `localhost` or HTTPS.

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # Windows PowerShell: Copy-Item .env.example .env
uvicorn backend.main:app --reload --port 8001
```

Open [http://localhost:8001](http://localhost:8001). `MOCK_MODE=true` is the default: type a reply, or use browser speech recognition when available. Browser speech synthesis reads the responses aloud.

## Live Gnani mode

Set `MOCK_MODE=false` and `GNANI_API_KEY` in `.env`. Set `EVON_BASE_URL` to an OpenAI-compatible endpoint serving `gnani/gnani-evon-v3.3-30B-A3B` and set `EVON_API_KEY` if required. The browser sends a complete mono WAV utterance to the backend; the backend strips the WAV container, paces PCM16 frames, and streams them to Prisma v2.5 over its documented realtime WebSocket. Timbre v2.5 streams raw PCM chunks back over this app's WebSocket for playback. Audio is converted to mono PCM16 at 16 kHz and gently normalized. Evon API access may require a hosted endpoint or self-hosting; the hosted Evon API has had gated availability. See the [Evon model card](https://huggingface.co/gnani/gnani-evon-v3.3-30B-A3B).

```bash
# Set in .env; start your Evon-compatible server separately (for example vLLM):
vllm serve gnani/gnani-evon-v3.3-30B-A3B
```

The server uses a configurable Prisma websocket endpoint (`GNANI_STT_WS_URL`). The model is used for strict JSON slot extraction only. Output rendering uses the rules engine and saved scheme entries; unsupported/malformed model responses fall back to deterministic extraction.

## Architecture

```text
Phone browser
  ├─ microphone → mono PCM WAV → FastAPI /ws/voice
  ├─ mock: text / browser speech recognition → browser speech synthesis
  └─ live: captured audio → Prisma v2.5 STT → transcript
                                           ↓
                                  slot_filler.py
                                  ├─ heuristics + Evon JSON extraction
                                  └─ missing slot? ask one short question
                                           ↓
                            eligibility.py + data/schemes.json
                                           ↓
                             approved result facts → response
                                           ↓
                         Timbre v2.5 audio chunks → phone
```

## Conversation and safeguards

- Collects language, state, crop, acres, land ownership, bank account and Aadhaar-linked phone one missing item at a time.
- Eligibility is rule-based. The model does not select schemes, amounts, documents or outcomes.
- Presents up to three likely/maybe matches, then offers documents and a mocked SMS summary. “Final eligibility is decided by the government office” is included in the scheme result.
- Supports repeat, slower, next scheme, yes/no follow-ups, silence timeout, and a fresh recording while prior speech is playing (barge-in).
- Browser audio capture uses echo cancellation, noise suppression and auto gain when supported. Server normalization avoids hard-gating quiet input. For real telephony deployments, feed 8/16 kHz mono PCM into the streaming adapter and validate codecs with the carrier.
- `/webhooks/twilio` and `/webhooks/exotel` are routing stubs, not a provisioned phone service.
- Logs per-turn and STT/TTS latency. No farmer profile is written to a database.

## Tests

```bash
python -m unittest discover -s backend/tests -v
```

Tests cover 15 farmer profiles, Karnataka scheme filtering, Hinglish (`do acre mein dhaan lagaya hai`), Kannada code-switching, and synthetic low-volume noisy PCM. The noise test checks that the preprocessing retains and boosts quiet frames; it does not claim a measured STT word-error rate.

## 60-second Hindi demo script

**Assistant:** नमस्ते किसान मित्र। आप किस राज्य में रहते हैं?

**Farmer:** कर्नाटक में। दो एकड़ में धान लगाता हूँ, जमीन मेरी है।

**Assistant:** आपके नाम से बैंक खाता है?

**Farmer:** हाँ।

**Assistant:** क्या आधार से जुड़ा मोबाइल नंबर चालू है?

**Farmer:** हाँ।

**Assistant:** पीएम-किसान में आपकी पात्रता की संभावना है। पात्र परिवार को साल में छह हजार रुपये मिलते हैं। क्या अगली योजना या दस्तावेज़ सुनें? अंतिम पात्रता सरकारी कार्यालय तय करेगा।

**Farmer:** दस्तावेज़ बताइए।

**Assistant:** आधार, जमीन का रिकॉर्ड और बैंक पासबुक तैयार रखें। क्या सारांश SMS से भेजूँ?

**Farmer:** हाँ।

**Assistant:** डेमो में SMS अनुरोध दर्ज हुआ। नजदीकी कृषि केंद्र से पुष्टि करें।

## Assumptions and official checks

- `data/schemes.json` is starter demo content, not an authoritative eligibility determination. A `null` `last_verified_date` means an entry has not been checked for the current cycle. For dated entries, confirm beneficiary rules and open application windows with the linked official source before applying.
- Recheck amounts, active application windows, notified crops/seasons, document lists and status on the linked central portals before any public launch. Tenant/sharecropper recognition and bank/Aadhaar requirements vary across schemes and states.
- Karnataka examples (Raitha Siri, Krishi Bhagya, Ganga Kalyana) are illustrative entries with no verification date. Confirm current scheme names, department, target groups, budget and application process with the Karnataka agriculture / welfare departments or a Raitha Samparka Kendra.
- Official launch checks: [PM-KISAN](https://pmkisan.gov.in/), [PMFBY](https://pmfby.gov.in/), [KCC scheme listing](https://www.myscheme.gov.in/schemes/kcc), [Soil Health Card](https://soilhealth.dac.gov.in/), [PM-KUSUM](https://pmkusum.mnre.gov.in/), [PMKSY](https://pmksy.gov.in/), [Karnataka Raitha Mitra](https://raitamitra.karnataka.gov.in/), [Karnataka KMDC](https://kmdc.karnataka.gov.in/).
- The demo uses simplified crop normalization and acres only; it does not gather district, season, caste/community, irrigation source, income, or land-record identifiers that real scheme screening may require.
- Live speech language selection uses the selected language where available; the first utterance provides a script-based language hint. Validate code-mixed accents and browser microphone permissions on target low-end Android devices.
