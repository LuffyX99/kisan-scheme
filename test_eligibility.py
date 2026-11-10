import array, math, unittest
from backend.eligibility import evaluate
from backend.slot_filler import heuristic_extract
from backend.audio_utils import is_speech_frame, normalize_pcm16, pcm16_mono_rms

BASE={"state":"Karnataka","crop":"rice","land_size_acres":2.0,"land_ownership":"owner","has_bank_account":True,"has_aadhaar_linked_phone":True,"language":"hi"}
PROFILES=[
 ({"state":None,"land_ownership":None,"has_bank_account":None},"maybe (needs check)"),
 ({"state":"Karnataka","land_ownership":"owner","has_bank_account":True},"likely eligible"),
 ({"state":"Karnataka","crop":"rice","land_size_acres":1,"land_ownership":"owner","has_bank_account":True},"likely eligible"),
 ({"state":"Karnataka","crop":"rice","land_size_acres":3,"land_ownership":"tenant","has_bank_account":True},"not eligible"),
 ({"state":"Karnataka","crop":"rice","land_size_acres":3,"land_ownership":"sharecropper","has_bank_account":True},"not eligible"),
 ({"state":"Karnataka","crop":"rice","land_size_acres":1,"land_ownership":"owner","has_bank_account":False},"maybe (needs check)"),
 ({"state":"Maharashtra","crop":"cotton","land_size_acres":4,"land_ownership":"owner","has_bank_account":True},"likely eligible"),
 ({"state":"Tamil Nadu","crop":"rice","land_size_acres":0.5,"land_ownership":"owner","has_bank_account":True},"likely eligible"),
 ({"state":"Karnataka","crop":"millet","land_size_acres":2,"land_ownership":"owner","has_bank_account":True},"likely eligible"),
 ({"state":"Karnataka","crop":"rice","land_size_acres":2,"land_ownership":"owner","has_bank_account":True},"likely eligible"),
 ({"state":"Karnataka","crop":"cotton","land_size_acres":2,"land_ownership":"owner","has_bank_account":True},"likely eligible"),
 ({"state":"Karnataka","crop":"cotton","land_size_acres":2,"land_ownership":"tenant","has_bank_account":False},"not eligible"),
 ({"state":"Karnataka","crop":"rice","land_size_acres":2,"land_ownership":"owner","has_bank_account":None},"maybe (needs check)"),
 ({"state":"Karnataka","crop":"rice","land_size_acres":2,"land_ownership":"owner","has_bank_account":True,"has_aadhaar_linked_phone":False},"likely eligible"),
 ({"state":"Karnataka","crop":"rice","land_size_acres":2,"land_ownership":"owner","has_bank_account":True,"has_aadhaar_linked_phone":True},"likely eligible")]

class KisanMitraTests(unittest.TestCase):
    def test_eligibility_fifteen_profiles(self):
        self.assertEqual(len(PROFILES),15)
        for i,(profile,expected) in enumerate(PROFILES):
            with self.subTest(profile=i):
                results=evaluate({**BASE,**profile})
                pm=next((r for r in results if r["id"]=="pm_kisan"),{"status":"not eligible"})
                self.assertEqual(pm["status"],expected)

    def test_non_karnataka_state_scheme_excluded(self):
        results=evaluate({**BASE,"state":"Maharashtra"})
        raitha=next(x for x in results if x["id"]=="karnataka_raitha_siri")
        self.assertEqual(raitha["status"],"not eligible")

    def test_hinglish_code_mixed_land_and_crop(self):
        slots=heuristic_extract("do acre mein dhaan lagaya hai")
        self.assertEqual(slots["language"],"hinglish")
        self.assertEqual(slots["land_size_acres"],2)
        self.assertEqual(slots["crop"],"rice")

    def test_kannada_regional_extraction(self):
        slots=heuristic_extract("ಕರ್ನಾಟಕದಲ್ಲಿ 2 ಎಕರೆ ನನ್ನದೇ ಜಮೀನಿನಲ್ಲಿ ಭತ್ತ ಬೆಳೆಯುತ್ತೇನೆ")
        self.assertEqual(slots["language"],"kn")
        self.assertEqual(slots["state"],"Karnataka")
        self.assertEqual(slots["land_size_acres"],2)
        self.assertEqual(slots["crop"],"rice")
        self.assertEqual(slots["land_ownership"],"owner")

    def test_hindi_and_marathi_script_hint(self):
        self.assertEqual(heuristic_extract("मेरी जमीन दो एकड़ है")["language"],"hi")
        self.assertEqual(heuristic_extract("माझे दोन एकर शेत आहे")["language"],"mr")

    def test_noisy_low_volume_audio_keeps_speech(self):
        rate=16000
        pcm=array.array("h",(int(450*math.sin(2*math.pi*220*i/rate)+int(110*math.sin(i*0.71))) for i in range(rate//4))).tobytes()
        self.assertTrue(is_speech_frame(pcm))
        lifted=normalize_pcm16(pcm)
        self.assertEqual(len(lifted),len(pcm))
        self.assertGreater(pcm16_mono_rms(lifted),pcm16_mono_rms(pcm))

    def test_quiet_frames_are_not_dropped(self):
        quiet=array.array("h",[12,-10,9,-12]*200).tobytes()
        self.assertTrue(normalize_pcm16(quiet))

if __name__=="__main__": unittest.main()
