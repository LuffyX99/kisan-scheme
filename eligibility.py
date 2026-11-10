import json
from pathlib import Path

SCHEME_PATH = Path(__file__).resolve().parents[1] / "data" / "schemes.json"

def load_schemes():
    return json.loads(SCHEME_PATH.read_text(encoding="utf-8"))

def evaluate(slots: dict, schemes=None) -> list[dict]:
    schemes = schemes if schemes is not None else load_schemes()
    results = []
    for scheme in schemes:
        rules = scheme["eligibility"]
        reasons = []
        unknown = False
        rejected = False
        if rules.get("states") and slots.get("state") not in rules["states"]:
            if not slots.get("state"): unknown = True; reasons.append("state not known")
            else: rejected = True; reasons.append("state is outside this scheme")
        crop = slots.get("crop")
        if rules.get("crops") and crop:
            if crop not in rules["crops"]: rejected = True; reasons.append("crop is not covered")
        elif rules.get("crops") and not crop:
            unknown = True; reasons.append("crop and season need checking")
        if rules.get("crop_season_required"):
            unknown = True; reasons.append("notified crop and current season window need checking")
        if rules.get("ownership_required") and slots.get("land_ownership"):
            if slots["land_ownership"] not in rules.get("allowed_ownership", ["owner"]):
                if rules.get("tenant_review") and slots["land_ownership"] in ("tenant", "sharecropper"):
                    unknown = True; reasons.append("tenant documentation varies by state")
                else: rejected = True; reasons.append("scheme requires eligible landholding status")
        elif rules.get("ownership_required") and not slots.get("land_ownership"):
            unknown = True; reasons.append("land ownership not known")
        min_acres = rules.get("min_land_acres")
        if min_acres is not None and slots.get("land_size_acres") is not None and slots["land_size_acres"] < min_acres:
            rejected = True; reasons.append("land size is below the scheme minimum")
        if min_acres is not None and slots.get("land_size_acres") is None: unknown = True; reasons.append("land size not known")
        for field in rules.get("requires_true", []):
            if slots.get(field) is False:
                unknown = True; reasons.append(f"{field.replace('_', ' ')} requirement needs resolution")
            elif slots.get(field) is None:
                unknown = True; reasons.append(f"{field.replace('_', ' ')} not confirmed")
        if rules.get("needs_state_program_check"):
            unknown = True; reasons.append("current state component and application window need checking")
        if rules.get("needs_official_eligibility_check"):
            unknown = True; reasons.append("confirm beneficiary and land-record requirements with the official scheme")
        if rules.get("needs_application_window_check"):
            unknown = True; reasons.append("confirm that applications or the relevant seasonal component are open")
        status = "not eligible" if rejected else "maybe (needs check)" if unknown else "likely eligible"
        results.append({"id": scheme["id"], "name": scheme["name"], "benefit": scheme["benefit"], "documents": scheme["documents"], "where_to_apply": scheme["where_to_apply"], "source_url": scheme["source_url"], "last_verified_date": scheme["last_verified_date"], "status": status, "reasons": reasons})
    return results
