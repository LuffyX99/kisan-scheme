import json
import re
from backend.gnani_llm import extract_slots

SLOT_KEYS = ("language", "state", "crop", "land_size_acres", "land_ownership", "has_bank_account", "has_aadhaar_linked_phone")
OWNERSHIP_TERMS = {
    "sharecropper": ("sharecropper", "share cropping", "sharecrop", "batai", "bataiya", "bataidar", "adhiya", "barga", "बटाई", "बटाई पर", "अधिया", "आधे पर", "बंटाई", "ಪಾಲು", "பங்காக", "కౌలు భాగం"),
    "tenant": ("tenant", "lease", "leased", "rent", "rented", "kiraye", "kiraye par", "kiraye pe", "kiraye ki", "theke par", "पट्टे पर", "ठेके पर", "किराये", "किराए", "किराए पर", "ಲೀಸ್", "ಗುತ್ತಿಗೆ", "குத்தகை", "కౌలుకు"),
    "owner": ("owner", "owned", "my own", "own land", "meri zameen", "meri khud ki", "meri apni", "meri hai", "apni zameen", "apni hai", "khud ki", "khudki", "mere naam", "hamari zameen", "swanta", "निजी जमीन", "मेरी जमीन", "मेरी अपनी", "मेरी खुद की", "मेरी है", "अपनी जमीन", "अपनी है", "खुद की", "स्वयं की", "मेरे नाम", "हमारी जमीन", "मालिकाना", "मालिक हूं", "मेरी", "ನನ್ನದೇ", "ನನ್ನ ಸ್ವಂತ", "ಸ್ವಂತ ಜಮೀನು", "ಸ್ವಂತ", "எனது சொந்த", "சொந்த நிலம்", "నా సొంత", "సొంత భూమి")
}
STATE_NAMES = {
    "andhra pradesh":"Andhra Pradesh", "आंध्र प्रदेश":"Andhra Pradesh", "आन्ध्र प्रदेश":"Andhra Pradesh", "ఆంధ్రప్రదేశ్":"Andhra Pradesh", "அந்திரப் பிரதேசம்":"Andhra Pradesh",
    "arunachal pradesh":"Arunachal Pradesh", "अरुणाचल प्रदेश":"Arunachal Pradesh",
    "assam":"Assam", "असम":"Assam", "bihar":"Bihar", "बिहार":"Bihar",
    "chhattisgarh":"Chhattisgarh", "छत्तीसगढ़":"Chhattisgarh", "छत्तीसगढ":"Chhattisgarh",
    "goa":"Goa", "गोवा":"Goa", "gujarat":"Gujarat", "गुजरात":"Gujarat",
    "haryana":"Haryana", "हरियाणा":"Haryana", "himachal pradesh":"Himachal Pradesh", "हिमाचल प्रदेश":"Himachal Pradesh",
    "jharkhand":"Jharkhand", "झारखंड":"Jharkhand", "karnataka":"Karnataka", "ಕರ್ನಾಟಕ":"Karnataka", "कर्नाटक":"Karnataka",
    "kerala":"Kerala", "केरल":"Kerala", "madhya pradesh":"Madhya Pradesh", "मध्य प्रदेश":"Madhya Pradesh",
    "maharashtra":"Maharashtra", "महाराष्ट्र":"Maharashtra", "ಮಹಾರಾಷ್ಟ್ರ":"Maharashtra", "తెలంగాణ":"Telangana", "तेलंगाना":"Telangana", "telangana":"Telangana", "ತೆಲಂಗಾಣ":"Telangana",
    "manipur":"Manipur", "मणिपुर":"Manipur", "meghalaya":"Meghalaya", "मेघालय":"Meghalaya", "mizoram":"Mizoram", "मिजोरम":"Mizoram",
    "nagaland":"Nagaland", "नागालैंड":"Nagaland", "odisha":"Odisha", "ओडिशा":"Odisha", "उड़ीसा":"Odisha",
    "punjab":"Punjab", "पंजाब":"Punjab", "rajasthan":"Rajasthan", "राजस्थान":"Rajasthan", "రాజస్థాన్":"Rajasthan", "tripura":"Tripura", "त्रिपुरा":"Tripura",
    "sikkim":"Sikkim", "सिक्किम":"Sikkim", "tamil nadu":"Tamil Nadu", "தமிழ்நாடு":"Tamil Nadu", "तमिलनाडु":"Tamil Nadu",
    "uttar pradesh":"Uttar Pradesh", "उत्तर प्रदेश":"Uttar Pradesh", "uttarakhand":"Uttarakhand", "उत्तराखंड":"Uttarakhand", "उत्तराखण्ड":"Uttarakhand",
    "west bengal":"West Bengal", "पश्चिम बंगाल":"West Bengal", "delhi":"Delhi", "दिल्ली":"Delhi", "jammu and kashmir":"Jammu and Kashmir", "जम्मू कश्मीर":"Jammu and Kashmir", "ladakh":"Ladakh", "लद्दाख":"Ladakh", "puducherry":"Puducherry", "पुदुचेरी":"Puducherry", "మహారాష్ట్ర":"Maharashtra", "मೈಸೂರು":"Karnataka"
}
LANG_SCRIPT = [("kn", re.compile(r"[\u0c80-\u0cff]")), ("ta", re.compile(r"[\u0b80-\u0bff]")), ("te", re.compile(r"[\u0c00-\u0c7f]"))]

