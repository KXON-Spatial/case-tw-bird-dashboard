# 台灣鳥類時空分析儀表板

GBIF 開放鳥類觀測 → 清洗 → H3 + 月份聚合 → deck.gl + MapLibre 互動儀表板。
零後端、靜態網頁、每季自動重建。

## MVP 範圍

**2 物種**(代表兩種生態策略):
- 黑面琵鷺 *Platalea minor*(冬候鳥,東亞瀕危,鰲鼓/七股越冬)
- 五色鳥 *Psilopogon nuchalis*(留鳥,台灣特有種)

**單一視覺**:月份滑桿 + Play 動畫,展現冬候鳥的季節空白 vs 留鳥的全年穩定駐留。

## 不在 MVP 的(後續 phase)

- 年份維度與「歷史趨勢」——raw observation count ≠ population trend,要做需先處理 effort 正規化(eBird ST 或 checklist frequency)
- 候鳥/留鳥/外來種群組多選 filter
- 跨物種比對(會用 small multiples,不疊圖)

## 跑起來

```bash
python -m venv .venv
.venv/bin/pip install pygbif h3
.venv/bin/python fetch_gbif.py        # 5–15 分,輸出 bird_h3_monthly.json
.venv/bin/python build_dashboard.py   # 輸出 bird_dashboard.html
open bird_dashboard.html
```

## 部署

GitHub Pages + custom domain `bird.kxon.net`,workflow `.github/workflows/update.yml`
每季(1/4/7/10 月)自動跑 + 可手動觸發。

一次性設定:
1. push 到新 GitHub repo
2. Settings → Pages → Source = GitHub Actions
3. DNS:CNAME `bird.kxon.net` → `<owner>.github.io`
4. Settings → Pages → Custom domain 填 `bird.kxon.net`,等憑證綠燈

## 技術備註

- pygbif 0.6.6:`name_backbone(scientificName=, taxonRank=)`,回傳 `usage.key`
- h3 v4:`latlng_to_cell()` / `cell_to_boundary()`(回傳 (lat,lng))
- deck.gl UMD bundle 不含 h3-js → 用 Python 預算 hex 邊界 + 內建 PolygonLayer
- 兩物種 GBIF 數量都在 Search API 100k 上限內;若日後升 Aves 整類群須改 Download API
