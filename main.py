import asyncio, base64, json, logging, os, time
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from backend.eligibility import evaluate
from backend.slot_filler import merge_utterance, missing_slots
from backend.gnani_stt import transcribe_audio
from backend.gnani_tts import synthesize_chunks
from backend.audio_utils import prepare_wav

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
MOCK = os.getenv("MOCK_MODE", "true").lower() == "true"
FRONT = Path(__file__).resolve().parents[1] / "frontend"
app = FastAPI(title="Kisan Mitra", description="Voice-first farmer scheme guide")
app.mount("/assets", StaticFiles(directory=FRONT), name="assets")

QUESTIONS = {
 "language": {"hi":"आप कौन सी भाषा में बात करना चाहेंगे?","hinglish":"Aap kaunsi language mein baat karna chahenge?","kn":"ನೀವು ಯಾವ ಭಾಷೆಯಲ್ಲಿ ಮಾತನಾಡಲು ಇಷ್ಟಪಡುತ್ತೀರಿ?","ta":"நீங்கள் எந்த மொழியில் பேச விரும்புகிறீர்கள்?","te":"మీరు ఏ భాషలో మాట్లాడాలనుకుంటున్నారు?","mr":"तुम्हाला कोणत्या भाषेत बोलायचे आहे?"},
 "state": {"hi":"आप किस राज्य में रहते हैं?","hinglish":"Aap kis state mein rehte hain?","kn":"ನೀವು ಯಾವ ರಾಜ್ಯದಲ್ಲಿ ವಾಸಿಸುತ್ತೀರಿ?","ta":"நீங்கள் எந்த மாநிலத்தில் வசிக்கிறீர்கள்?","te":"మీరు ఏ రాష్ట్రంలో ఉంటారు?","mr":"तुम्ही कोणत्या राज्यात राहता?"},
 "crop": {"hi":"आप कौन सी फसल उगाते हैं?","hinglish":"Aap kaunsi fasal ugate hain?","kn":"ನೀವು ಯಾವ ಬೆಳೆ ಬೆಳೆಯುತ್ತೀರಿ?","ta":"நீங்கள் என்ன பயிர் செய்கிறீர்கள்?","te":"మీరు ఏ పంట పండిస్తారు?","mr":"तुम्ही कोणते पीक घेता?"},
 "land_size_acres": {"hi":"आपके पास कितने एकड़ जमीन है?","hinglish":"Aapke paas kitne acre zameen hai?","kn":"ನಿಮ್ಮ ಬಳಿ ಎಷ್ಟು ಎಕರೆ ಜಮೀನಿದೆ?","ta":"உங்களிடம் எத்தனை ஏக்கர் நிலம் உள்ளது?","te":"మీకు ఎన్ని ఎకరాల భూమి ఉంది?","mr":"तुमच्याकडे किती एकर जमीन आहे?"},
 "land_ownership": {"hi":"जमीन आपकी है, किराये पर है, या बटाई पर?","hinglish":"Zameen aapki hai, kiraye par, ya batai par?","kn":"ಜಮೀನು ನಿಮ್ಮದೇ, ಗುತ್ತಿಗೆಯದ್ದೇ, ಅಥವಾ ಪಾಲಿನದ್ದೇ?","ta":"நிலம் சொந்தமா, குத்தகையா, அல்லது பங்கா?","te":"భూమి మీ సొంతమా, కౌలుదా, లేక భాగస్వామ్యమా?","mr":"जमीन स्वतःची, भाड्याची की वाट्याने कसता?"},
 "has_bank_account": {"hi":"क्या आपके नाम से बैंक खाता है?","hinglish":"Aapke naam ka bank account hai?","kn":"ನಿಮ್ಮ ಹೆಸರಿನಲ್ಲಿ ಬ್ಯಾಂಕ್ ಖಾತೆ ಇದೆಯೇ?","ta":"உங்கள் பெயரில் வங்கிக் கணக்கு உள்ளதா?","te":"మీ పేరుతో బ్యాంకు ఖాతా ఉందా?","mr":"तुमच्या नावावर बँक खाते आहे का?"},
 "has_aadhaar_linked_phone": {"hi":"क्या आधार से जुड़ा मोबाइल नंबर चालू है?","hinglish":"Aadhaar se linked mobile number chalu hai?","kn":"ಆಧಾರ್‌ಗೆ ಜೋಡಿಸಿದ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ಸಕ್ರಿಯವಾಗಿದೆಯೇ?","ta":"ஆதாருடன் இணைத்த கைபேசி எண் செயலிலா?","te":"ఆధార్‌కు లింక్ చేసిన మొబైల్ పనిచేస్తోందా?","mr":"आधारशी जोडलेला मोबाइल क्रमांक सुरू आहे का?"}}