def contains_alias(text: str, alias: str) -> bool:
    if alias.isascii() and any(char.isalpha() for char in alias):
        return re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text) is not None
    return alias in text

def detect_language(text: str) -> str:
    for lang, pattern in LANG_SCRIPT:
        if pattern.search(text):
            return lang
    if re.search(r"[\u0900-\u097f]", text):
        return "mr" if re.search(r"(आहे|माझे|तुम्ही|शेतकरी|आहोत)", text) else "hi"
    return "hinglish" if re.search(r"\b(acre|bank|aadhaar|crop|hectare|loan)\b", text, re.I) else "hi"

def heuristic_extract(text: str) -> dict:
    t = text.lower()
    out = {k: None for k in SLOT_KEYS}
    out["language"] = detect_language(text)
    for key in sorted(STATE_NAMES, key=len, reverse=True):
        value = STATE_NAMES[key]
        if contains_alias(t, key):
            out["state"] = value
            break
    crops = {
        "rice":"rice", "paddy":"rice", "dhan":"rice", "dhaan":"rice", "धान":"rice", "चावल":"rice", "भात":"rice", "ನೆಲ್ಲು":"rice", "ಭತ್ತ":"rice", "நெல்":"rice", "వరి":"rice",
        "wheat":"wheat", "गेहूं":"wheat", "गेंहू":"wheat", "गहू":"wheat", "ಗೋಧಿ":"wheat", "கோதுமை":"wheat", "గోధుమ":"wheat",
        "cotton":"cotton", "कपास":"cotton", "ಕપાસ":"cotton", "பருத்தி":"cotton", "పత్తి":"cotton",
        "sugarcane":"sugarcane", "गन्ना":"sugarcane", "ಕಬ್ಬು":"sugarcane", "கரும்பு":"sugarcane", "చెరకు":"sugarcane",
        "maize":"maize", "corn":"maize", "मक्का":"maize", "ಮೆಕ್ಕೆಜೋಳ":"maize", "மக்காச்சோளம்":"maize", "మొక్కజొన్న":"maize",
        "soybean":"soybean", "सोयाबीन":"soybean", "सोयाबिन":"soybean", "ಸೋಯಾ":"soybean", "சோயா":"soybean", "సోయా":"soybean",
        "millet":"millet", "bajra":"millet", "बाजरा":"millet", "रागी":"millet", "ರಾಗಿ":"millet", "கேழ்வரகு":"millet", "సజ్జలు":"millet",
        "sorghum":"sorghum", "jowar":"sorghum", "ज्वार":"sorghum", "ಜೋಳ":"sorghum", "சோளம்":"sorghum", "జొన్న":"sorghum",
        "pulses":"pulses", "dal":"pulses", "दाल":"pulses", "दालें":"pulses", "चना":"pulses", "अरहर":"pulses", "तूर":"pulses", "मूंग":"pulses", "उड़द":"pulses", "मसूर":"pulses", "ಕಾಳು":"pulses", "பருப்பு":"pulses", "పప్పు":"pulses",
        "mustard":"mustard", "सरसों":"mustard", "मूंगफली":"groundnut", "groundnut":"groundnut", "peanut":"groundnut", "ಶೇಂಗಾ":"groundnut", "நிலக்கடலை":"groundnut", "వేరుశెనగ":"groundnut",
        "potato":"potato", "आलू":"potato", "உருளைக்கிழங்கு":"potato", "బంగాళాదుంప":"potato", "onion":"onion", "प्याज":"onion", "வெங்காயம்":"onion", "ఉల్లిపాయ":"onion",
        "tomato":"tomato", "टमाटर":"tomato", "தக்காளி":"tomato", "టమాటా":"tomato", "banana":"banana", "केला":"banana", "வாழை":"banana", "అరటి":"banana",
        "turmeric":"turmeric", "हल्दी":"turmeric", "மஞ்சள்":"turmeric", "పసుపు":"turmeric", "tea":"tea", "चाय":"tea", "coffee":"coffee", "कॉफी":"coffee", "coconut":"coconut", "नारियल":"coconut"
    }
    for name in sorted(crops, key=len, reverse=True):
        value = crops[name]
        if contains_alias(t, name):
            out["crop"] = value
            break
    land = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:acre|acres|ಎಕರೆ|एकड़|ஏக்கர்|ఎకరాలు?)", t)
    if land:
        out["land_size_acres"] = float(land.group(1).replace(",", "."))
    else:
        word_numbers = {"one":1,"a":1,"ek":1,"एक":1,"दो":2,"do":2,"two":2,"ढाई":2.5,"तीन":3,"teen":3,"चार":4,"chaar":4,"डेढ़":1.5}
        for word, number in word_numbers.items():
            if re.search(rf"(?<!\w){re.escape(word)}(?!\w)\s*(?:acre|acres|एकड़|एकड़)", t):
                out["land_size_acres"] = float(number); break
        hectares = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:hectare|ಹೆಕ್ಟೇರ್|हेक्टेयर)", t)
        if hectares: out["land_size_acres"] = round(float(hectares.group(1).replace(",", ".")) * 2.47105, 2)
    for ownership in ("sharecropper", "tenant", "owner"):
        if any(contains_alias(t, term) for term in OWNERSHIP_TERMS[ownership]):
            out["land_ownership"] = ownership
            break
    if re.search(r"\b(no bank|no account|bank account illa|ಖಾತೆ ಇಲ್ಲ|கணக்கு இல்லை)\b", t): out["has_bank_account"] = False
    elif re.search(r"\b(bank account|bank khata|ಖಾತೆ ಇದೆ|வங்கி கணக்கு)\b", t): out["has_bank_account"] = True
    if re.search(r"\b(no aadhaar|aadhaar link nahi|link nahi|ಲಿಂಕ್ ಇಲ್ಲ|இணைக்கவில்லை)\b", t): out["has_aadhaar_linked_phone"] = False
    elif re.search(r"\b(aadhaar linked|aadhaar link|ಆಧಾರ್ ಲಿಂಕ್|ஆதார் இணைப்பு)\b", t): out["has_aadhaar_linked_phone"] = True
    return out

async def merge_utterance(text: str, slots: dict, mock: bool) -> dict:
    base = dict(slots)
    heuristics = heuristic_extract(text)
    if not mock:
        try:
            model_values = await extract_slots(text)
            for key in SLOT_KEYS:
                if model_values.get(key) is not None:
                    base[key] = model_values[key]
        except Exception:
            pass
    for key, value in heuristics.items():
        if value is not None:
            base[key] = value
    # Normalize and guard model output.
    if base.get("land_size_acres") is not None:
        try: base["land_size_acres"] = max(0, float(base["land_size_acres"]))
        except (ValueError, TypeError): base["land_size_acres"] = None
    if base.get("land_ownership") not in ("owner", "tenant", "sharecropper"): base["land_ownership"] = None
    return base

def missing_slots(slots: dict) -> list[str]:
    return [k for k in SLOT_KEYS if slots.get(k) is None]
