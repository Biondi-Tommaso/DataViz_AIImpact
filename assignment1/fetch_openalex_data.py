import json
import os
import time
from datetime import datetime, timezone
import requests

BASE_URL = "https://api.openalex.org/works"
CONTACT_EMAIL = os.environ.get("OPENALEX_EMAIL", "research@example.org")
API_KEY = os.environ.get("OPENALEX_API_KEY", "").strip()
HEADERS = {"User-Agent": f"AIMathObservatory/1.3 (mailto:{CONTACT_EMAIL})"}

# Tassonomia aggiornata OpenAlex (Topics sostituisce Concepts dal 2024):
# Field 26 = Mathematics, Subfield 1702 = Artificial Intelligence
MATH_FIELD_ID = "26"
AI_SUBFIELD_ID = "1702"
BASE_FILTER = f"topics.field.id:{MATH_FIELD_ID},topics.subfield.id:{AI_SUBFIELD_ID}"

# Concetti legacy mantenuti solo per i sotto-campi specifici nello step 6
MATH_CONCEPT_ID = "C33923547"
ARXIV_SOURCE_ID = "S4306400194"

YEARS_HISTORY = [str(y) for y in range(2000, 2026)]  # 2000–2025 per la regressione storica
YEARS_MAIN = [str(y) for y in range(2019, 2027)]     # 2019–2026 per i dettagli annuali

# Query Lean senza falsi positivi (esclude "lean manufacturing", "lean body", ecc.)
LEAN_SEARCH = (
    'mathlib OR mathlib4 OR "Lean 4" OR "Lean4" OR "Lean prover" OR "Lean theorem prover" '
    'OR (Lean AND ("proof assistant" OR "theorem proving" OR "theorem prover" '
    'OR formalization OR autoformalization OR "formal proof" OR "formal verification"))'
)

# Universo per la verifica formale / theorem proving (Lean vs Isabelle, Coq/Rocq, HOL, ecc.)
FORMAL_SEARCH = (
    '"theorem proving" OR "proof assistant" OR autoformalization OR "formal proof" '
    'OR "formal mathematics" OR Isabelle OR Coq OR Rocq OR "HOL Light" OR Metamath '
    'OR mathlib OR mathlib4 OR (Lean AND "formal verification")'
)


def openalex_get(params: dict, retries: int = 4) -> dict:
    """Esegue una richiesta GET a OpenAlex con gestione API key, polite pool e retry."""
    req_params = dict(params)
    req_params.setdefault("mailto", CONTACT_EMAIL)
    if API_KEY:
        req_params["api_key"] = API_KEY

    for attempt in range(retries):
        resp = requests.get(BASE_URL, params=req_params, headers=HEADERS, timeout=45)
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
            wait_s = 1.5 * (2 ** attempt)
            print(f"  [OpenAlex {resp.status_code}] attendo {wait_s:.1f}s e riprovo...")
            time.sleep(wait_s)
            continue
        if not resp.ok:
            raise RuntimeError(f"OpenAlex HTTP {resp.status_code}: {resp.text[:300]}")
        time.sleep(0.18)
        return resp.json()
    raise RuntimeError("OpenAlex: numero massimo di tentativi superato.")


def fetch_group_by_year(
    extra_filter: str,
    year_range: str = "2019-2026",
    search_query: str | None = None,
) -> dict[str, int]:
    """Esegue una query OpenAlex raggruppata per anno di pubblicazione."""
    full_filter = f"{extra_filter},publication_year:{year_range}"
    params = {
        "filter": full_filter,
        "group_by": "publication_year",
        "per_page": 200,
    }
    if search_query:
        params["search"] = search_query

    data = openalex_get(params)
    counts = {}
    for bucket in data.get("group_by", []):
        yr = str(bucket.get("key"))
        counts[yr] = int(bucket.get("count", 0))
    return counts


def fetch_count(extra_filter: str, search_query: str | None = None) -> int:
    """Restituisce il conteggio totale (meta.count) per un filtro."""
    params = {"filter": extra_filter, "per_page": 1}
    if search_query:
        params["search"] = search_query
    data = openalex_get(params)
    return int(data.get("meta", {}).get("count", 0))


def fetch_search_counts_by_year(scope_filter: str, search_query: str) -> dict[str, int]:
    """Ottiene i conteggi 2019–2026 per una query di ricerca con fallback anno per anno."""
    counts = fetch_group_by_year(scope_filter, "2019-2026", search_query=search_query)
    if sum(counts.values()) == 0:
        counts = {
            yr: fetch_count(f"{scope_filter},publication_year:{yr}", search_query=search_query)
            for yr in YEARS_MAIN
        }
    return counts


def fetch_ai_or_math_union(search_query: str) -> dict[str, int]:
    """Calcola l'unione esatta (AI subfield 1702) U (Math field 26) via inclusione-esclusione."""
    ai_only_and_both = fetch_search_counts_by_year(f"topics.subfield.id:{AI_SUBFIELD_ID}", search_query)
    math_only_and_both = fetch_search_counts_by_year(f"topics.field.id:{MATH_FIELD_ID}", search_query)
    both = fetch_search_counts_by_year(BASE_FILTER, search_query)
    return {
        yr: max(ai_only_and_both.get(yr, 0) + math_only_and_both.get(yr, 0) - both.get(yr, 0), 0)
        for yr in YEARS_MAIN
    }