GREET={"hi":"नमस्ते किसान मित्र। योजना जानने के लिए बताइए, आप कहाँ खेती करते हैं?","hinglish":"Namaste Kisan Mitra. Scheme dekhne ke liye batayein, aap kahan kheti karte hain?","kn":"ನಮಸ್ಕಾರ ರೈತ ಮಿತ್ರ. ಯೋಜನೆ ತಿಳಿಯಲು, ನೀವು ಎಲ್ಲಿ ಕೃಷಿ ಮಾಡುತ್ತೀರಿ?","ta":"வணக்கம் கிசான் மித்ரா. திட்டங்களை அறிய, நீங்கள் எங்கு விவசாயம் செய்கிறீர்கள்?","te":"నమస్కారం కిసాన్ మిత్ర. పథకాలు తెలుసుకోవడానికి, మీరు ఎక్కడ వ్యవసాయం చేస్తారు?","mr":"नमस्कार किसान मित्र. योजना जाणून घेण्यासाठी, तुम्ही कुठे शेती करता?"}
SORRY={"hi":"माफ कीजिए, मैं समझ नहीं पाया। फिर से बोलिए।","hinglish":"Maaf kijiye, samajh nahi aaya. Ek baar phir boliye.","kn":"ಕ್ಷಮಿಸಿ, ಅರ್ಥವಾಗಲಿಲ್ಲ. ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ.","ta":"மன்னிக்கவும், புரியவில்லை. மீண்டும் சொல்லுங்கள்.","te":"క్షమించండి, అర్థం కాలేదు. మళ్లీ చెప్పండి.","mr":"माफ करा, समजले नाही. पुन्हा सांगा."}
DISCLAIMER={"hi":"अंतिम पात्रता सरकारी कार्यालय तय करेगा।","hinglish":"Final eligibility government office hi decide karega.","kn":"ಅಂತಿಮ ಅರ್ಹತೆಯನ್ನು ಸರ್ಕಾರಿ ಕಚೇರಿ ನಿರ್ಧರಿಸುತ್ತದೆ.","ta":"இறுதி தகுதியை அரசு அலுவலகம் தீர்மானிக்கும்.","te":"తుది అర్హతను ప్రభుత్వ కార్యాలయం నిర్ణయిస్తుంది.","mr":"अंतिम पात्रता सरकारी कार्यालय ठरवेल."}
LANG_CODES={"hi":"hi-IN","hinglish":"hi-en","kn":"kn-IN","ta":"ta-IN","te":"te-IN","mr":"mr-IN"}
CLARIFY={
 "state":{"hi":"कृपया राज्य का नाम बताइए, जैसे बिहार, महाराष्ट्र या कर्नाटक।","hinglish":"State ka naam boliye, jaise Bihar, Maharashtra ya Karnataka.","kn":"ದಯವಿಟ್ಟು ರಾಜ್ಯದ ಹೆಸರನ್ನು ಹೇಳಿ, ಉದಾಹರಣೆಗೆ ಕರ್ನಾಟಕ ಅಥವಾ ಮಹಾರಾಷ್ಟ್ರ.","ta":"மாநிலத்தின் பெயரைச் சொல்லுங்கள்; உதாரணம் தமிழ்நாடு அல்லது கர்நாடகம்.","te":"రాష్ట్రం పేరు చెప్పండి; ఉదాహరణకు తెలంగాణ లేదా ఆంధ్రప్రదేశ్.","mr":"कृपया राज्याचे नाव सांगा, उदाहरणार्थ महाराष्ट्र किंवा कर्नाटक."},
 "crop":{"hi":"फसल का नाम बताइए, जैसे धान, गेहूं, कपास या मक्का।","hinglish":"Fasal ka naam boliye, jaise dhan, gehun, cotton ya makka.","kn":"ಬೆಳೆಯ ಹೆಸರನ್ನು ಹೇಳಿ, ಉದಾಹರಣೆಗೆ ಭತ್ತ, ರಾಗಿ ಅಥವಾ ಹತ್ತಿ.","ta":"பயிரின் பெயரைச் சொல்லுங்கள்; உதாரணம் நெல், பருத்தி அல்லது மக்காச்சோளம்.","te":"పంట పేరు చెప్పండి; ఉదాహరణకు వరి, పత్తి లేదా మొక్కజొన్న.","mr":"पिकाचे नाव सांगा, उदाहरणार्थ भात, गहू, कापूस किंवा मका."},
 "land_size_acres":{"hi":"जमीन कितने एकड़ है, जैसे 2 एकड़ या दो एकड़?","hinglish":"Zameen kitne acre hai? Jaise 2 acre ya do acre.","kn":"ಜಮೀನು ಎಷ್ಟು ಎಕರೆ ಇದೆ? ಉದಾಹರಣೆಗೆ 2 ಎಕರೆ ಎಂದು ಹೇಳಿ.","ta":"நிலம் எத்தனை ஏக்கர்? உதாரணமாக 2 ஏக்கர் என்று சொல்லுங்கள்.","te":"భూమి ఎన్ని ఎకరాలు? ఉదాహరణకు 2 ఎకరాలు అని చెప్పండి.","mr":"जमीन किती एकर आहे? उदाहरणार्थ 2 एकर सांगा."},
 "land_ownership":{"hi":"कृपया एक विकल्प बताइए: जमीन अपनी है, किराये पर है, या बटाई पर?","hinglish":"Ek option boliye: apni zameen, kiraye par, ya batai par?","kn":"ಒಂದು ಆಯ್ಕೆ ಹೇಳಿ: ಸ್ವಂತ ಜಮೀನು, ಗುತ್ತಿಗೆ, ಅಥವಾ ಪಾಲಿನ ಕೃಷಿ?","ta":"ஒரு விருப்பத்தைச் சொல்லுங்கள்: சொந்த நிலம், குத்தகை அல்லது பங்காகச் சாகுபடி?","te":"ఒక ఎంపిక చెప్పండి: సొంత భూమి, కౌలు, లేదా భాగస్వామ్య సాగు?","mr":"एक पर्याय सांगा: स्वतःची जमीन, भाड्याने की वाट्याने कसता?"}
}

