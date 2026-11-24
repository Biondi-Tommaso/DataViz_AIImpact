import json
import os
import time
from datetime import datetime, timezone
import requests

BASE_URL = "https://api.openalex.org/works"
# Inserisci la tua email per accedere al Polite Pool di OpenAlex (limiti più alti)
HEADERS = {"User-Agent": "AIMathObservatory/1.0 (mailto:research@example.org)"}

# Concetti OpenAlex: Mathematics (C33923547) e Artificial Intelligence (C154945302)
MATH_ID = "C33923547"
AI_ID = "C154945302"
BASE_FILTER = f"concepts.id:{MATH_ID},concepts.id:{AI_ID}"

YEARS_PRE_AI = [str(y) for y in range(2015, 2020)]
YEARS_MAIN = [str(y) for y in range(2019, 2027)]


def fetch_group_by_year(extra_filter: str, year_range: str = "2019-2026") -> dict[str, int]:
    """Esegue una query OpenAlex raggruppata per anno di pubblicazione."""
    full_filter = f"{extra_filter},publication_year:{year_range}"
    params = {
        "filter": full_filter,
        "group_by": "publication_year",
        "per-page": 200,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    time.sleep(0.15)  # Rispetto del rate limit OpenAlex

    counts = {}
    for bucket in data.get("group_by", []):
        yr = str(bucket.get("key"))
        counts[yr] = int(bucket.get("count", 0))
    return counts


def fetch_count(extra_filter: str) -> int:
    """Restituisce il conteggio totale (meta.count) per un filtro."""
    params = {"filter": extra_filter, "per-page": 1}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    time.sleep(0.15)
    return int(resp.json().get("meta", {}).get("count", 0))


def main():
    print("1/6 Scarico serie totale 2015–2026 (Mathematics + AI)...")
    totals_all = fetch_group_by_year(BASE_FILTER, "2015-2026")

    pre_ai_series = [
        {"year": yr, "totalCount": totals_all.get(yr, 0)}
        for yr in YEARS_PRE_AI
    ]

    print("2/6 Scarico dati per Università (Oxford, NYU, UniGe)...")
    inst_ids = {
        "Oxford": "I40120149",
        "NYU": "I57206974",
        "UniGe": "I83816512",
    }
    inst_counts = {
        name: fetch_group_by_year(f"{BASE_FILTER},authorships.institutions.id:{oid}")
        for name, oid in inst_ids.items()
    }
    universities_by_year = [
        {
            "year": yr,
            "Oxford": inst_counts["Oxford"].get(yr, 0),
            "NYU": inst_counts["NYU"].get(yr, 0),
            "UniGe": inst_counts["UniGe"].get(yr, 0),
        }
        for yr in YEARS_MAIN
    ]

    print("3/6 Scarico distribuzione geografica (Top 10 Paesi)...")
    countries = [
        ("Stati Uniti", "US"),
        ("Cina", "CN"),
        ("Regno Unito", "GB"),
        ("Germania", "DE"),
        ("Francia", "FR"),
        ("Italia", "IT"),
        ("Canada", "CA"),
        ("Giappone", "JP"),
        ("Svizzera", "CH"),
        ("India", "IN"),
    ]
    geographic_heatmap = []
    for label, code in countries:
        c_counts = fetch_group_by_year(f"{BASE_FILTER},authorships.countries:{code}")
        geographic_heatmap.append({
            "country": label,
            "code": code,
            "values": {yr: c_counts.get(yr, 0) for yr in YEARS_MAIN},
        })

    print("4/6 Scarico quota lavori con verifica formale Lean...")
    lean_filter = f'{BASE_FILTER},default.search:("Lean 4" OR "Lean prover" OR "mathlib")'
    lean_counts = fetch_group_by_year(lean_filter)
    lean_verification_by_year = []
    for yr in YEARS_MAIN:
        tot = max(totals_all.get(yr, 0), 1)
        verified = lean_counts.get(yr, 0)
        v_pct = round((verified / tot) * 100, 1)
        lean_verification_by_year.append({
            "year": yr,
            "verifiedPct": v_pct,
            "unverifiedPct": round(100.0 - v_pct, 1),
            "verifiedCount": verified,
            "totalCount": tot,
        })

    print("5/6 Scarico ripartizione Peer-Reviewed vs Preprint/Repository...")
    preprint_filter = f"{BASE_FILTER},primary_location.source.type:repository"
    preprint_counts = fetch_group_by_year(preprint_filter)
    peer_review_by_year = []
    for yr in YEARS_MAIN:
        tot = max(totals_all.get(yr, 0), 1)
        pre_cnt = preprint_counts.get(yr, 0)
        pre_pct = round((pre_cnt / tot) * 100)
        pr_pct = 100 - pre_pct
        peer_review_by_year.append({
            "year": yr,
            "peerReviewedPct": pr_pct,
            "preprintPct": pre_pct,
            "totalCount": tot,
        })

    print("6/6 Scarico confronto sottodiscipline matematiche (2019 vs 2026)...")
    subfields = [
        ("Logica & Fondamenti", f"concepts.id:{MATH_ID},concepts.id:C111472728"),
        ("Analisi Numerica & PDE", f"concepts.id:{MATH_ID},concepts.id:C28826006"),
        ("Combinatoria & Teoria Grafi", f"concepts.id:{MATH_ID},concepts.id:C114614502"),
        ("Algebra & Teoria dei Numeri", f"concepts.id:{MATH_ID},concepts.id:C136119220"),
        ("Geometria & Topologia", f"concepts.id:{MATH_ID},concepts.id:C2524010"),
        ("Probabilità & Statistica Mat.", f"concepts.id:{MATH_ID},concepts.id:C105795698"),
    ]
    subfields_comparison = []
    for label, sf_filter in subfields:
        tot_19 = max(fetch_count(f"{sf_filter},publication_year:2019"), 1)
        ai_19 = fetch_count(f"{sf_filter},concepts.id:{AI_ID},publication_year:2019")
        tot_26 = max(fetch_count(f"{sf_filter},publication_year:2026"), 1)
        ai_26 = fetch_count(f"{sf_filter},concepts.id:{AI_ID},publication_year:2026")
        subfields_comparison.append({
            "field": label,
            "pct2019": round((ai_19 / tot_19) * 100, 1),
            "pct2026": round((ai_26 / tot_26) * 100, 1),
        })

    payload = {
        "metadata": {
            "source": "OpenAlex API (https://api.openalex.org/works)",
            "filter": BASE_FILTER,
            "period": "2015-2026",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        },
        "preAiHistoricalSeries": pre_ai_series,
        "universitiesByYear": universities_by_year,
        "geographicHeatmap": geographic_heatmap,
        "leanVerificationByYear": lean_verification_by_year,
        "peerReviewByYear": peer_review_by_year,
        "subfieldsComparison": subfields_comparison,
    }

    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "openalex_ai_math.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Completato! File salvato in: {out_path}")


if __name__ == "__main__":
    main()
