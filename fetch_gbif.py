"""
GBIF 台灣鳥類觀測 → 清洗 → (H3, 月份) 聚合 → JSON

MVP 2 物種(代表兩種生態策略):
  - 黑面琵鷺 Platalea minor       — 冬候鳥(東亞瀕危,鰲鼓/七股越冬)
  - 五色鳥   Psilopogon nuchalis  — 留鳥 / 台灣特有種

設計重點:
  - 月份維度聚合(非年份),展現「季節律動」——冬候鳥的紅外/夏季空白 vs 留鳥的全年穩定
  - 清洗:TW bbox、(0,0)、issue flags、無 month 的丟掉
  - 聚合 cardinality:(物種 × hex × 月份)= 2 × ~600 × 12 ≈ 14k 列,可 inline 進 HTML
  - Search API:這 2 物種應在 100k 上限內;若撞上限會印警告(下階段升 Download API)

輸出:bird_h3_monthly.json
"""
import json
import time
from datetime import date, datetime
from pygbif import species, occurrences
import h3

SPECIES = [
    {"zh": "黑面琵鷺", "name": "Platalea minor",       "type": "冬候鳥"},
    {"zh": "五色鳥",   "name": "Psilopogon nuchalis",  "type": "留鳥 · 台灣特有"},
]

TW_BBOX = {"min_lng": 119.3, "max_lng": 122.1, "min_lat": 21.8, "max_lat": 25.4}
H3_RES = 7
PAGE_SIZE = 300
SEARCH_OFFSET_CAP = 100_000
OUT = "bird_h3_monthly.json"

# GBIF issue flags 顯示座標可疑時剔除
BAD_ISSUES = {
    "ZERO_COORDINATE", "COORDINATE_OUT_OF_RANGE",
    "COUNTRY_COORDINATE_MISMATCH",
    "PRESUMED_NEGATED_LATITUDE", "PRESUMED_NEGATED_LONGITUDE",
    "PRESUMED_SWAPPED_COORDINATE",
}


def resolve_key(name: str) -> int:
    r = species.name_backbone(scientificName=name, taxonRank="SPECIES")
    if r.get("matchType") == "NONE":
        raise ValueError(f"name_backbone 找不到 {name}")
    return r["usage"]["key"]


def total_count(key: int) -> int:
    r = occurrences.search(taxonKey=key, country="TW", hasCoordinate=True, limit=0)
    return r.get("count", 0)


def fetch(key: int) -> list:
    """Search API 分頁。撞 100k 上限會停並警告。"""
    rows, offset = [], 0
    while offset < SEARCH_OFFSET_CAP:
        r = occurrences.search(
            taxonKey=key, country="TW", hasCoordinate=True,
            limit=PAGE_SIZE, offset=offset,
        )
        results = r.get("results", [])
        rows.extend(results)
        if r.get("endOfRecords") or len(results) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        if offset % 3000 == 0:
            print(f"    抓到 {offset:,}")
        time.sleep(0.05)
    if offset >= SEARCH_OFFSET_CAP:
        print(f"  ⚠ 撞到 Search API 100k 上限,建議升 Download API")
    return rows


def clean(rows: list) -> list:
    """回傳 [(lat, lng, month, year_or_None), ...]"""
    out = []
    for r in rows:
        lat, lng = r.get("decimalLatitude"), r.get("decimalLongitude")
        if lat is None or lng is None:
            continue
        if lat == 0 and lng == 0:
            continue
        if not (TW_BBOX["min_lat"] <= lat <= TW_BBOX["max_lat"]):
            continue
        if not (TW_BBOX["min_lng"] <= lng <= TW_BBOX["max_lng"]):
            continue
        if set(r.get("issues") or []) & BAD_ISSUES:
            continue
        m = r.get("month")
        if not m:
            ed = r.get("eventDate") or ""
            try:
                m = datetime.fromisoformat(ed.split("T")[0]).month
            except Exception:
                continue
        y = r.get("year")
        out.append((float(lat), float(lng), int(m), int(y) if y else None))
    return out


def aggregate(per_species: list) -> dict:
    hexes, data = {}, []
    year_min, year_max = 9999, 0
    species_info = []
    for sp_idx, (sp, pts) in enumerate(per_species):
        acc = {}
        for lat, lng, m, y in pts:
            h_ = h3.latlng_to_cell(lat, lng, H3_RES)
            acc[(h_, m)] = acc.get((h_, m), 0) + 1
            if y is not None:
                year_min, year_max = min(year_min, y), max(year_max, y)
            if h_ not in hexes:
                ring = [[lng_, lat_] for lat_, lng_ in h3.cell_to_boundary(h_)]
                ring.append(ring[0])
                hexes[h_] = ring
        for (h_, m), c in acc.items():
            data.append({"s": sp_idx, "h": h_, "m": m, "c": c})
        species_info.append({
            "zh": sp["zh"], "name": sp["name"], "type": sp["type"],
            "key": sp["key"], "total": len(pts),
        })
    return {
        "fetched": date.today().isoformat(),
        "species": species_info,
        "data": data,
        "hexes": hexes,
        "yearMin": year_min if year_min != 9999 else None,
        "yearMax": year_max if year_max != 0 else None,
    }


def main():
    per_species = []
    for sp in SPECIES:
        print(f"\n[{sp['zh']} {sp['name']}]")
        sp["key"] = resolve_key(sp["name"])
        n = total_count(sp["key"])
        print(f"  usageKey={sp['key']}  TW 有座標總數={n:,}")
        if n > SEARCH_OFFSET_CAP:
            print(f"  ⚠ 超過 Search API 上限,僅能抓前 {SEARCH_OFFSET_CAP:,} 筆")
        print("  分頁抓取中...")
        raw = fetch(sp["key"])
        print(f"  原始 {len(raw):,} 筆")
        pts = clean(raw)
        dropped = len(raw) - len(pts)
        print(f"  清洗後 {len(pts):,} 筆(丟 {dropped:,})")
        per_species.append((sp, pts))

    payload = aggregate(per_species)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"\n=== 完成 ===")
    print(f"物種 {len(payload['species'])}, "
          f"列 {len(payload['data']):,}, "
          f"hexes {len(payload['hexes']):,}, "
          f"年 {payload['yearMin']}–{payload['yearMax']}")
    print(f"輸出 -> {OUT}")


if __name__ == "__main__":
    main()