def msg(lang, key): return QUESTIONS.get(key,{}).get(lang, QUESTIONS.get(key,{}).get("hi", "कृपया बताइए।"))

def next_reply(state, command=None):
    slots=state["slots"]; lang=slots.get("language") or "hi"
    if command == "repeat" and state.get("last_reply"): return state["last_reply"]
    if command == "slower": state["speed"]=0.85; return state.get("last_reply") or GREET[lang]
    if command == "next" and state.get("results"):
        state["result_index"]+=1
        if state["result_index"] < len(state["results"]): return scheme_sentence(state["results"][state["result_index"]],lang)
        return "बस, यही योजनाएँ मिलीं। क्या दस्तावेज़ों की सूची सुनें?" if lang=="hi" else "Yahi schemes mili. Documents ki list sunni hai?"
    missing=missing_slots(slots)
    if missing:
        key=missing[0]
        if key=="language": slots["language"]="hi"; lang="hi"; key=missing[1] if len(missing)>1 else "state"
        return msg(lang,key)
    if state.get("results") is None:
        state["evaluation"]=evaluate(slots)
        state["results"]=[r for r in state["evaluation"] if r["status"]!="not eligible"]
        state["result_index"]=0
        state["offer_docs"]=True
        return result_intro(state["results"],lang)
    if command == "yes_sms": command = "docs" if state.get("offer_docs") else "sms" if state.get("offer_sms") else "yes"
    if command in ("docs","yes"):
        state["offer_docs"]=False
        docs=[]
        for result in state["results"][:3]: docs.extend(result["documents"])
        unique=list(dict.fromkeys(docs))
        if not unique: unique=["Aadhaar","Land record","Bank details"]
        state["checklist"]=unique
        state["offer_sms"]=True
        return ("दस्तावेज़: " + ", ".join(unique[:6]) + ". सूची मोबाइल पर भेजूँ?") if lang=="hi" else ("Documents: "+", ".join(unique[:6])+". SMS summary bhejun?")
    if command == "sms":
        state["offer_sms"]=False
        state["completed"]=True
        return "डेमो में संदेश भेजने का अनुरोध दर्ज हुआ। नजदीकी कृषि केंद्र से पुष्टि करें।" if lang=="hi" else "Demo mein SMS request noted. Krishi Kendra par confirm karein."
    if command == "no":
        if state.get("offer_docs"):
            state["offer_docs"]=False; state["offer_sms"]=True
            return "ठीक है। क्या योजना का सारांश SMS से भेजूँ?" if lang=="hi" else "Theek hai. SMS summary bhejun?"
        if state.get("offer_sms"):
            state["offer_sms"]=False
            state["completed"]=True
            return "ठीक है। मदद के लिए नजदीकी कृषि केंद्र जाएँ।" if lang=="hi" else "Theek hai. Madad ke liye Krishi Kendra jayein."
    return "कृपया हाँ या नहीं कहें।" if lang=="hi" else "Haan ya nahi batayein."