def main():
    print("1/6 Scarico serie totale 2000–2026 (Mathematics field:26 + AI subfield:1702)...")
    totals_all = fetch_group_by_year(BASE_FILTER, "2000-2026")

    historical_series = [
        {"year": yr, "totalCount": totals_all.get(yr, 0)}
        for yr in YEARS_HISTORY
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

    print("4/6 Scarico adozione di Lean (unione AI U Math, e quota tra i Proof Assistant)...")
    lean_counts = fetch_ai_or_math_union(LEAN_SEARCH)
    formal_counts = fetch_ai_or_math_union(FORMAL_SEARCH)

    lean_verification_by_year = []
    for yr in YEARS_MAIN:
        tot_math_ai = max(totals_all.get(yr, 0), 1)
        verified = lean_counts.get(yr, 0)
        formal_tot = max(formal_counts.get(yr, 0), verified, 1)

        formal_share_pct = round(min((verified / formal_tot) * 100, 100.0), 1)
        math_ai_pct = round(min((verified / tot_math_ai) * 100, 100.0), 2)

        lean_verification_by_year.append({
            "year": yr,
            "verifiedPct": formal_share_pct,
            "unverifiedPct": round(max(100.0 - formal_share_pct, 0.0), 1),
            "mathAiPct": math_ai_pct,
            "verifiedCount": verified,
            "formalTotalCount": formal_tot,
            "totalCount": tot_math_ai,
        })
        print(
            f"  {yr}: Lean={verified} paper | "
            f"{formal_share_pct}% tra i Proof Assistant ({verified}/{formal_tot}) | "
            f"{math_ai_pct}% su Math+AI ({verified}/{tot_math_ai})"
        )

    print("5/6 Scarico confronto pulito Peer-Reviewed vs arXiv (locations)...")
    arxiv_counts = fetch_group_by_year(f"{BASE_FILTER},locations.source.id:{ARXIV_SOURCE_ID}")
    peer_counts = fetch_group_by_year(f"{BASE_FILTER},locations.source.type:journal|conference")
    both_counts = fetch_group_by_year(
        f"{BASE_FILTER},locations.source.id:{ARXIV_SOURCE_ID},locations.source.type:journal|conference"
    )

    peer_review_by_year = []
    for yr in YEARS_MAIN:
        tot = max(totals_all.get(yr, 0), 1)
        arxiv_tot = arxiv_counts.get(yr, 0)
        peer_tot = peer_counts.get(yr, 0)
        both_cnt = min(both_counts.get(yr, 0), arxiv_tot, peer_tot)

        arxiv_only = max(arxiv_tot - both_cnt, 0)
        peer_only = max(peer_tot - both_cnt, 0)
        classified_tot = max(peer_only + both_cnt + arxiv_only, 1)

        peer_only_pct = round((peer_only / classified_tot) * 100, 1)
        both_pct = round((both_cnt / classified_tot) * 100, 1)
        arxiv_only_pct = round(max(100.0 - peer_only_pct - both_pct, 0.0), 1)

        peer_review_by_year.append({
            "year": yr,
            "totalCount": tot,
            "peerReviewedTotalCount": peer_tot,
            "arxivTotalCount": arxiv_tot,
            "bothCount": both_cnt,
            "peerOnlyCount": peer_only,
            "arxivOnlyCount": arxiv_only,
            "classifiedCount": classified_tot,
            "peerOnlyPct": peer_only_pct,
            "bothPct": both_pct,
            "arxivOnlyPct": arxiv_only_pct,
            "peerReviewedPct": round(peer_only_pct + both_pct, 1),
            "preprintPct": arxiv_only_pct,
            "peerTotalSharePct": round((peer_tot / classified_tot) * 100, 1),
            "arxivTotalSharePct": round((arxiv_tot / classified_tot) * 100, 1),
            "ratioPeerToArxiv": round(peer_tot / max(arxiv_tot, 1), 2),
        })

    print("6/6 Scarico confronto sottodiscipline matematiche (2019 vs 2026)...")
    subfields = [
        ("Logica & Fondamenti", f"concepts.id:{MATH_CONCEPT_ID},concepts.id:C111472728"),
        ("Analisi Numerica & PDE", f"concepts.id:{MATH_CONCEPT_ID},concepts.id:C28826006"),
        ("Combinatoria & Teoria Grafi", f"concepts.id:{MATH_CONCEPT_ID},concepts.id:C114614502"),
        ("Algebra & Teoria dei Numeri", f"concepts.id:{MATH_CONCEPT_ID},concepts.id:C136119220"),
        ("Geometria & Topologia", f"concepts.id:{MATH_CONCEPT_ID},concepts.id:C2524010"),
        ("Probabilità & Statistica Mat.", f"concepts.id:{MATH_CONCEPT_ID},concepts.id:C105795698"),
    ]
    subfields_comparison = []
    for label, sf_filter in subfields:
        tot_19 = max(fetch_count(f"{sf_filter},publication_year:2019"), 1)
        ai_19 = fetch_count(f"{sf_filter},topics.subfield.id:{AI_SUBFIELD_ID},publication_year:2019")
        tot_26 = max(fetch_count(f"{sf_filter},publication_year:2026"), 1)
        ai_26 = fetch_count(f"{sf_filter},topics.subfield.id:{AI_SUBFIELD_ID},publication_year:2026")
        subfields_comparison.append({
            "field": label,
            "pct2019": round((ai_19 / tot_19) * 100, 1),
            "pct2026": round((ai_26 / tot_26) * 100, 1),
        })

    payload = {
        "metadata": {
            "source": "OpenAlex API (https://api.openalex.org/works)",
            "filter": BASE_FILTER,
            "arxivSourceId": ARXIV_SOURCE_ID,
            "period": "2000-2026",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        },
        "preAiHistoricalSeries": historical_series,
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