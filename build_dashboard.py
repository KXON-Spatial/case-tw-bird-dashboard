"""
讀 bird_h3_monthly.json → 產出含「月份滑桿 + Play 動畫 + 物種下拉」的
deck.gl + MapLibre 互動儀表板。

設計:
  - 六角格邊界 Python 端 inline,前端用 PolygonLayer(避開 deck.gl UMD 沒打包 h3-js 的雷)
  - overlaid 模式(interleaved:false):deck 畫在底圖上層
  - 篩選(物種 / 月份)在前端 groupby-sum,即時重建圖層
  - Play 動畫:每 ~800ms 月份 +1,12 → 1 循環
"""
import json
from datetime import date

JSON_IN = "bird_h3_monthly.json"
HTML_OUT = "bird_dashboard.html"
CENTER = [120.9, 23.7]
ZOOM = 7.0
ELEV_SCALE = 30

SITE_URL = "https://bird.kxon.net"
PAGE_PATH = "/"
OG_IMAGE = f"{SITE_URL}/og.png"   # TODO: 加 1200x630 預覽圖


def main():
    payload = json.load(open(JSON_IN, encoding="utf-8"))
    html = TEMPLATE
    for k, v in {
        "__PAYLOAD__": json.dumps(payload, ensure_ascii=False),
        "__CENTER__": json.dumps(CENTER),
        "__ZOOM__": str(ZOOM),
        "__ELEV__": str(ELEV_SCALE),
        "__FETCHED__": payload.get("fetched") or date.today().isoformat(),
        "__PAGE_URL__": f"{SITE_URL}{PAGE_PATH}",
        "__OG_IMAGE__": OG_IMAGE,
    }.items():
        html = html.replace(k, v)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"物種 {len(payload['species'])}, 列 {len(payload['data']):,}, "
          f"hexes {len(payload['hexes']):,}")
    print(f"輸出 -> {HTML_OUT}")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>台灣鳥類季節律動 | KXON Spatial</title>
<meta name="description" content="台灣鳥類 GBIF 觀測的月份動態地圖。冬候鳥黑面琵鷺 vs 留鳥五色鳥,H3 六角格 + 月份滑桿 + Play 動畫展現候鳥遷移與留鳥穩定駐留的對比。" />
<link rel="canonical" href="__PAGE_URL__" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="KXON Spatial" />
<meta property="og:locale" content="zh_TW" />
<meta property="og:title" content="台灣鳥類季節律動" />
<meta property="og:description" content="GBIF 觀測月份動畫,展現冬候鳥 vs 留鳥的時空對比。" />
<meta property="og:url" content="__PAGE_URL__" />
<meta property="og:image" content="__OG_IMAGE__" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="台灣鳥類季節律動" />
<meta name="twitter:description" content="GBIF 觀測月份動畫,展現冬候鳥 vs 留鳥的時空對比。" />
<meta name="twitter:image" content="__OG_IMAGE__" />
<link href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css" rel="stylesheet" />
<script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
<script src="https://unpkg.com/deck.gl@9/dist.min.js"></script>
<style>
  html,body{margin:0;height:100%;background:#0b0b10;
    font-family:"PingFang TC",system-ui,sans-serif;}
  #map{position:absolute;inset:0;}
  .panel{position:absolute;z-index:2;color:#f2f2f2;text-shadow:0 1px 4px rgba(0,0,0,.8);}
  #title{top:16px;left:20px;background:rgba(13,16,22,.74);padding:12px 16px;
    border-radius:10px;backdrop-filter:blur(2px);}
  #title h1{margin:0;font-size:21px;font-weight:700;}
  #title p{margin:4px 0 0;font-size:12px;color:#cfcfcf;}
  #controls{top:16px;right:16px;background:rgba(15,15,22,.84);padding:14px 16px;
    border-radius:10px;width:288px;text-shadow:none;}
  #controls label{font-size:12px;color:#cfcfcf;display:block;margin:0 0 5px;}
  #controls select{width:100%;padding:6px 8px;border-radius:6px;border:1px solid #333;
    background:#1c1c26;color:#f2f2f2;font-size:13px;margin-bottom:14px;}
  .row{display:flex;align-items:center;gap:10px;margin-bottom:6px;}
  #play{background:#46c46e;color:#0b0b10;border:0;padding:6px 12px;border-radius:6px;
    font-weight:700;cursor:pointer;font-size:13px;}
  #play.playing{background:#e8a23a;}
  #month{flex:1;accent-color:#46c46e;}
  #mlabel{font-size:20px;font-weight:700;width:50px;text-align:right;color:#46c46e;}
  #stat{margin-top:12px;font-size:11.5px;color:#9fd;line-height:1.6;}
  #legend{bottom:26px;left:20px;background:rgba(15,15,22,.72);padding:11px 13px;
    border-radius:8px;font-size:12px;}
  #legend .bar{height:11px;width:190px;border-radius:3px;margin:6px 0 4px;
    background:linear-gradient(to right,rgb(20,40,90),rgb(40,110,180),
      rgb(80,170,200),rgb(180,220,160),rgb(255,220,80));}
  #legend .ticks{display:flex;justify-content:space-between;color:#cfcfcf;}
  #legend .cite{margin-top:9px;font-size:9.5px;color:#8aa894;line-height:1.5;max-width:225px;}
  #attrib{bottom:6px;right:8px;font-size:10px;color:#aaa;}
</style>
</head>
<body>
<div id="map"></div>
<div id="title" class="panel">
  <h1>台灣鳥類季節律動</h1>
  <p>GBIF occurrence · 資料更新 __FETCHED__</p>