def scheme_sentence(result, lang):
    name=result["name"].get(lang,result["name"]["hi"]); benefit=result["benefit"].get(lang,result["benefit"]["hi"])
    return f"{name}: {benefit} स्थिति: {result['status']}."

def result_intro(results,lang):
    if not results: return "अभी मेल खाती योजना की पुष्टि नहीं हुई। कृषि केंद्र या CSC पर पूछें। " + DISCLAIMER[lang]
    first=results[:3]
    # Keep first turn brief. Detailed next schemes use the `next` command.
    lines=[scheme_sentence(r,lang) for r in first[:1]]
    lines.append("क्या अगली योजना सुनें, या दस्तावेज़ों की सूची?" if lang=="hi" else "Agli scheme ya documents ki list sunni hai?")
    lines.append(DISCLAIMER[lang])
    return " ".join(lines)

def classify_command(text):
    t=text.lower().strip()
    if any(x in t for x in ("repeat","फिर से","दोहराओ","ಮತ್ತೆ ಹೇಳು","மீண்டும்","మళ్లీ","पुन्हा")): return "repeat"
    if any(x in t for x in ("slower","धीरे","slow","ನಿಧಾನ","மெதுவா","నెమ్మదిగా")): return "slower"
    if any(x in t for x in ("next scheme","अगली योजना","ಮುಂದಿನ ಯೋಜನೆ","அடுத்த திட்டம்","తదుపరి పథకం")): return "next"
    if any(x in t for x in ("document","दस्तावेज","कागज","ಹೆಚ್ಚಿನ ದಾಖಲೆ","ஆவணம்","పత్రాలు")): return "docs"
    if any(x in t for x in ("sms","whatsapp","message","भेज","ಕಳುಹಿಸಿ","அனுப்பு","పంపండి")): return "sms"
    if t in ("no","नहीं","नही","ಬೇಡ","இல்லை","కాదు","नको"): return "no"
    if t in ("yes","haan","ha","haan ji","हाँ","हां","ಹೌದು","ஆம்","ஆமாம்","అవును","हो","होय"): return "yes_sms"
    return None

def fill_yes_no_answer(text, slots):
    t=text.strip().lower()
    yes={"yes","haan","ha","ji","haan ji","हाँ","हां","हूँ","हां जी","ಹೌದು","ஆம்","ஆமாம்","అవును","हो","होय"}
    no={"no","नहीं","नही","नाही","ಬೇಡ","இல்லை","கிடையாது","కాదు","లేదు"}
    if t not in yes|no: return
    value=t in yes
    for key in ("has_bank_account","has_aadhaar_linked_phone"):
        if slots.get(key) is None:
            slots[key]=value
            return

async def respond(ws, state, text):
    t0=time.perf_counter(); cmd=classify_command(text)
    if cmd=="repeat": reply=state.get("last_reply") or SORRY.get(state["slots"].get("language","hi"),SORRY["hi"])
    else:
        pending=next((key for key in missing_slots(state["slots"]) if key != "language"),None)
        if not state.get("results") or missing_slots(state["slots"]):
            fill_yes_no_answer(text,state["slots"])
            state["slots"]=await merge_utterance(text,state["slots"],MOCK)
        reply=next_reply(state,cmd)
        if pending:
            if state["slots"].get(pending) is None:
                retries=state.setdefault("slot_retries",{})
                retries[pending]=retries.get(pending,0)+1
                lang=state["slots"].get("language","hi")
                reply=CLARIFY.get(pending,{}).get(lang,CLARIFY.get(pending,{}).get("hi",msg(lang,pending)))
            else:
                state.setdefault("slot_retries",{}).pop(pending,None)
    if not reply or reply==SORRY.get(state["slots"].get("language","hi")): reply=SORRY.get(state["slots"].get("language","hi"),SORRY["hi"])
    state["last_reply"]=reply; state["turns"]+=1; state["log"].append({"transcript":text,"slots":dict(state["slots"])})
    await ws.send_json({"type":"reply","text":reply,"slots":state["slots"],"results":state.get("results"),"checklist":state.get("checklist"),"turns":state["turns"],"speed":state["speed"]})
    if not MOCK:
        lang=LANG_CODES.get(state["slots"].get("language","hi"),"hi-IN"); started=time.perf_counter()
        try:
            async for chunk in synthesize_chunks(reply,lang,state["speed"]):
                await ws.send_json({"type":"audio_chunk","audio":base64.b64encode(chunk).decode()})
            await ws.send_json({"type":"audio_complete","sample_rate":16000})
            logging.info("metric=timbre_latency_ms value=%d",int((time.perf_counter()-started)*1000))
        except Exception as exc: logging.warning("TTS unavailable: %s",exc)
    logging.info("metric=turn_latency_ms value=%d turns=%d",int((time.perf_counter()-t0)*1000),state["turns"])
    if state.get("completed") and not state.get("completion_logged"):
        logging.info("metric=turns_to_completion value=%d",state["turns"])
        state["completion_logged"]=True