</div>
<div id="controls" class="panel">
  <label>物種</label>
  <select id="species"></select>
  <label>月份(拖曳或按 Play)</label>
  <div class="row">
    <button id="play">▶</button>
    <input id="month" type="range" min="1" max="12" value="1" step="1" />
    <div id="mlabel">1月</div>
  </div>
  <div id="stat"></div>
</div>
<div id="legend" class="panel">
  <div>觀測密度（每 H3 格,對數色階）</div>
  <div class="bar"></div>
  <div class="ticks"><span>少</span><span id="legmax">多</span></div>
  <div class="cite">資料 GBIF.org · 存取 __FETCHED__ · 含 CC BY-NC 4.0 授權,僅供非商業使用</div>
</div>
<div id="attrib" class="panel">資料來源 GBIF · 底圖 © CARTO © OpenStreetMap</div>

<script>
const P = __PAYLOAD__;
const HEXES = P.hexes;
const DATA = P.data;          // [{s,h,m,c}, ...]
const SPECIES = P.species;    // [{zh,name,type,total}, ...]

// 預先 group by 物種 → 索引,加速每月篩選
const BY_SPECIES = SPECIES.map((_, i) => DATA.filter(r => r.s === i));

const RAMP = [[20,40,90],[40,110,180],[80,170,200],[180,220,160],[255,220,80]];
let curMaxLog = 1;
function colorFor(c){
  const t = Math.min(1, Math.log1p(c) / curMaxLog);
  const x = t * (RAMP.length - 1), i = Math.floor(x), f = x - i;
  const a = RAMP[i], b = RAMP[Math.min(i + 1, RAMP.length - 1)];
  return [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f, 235];
}

const sel = document.getElementById("species");
SPECIES.forEach((s, i) => sel.add(new Option(`${s.zh}  ${s.name}  · ${s.type}`, String(i))));

const map = new maplibregl.Map({
  container: "map",
  style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  center: __CENTER__, zoom: __ZOOM__, pitch: 48, bearing: -12, antialias: true
});
const lighting = new deck.LightingEffect({
  ambient: new deck.AmbientLight({ color: [255,255,255], intensity: 1.1 }),
  sun: new deck.DirectionalLight({ color: [255,255,255], intensity: 1.4, direction: [-1,-3,-1] })
});
const overlay = new deck.MapboxOverlay({
  interleaved: false, effects: [lighting], layers: [],
  getTooltip: ({object}) => object && {
    html: `觀測數 <b>${object.count}</b>`,
    style: {background:"rgba(15,15,22,.9)",color:"#fff",padding:"6px 9px",borderRadius:"6px"}
  }
});
map.addControl(overlay);
map.addControl(new maplibregl.NavigationControl({visualizePitch:true}), "bottom-right");

// 每物種、每月先預算好 hex → count,避免 Play 動畫每幀重 filter
const CACHE = new Map();   // `${s}|${m}` → Map<hex, count>
function getMonthMap(s, m) {
  const k = `${s}|${m}`;
  if (CACHE.has(k)) return CACHE.get(k);
  const acc = new Map();
  for (const r of BY_SPECIES[s]) {
    if (r.m !== m) continue;
    acc.set(r.h, (acc.get(r.h) || 0) + r.c);
  }
  CACHE.set(k, acc);
  return acc;
}

// 每物種的「最熱單月格」當該物種的色階上限,跨月份視覺一致(動畫不會跳)
const SPECIES_MAX = SPECIES.map((_, s) => {
  let mx = 1;
  for (let m = 1; m <= 12; m++) {
    for (const c of getMonthMap(s, m).values()) if (c > mx) mx = c;
  }
  return mx;
});

function update() {
  const s = +sel.value, m = +mEl.value;
  const acc = getMonthMap(s, m);
  const arr = [...acc].map(([h, c]) => ({polygon: HEXES[h], count: c}));
  const monthMax = arr.reduce((mx, d) => Math.max(mx, d.count), 1);
  curMaxLog = Math.log1p(SPECIES_MAX[s]);
  overlay.setProps({layers: [new deck.PolygonLayer({
    id: "bird-h3", data: arr, pickable: true, extruded: true, filled: true,
    getPolygon: d => d.polygon,
    getFillColor: d => colorFor(d.count),
    getElevation: d => d.count, elevationScale: __ELEV__, opacity: 0.9,
    material: {ambient:0.5, diffuse:0.6, shininess:32, specularColor:[60,60,60]},
    updateTriggers: {getFillColor:[s], getElevation:[s,m]}
  })]});
  document.getElementById("mlabel").textContent = `${m}月`;
  document.getElementById("legmax").textContent = `多（最高 ${SPECIES_MAX[s]}）`;
  const total = arr.reduce((t, d) => t + d.count, 0);
  document.getElementById("stat").innerHTML =
    `${SPECIES[s].zh} · ${m}月<br>觀測 <b>${total.toLocaleString()}</b> 筆 · 佔 <b>${arr.length}</b> 格 · 月最高 <b>${monthMax}</b>`;
}

const mEl = document.getElementById("month");
mEl.addEventListener("input", update);
sel.addEventListener("change", update);

// Play 動畫
const playBtn = document.getElementById("play");
let timer = null;
playBtn.addEventListener("click", () => {
  if (timer) {
    clearInterval(timer); timer = null;
    playBtn.textContent = "▶"; playBtn.classList.remove("playing");
  } else {
    playBtn.textContent = "⏸"; playBtn.classList.add("playing");
    timer = setInterval(() => {
      const next = (+mEl.value % 12) + 1;
      mEl.value = next; update();
    }, 800);
  }
});

update();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