@app.get("/")
async def index(): return FileResponse(FRONT/"index.html")

@app.get("/health")
async def health(): return {"ok":True,"mock_mode":MOCK}

@app.post("/webhooks/twilio")
async def twilio_stub():
    """Minimal IVR handoff stub. Connect your Twilio media stream to /ws/voice."""
    from fastapi.responses import Response
    xml='<?xml version="1.0" encoding="UTF-8"?><Response><Say language="hi-IN">नमस्ते किसान मित्र। इस हेल्पलाइन को voice assistant से जोड़ने के लिए Twilio Media Streams सेट करें।</Say><Hangup/></Response>'
    return Response(xml, media_type="application/xml")

@app.post("/webhooks/exotel")
async def exotel_stub():
    return {"status":"stub","message":"Connect Exotel audio streaming to /ws/voice; configure call routing in your Exotel account."}

@app.websocket("/ws/voice")
async def voice(ws: WebSocket):
    await ws.accept(); state={"slots":{"language":None,"state":None,"crop":None,"land_size_acres":None,"land_ownership":None,"has_bank_account":None,"has_aadhaar_linked_phone":None},"results":None,"checklist":None,"offer_docs":False,"offer_sms":False,"result_index":0,"speed":1.0,"turns":0,"log":[],"slot_retries":{}}
    lang="hi"; greeting=GREET[lang]; state["last_reply"]=greeting
    await ws.send_json({"type":"reply","text":greeting,"slots":state["slots"],"mock_mode":MOCK})
    while True:
        try: data=await asyncio.wait_for(ws.receive_json(),timeout=55)
        except asyncio.TimeoutError:
            await ws.send_json({"type":"silence","text":SORRY["hi"]}); continue
        except WebSocketDisconnect: break
        try:
            if data.get("type")=="language":
                chosen=data.get("language")
                if chosen in ("hi","hinglish","kn","ta","te","mr"):
                    state["slots"]["language"]=chosen
                    await ws.send_json({"type":"reply","text":GREET.get(chosen,GREET["hi"]),"slots":state["slots"],"mock_mode":MOCK})
                continue
            if data.get("type")=="audio":
                if MOCK: await ws.send_json({"type":"error","text":"Mock mode uses the text box or browser speech input."}); continue
                started=time.perf_counter(); raw=prepare_wav(base64.b64decode(data.get("audio_base64",""))); text,api_latency=await transcribe_audio(raw,language=LANG_CODES.get(state["slots"].get("language","hi"),"hi-IN"))
                logging.info("metric=prisma_latency_ms value=%d api_latency=%s",int((time.perf_counter()-started)*1000),api_latency)
                if not text.strip(): await ws.send_json({"type":"reply","text":SORRY.get(state["slots"].get("language","hi"),SORRY["hi"])}); continue
            else: text=(data.get("text") or "").strip()
            if not text: continue
            await respond(ws,state,text)
        except Exception as exc:
            logging.exception("conversation error")
            await ws.send_json({"type":"error","text":"माफ कीजिए, थोड़ी दिक्कत हुई। फिर से कोशिश करें।"})

if __name__=="__main__":
    import uvicorn
    uvicorn.run("backend.main:app",host=os.getenv("HOST","0.0.0.0"),port=int(os.getenv("PORT","8001")),reload=True)
