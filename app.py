from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional
import uuid
import json
from datetime import datetime, timedelta

app = FastAPI(title="Vigilancia Prospectiva API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}
SESSION_TTL_HOURS = 24


def cleanup_sessions():
    now = datetime.utcnow()
    expired = [k for k, v in sessions.items() if v["expires"] < now]
    for k in expired:
        del sessions[k]


class GenerateRequest(BaseModel):
    start: str
    end: str
    variable: Optional[str] = None
    noticias_json: Any


@app.get("/")
def root():
    return {"status": "ok", "service": "Vigilancia Prospectiva API"}


@app.post("/generateOutputs")
def generate_outputs(req: GenerateRequest):
    cleanup_sessions()

    if isinstance(req.noticias_json, str):
        try:
            data = json.loads(req.noticias_json)
        except Exception:
            raise HTTPException(status_code=400, detail="noticias_json is not valid JSON string")
    else:
        data = req.noticias_json

    session_id = str(uuid.uuid4()).replace("-", "")[:16]
    sessions[session_id] = {
        "data": data,
        "start": req.start,
        "end": req.end,
        "variable": req.variable or "",
        "expires": datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS),
    }

    BASE_URL = "https://dashboard-rmj8.onrender.com"
    view_path = f"{BASE_URL}/view/{session_id}"

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "view_url": view_path,
        "message": f"Reporte listo. Abre este enlace: {view_path}",
        "total_news": data.get("metadata", {}).get("total_news", "?"),
    })


@app.get("/data/{session_id}")
def get_data(session_id: str):
    cleanup_sessions()
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")
    s = sessions[session_id]
    return JSONResponse({**s["data"], "_meta": {"start": s["start"], "end": s["end"], "variable": s["variable"]}})


@app.get("/view/{session_id}", response_class=HTMLResponse)
def view_report(session_id: str):
    cleanup_sessions()
    if session_id not in sessions:
        return HTMLResponse("""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>Sesión expirada</title>
<style>
  body{font-family:'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;
  min-height:100vh;margin:0;background:#f5f5f5;}
  .box{text-align:center;padding:3rem;background:#fff;border-radius:12px;
  box-shadow:0 4px 24px rgba(0,0,0,0.08);max-width:400px;}
  h1{color:#C8102E;font-size:1.4rem;margin-bottom:1rem;}
  p{color:#666;font-size:0.9rem;}
</style></head>
<body><div class="box">
  <h1>⚠️ Sesión no disponible</h1>
  <p>Esta sesión expiró o no existe.<br>Genera un nuevo reporte desde ChatGPT.</p>
</div></body></html>""", status_code=404)

    s = sessions[session_id]
    data_json = json.dumps(s["data"], ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Monitor de Noticias — CEPLAN</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
  <style>
    :root {{
      --rojo:       #C8102E;
      --rojo-dark:  #9B0B22;
      --rojo-light: #FDF0F2;
      --rojo-mid:   #E8C0C8;
      --gris:       #F7F7F7;
      --gris2:      #EFEFEF;
      --borde:      #E0E0E0;
      --texto:      #1A1A1A;
      --muted:      #6B6B6B;
      --blanco:     #FFFFFF;
      --h1:         #C8102E;
      --h2:         #D4700A;
      --h3:         #1A7A3C;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      background: var(--gris);
      color: var(--texto);
      font-family: 'Source Sans 3', sans-serif;
      font-size: 15px;
      line-height: 1.6;
    }}

    /* HEADER */
    header {{
      background: var(--rojo);
      position: sticky; top: 0; z-index: 100;
      box-shadow: 0 2px 12px rgba(200,16,46,0.35);
    }}
    .header-inner {{
      max-width: 1280px; margin: 0 auto;
      padding: 0.85rem 2rem;
      display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
    }}
    .header-left {{ display: flex; align-items: center; gap: 1rem; }}
    .header-title {{
      font-size: 1rem; font-weight: 700;
      letter-spacing: 0.04em; text-transform: uppercase; color: #fff;
      border-left: 2px solid rgba(255,255,255,0.4); padding-left: 1rem;
    }}
    .header-title span {{
      display: block; font-size: 0.63rem; font-weight: 400;
      opacity: 0.82; letter-spacing: 0.08em; margin-top: 1px;
    }}
    .date-badge {{
      background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.35);
      border-radius: 4px; padding: 0.3rem 0.8rem;
      font-size: 0.75rem; font-weight: 600; letter-spacing: 0.05em; color: #fff;
    }}

    /* HERO */
    .hero {{
      background: var(--blanco);
      border-bottom: 4px solid var(--rojo);
      padding: 2rem 2rem 1.5rem;
    }}
    .hero-inner {{ max-width: 1280px; margin: 0 auto; }}
    .hero-eyebrow {{
      font-size: 0.68rem; font-weight: 700;
      letter-spacing: 0.18em; text-transform: uppercase;
      color: var(--rojo); margin-bottom: 0.4rem;
    }}
    .hero h1 {{
      font-family: 'Source Serif 4', serif;
      font-size: clamp(1.7rem, 3.5vw, 2.6rem);
      font-weight: 600; color: var(--texto); line-height: 1.15; margin-bottom: 0.5rem;
    }}
    .hero h1 em {{ font-style: normal; color: var(--rojo); }}
    .variable-tag {{
      display: inline-block;
      background: var(--rojo-light); border: 1px solid var(--rojo-mid);
      color: var(--rojo-dark);
      font-size: 0.72rem; font-weight: 700;
      letter-spacing: 0.1em; text-transform: uppercase;
      padding: 0.25rem 0.8rem; border-radius: 3px;
    }}

    /* STATS */
    .stats-bar {{
      max-width: 1280px; margin: 1.5rem auto 0;
      padding: 0 2rem;
      display: flex; flex-wrap: wrap; gap: 1rem;
    }}
    .stat {{
      background: var(--blanco);
      border: 1px solid var(--borde);
      border-top: 3px solid var(--rojo);
      border-radius: 6px;
      padding: 1rem 1.4rem;
      flex: 1; min-width: 110px;
    }}
    .stat-num {{
      font-family: 'Source Serif 4', serif;
      font-size: 2rem; font-weight: 600; color: var(--rojo); line-height: 1;
    }}
    .stat-label {{
      font-size: 0.65rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.1em;
      color: var(--muted); margin-top: 0.2rem;
    }}

    /* TOOLBAR */
    .toolbar {{
      max-width: 1280px; margin: 1.5rem auto 1rem;
      padding: 0 2rem;
      display: flex; flex-wrap: wrap; gap: 0.7rem; align-items: center;
    }}
    .filter-group {{ display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }}
    .filter-label {{
      font-size: 0.67rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted);
    }}
    .filter-btn {{
      font-family: 'Source Sans 3', sans-serif;
      font-size: 0.72rem; font-weight: 700;
      padding: 0.32rem 0.9rem; border-radius: 4px;
      border: 1.5px solid var(--borde);
      background: var(--blanco); color: var(--muted);
      cursor: pointer; text-transform: uppercase; letter-spacing: 0.08em;
      transition: all 0.14s;
    }}
    .filter-btn:hover {{ border-color: var(--rojo); color: var(--rojo); }}
    .filter-btn.active {{ background: var(--rojo); border-color: var(--rojo); color: #fff; }}
    .filter-btn.h1.active {{ background: var(--h1); border-color: var(--h1); color: #fff; }}
    .filter-btn.h2.active {{ background: var(--h2); border-color: var(--h2); color: #fff; }}
    .filter-btn.h3.active {{ background: var(--h3); border-color: var(--h3); color: #fff; }}

    .search-input {{
      flex: 1; min-width: 200px; max-width: 340px;
      background: var(--blanco); border: 1.5px solid var(--borde);
      border-radius: 4px; padding: 0.4rem 0.9rem;
      font-family: 'Source Sans 3', sans-serif; font-size: 0.82rem;
      color: var(--texto); outline: none; transition: border-color 0.14s;
    }}
    .search-input:focus {{ border-color: var(--rojo); }}
    .search-input::placeholder {{ color: #bbb; }}

    .btn-excel {{
      margin-left: auto;
      display: flex; align-items: center; gap: 0.4rem;
      background: var(--blanco); border: 1.5px solid #1D6F42; color: #1D6F42;
      border-radius: 4px; padding: 0.4rem 1rem;
      font-family: 'Source Sans 3', sans-serif;
      font-size: 0.75rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.08em;
      cursor: pointer; transition: all 0.14s;
    }}
    .btn-excel:hover {{ background: #1D6F42; color: #fff; }}

    /* GRID */
    .grid {{
      max-width: 1280px; margin: 0 auto;
      padding: 0 2rem 4rem;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 1.2rem;
    }}

    /* CARD */
    .card {{
      background: var(--blanco);
      border: 1px solid var(--borde);
      border-radius: 8px; overflow: hidden;
      display: flex; flex-direction: column;
      transition: box-shadow 0.18s, transform 0.18s;
      animation: fadeUp 0.35s ease both;
    }}
    @keyframes fadeUp {{
      from {{ opacity:0; transform:translateY(14px); }}
      to   {{ opacity:1; transform:translateY(0); }}
    }}
    .card:hover {{
      transform: translateY(-3px);
      box-shadow: 0 8px 28px rgba(200,16,46,0.13);
    }}
    .card-stripe {{ height: 4px; background: var(--rojo); }}
    .card.h1 .card-stripe {{ background: var(--h1); }}
    .card.h2 .card-stripe {{ background: var(--h2); }}
    .card.h3 .card-stripe {{ background: var(--h3); }}

    .card-body {{
      padding: 1.2rem; flex: 1;
      display: flex; flex-direction: column; gap: 0.75rem;
    }}
    .card-top {{
      display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;
    }}
    .hyp-badge {{
      font-size: 0.62rem; font-weight: 700;
      padding: 0.18rem 0.55rem; border-radius: 3px;
      text-transform: uppercase; letter-spacing: 0.1em;
    }}
    .hyp-badge.h1 {{ background:#FDECEA; color:var(--h1); }}
    .hyp-badge.h2 {{ background:#FFF3E6; color:var(--h2); }}
    .hyp-badge.h3 {{ background:#E8F5EC; color:var(--h3); }}

    .source-chip {{
      font-size: 0.62rem; font-weight: 700;
      color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em;
      background: var(--gris2); border: 1px solid var(--borde);
      padding: 0.15rem 0.5rem; border-radius: 3px;
    }}
    .card-title {{
      font-family: 'Source Serif 4', serif;
      font-size: 0.97rem; font-weight: 600;
      color: var(--texto); line-height: 1.5;
    }}

    /* PRECURSOR */
    .precursor-block {{
      background: var(--rojo-light);
      border-left: 3px solid var(--rojo-mid);
      border-radius: 0 4px 4px 0;
      padding: 0.65rem 0.85rem;
    }}
    .precursor-label {{
      font-size: 0.6rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.14em;
      color: var(--rojo); margin-bottom: 0.3rem;
    }}
    .precursor-text {{
      font-size: 0.83rem; color: #5a1a25;
      line-height: 1.5; font-style: italic;
    }}

    /* CARD FOOTER */
    .card-footer {{
      display: flex; align-items: center; justify-content: space-between;
      gap: 0.5rem; flex-wrap: wrap;
      padding: 0.7rem 1.2rem;
      border-top: 1px solid var(--gris2);
      background: var(--gris);
    }}
    .meta-row {{ display: flex; gap: 0.5rem; flex-wrap: wrap; }}
    .meta-chip {{
      font-size: 0.63rem; color: var(--muted);
      background: var(--blanco); border: 1px solid var(--borde);
      padding: 0.15rem 0.5rem; border-radius: 3px;
    }}
    .card-link {{
      font-size: 0.68rem; font-weight: 700;
      color: var(--rojo); text-decoration: none;
      padding: 0.3rem 0.8rem;
      border: 1.5px solid var(--rojo);
      border-radius: 4px; white-space: nowrap;
      text-transform: uppercase; letter-spacing: 0.06em;
      transition: all 0.14s;
    }}
    .card-link:hover {{ background: var(--rojo); color: #fff; }}

    /* EMPTY */
    .empty {{
      grid-column: 1/-1; text-align: center;
      padding: 4rem 1rem; color: var(--muted); font-size: 0.9rem;
    }}

    /* FOOTER */
    footer {{
      background: var(--rojo-dark); color: rgba(255,255,255,0.75);
      padding: 1.2rem 2rem; text-align: center;
      font-size: 0.68rem; letter-spacing: 0.06em;
    }}

    @media (max-width: 640px) {{
      .grid {{ grid-template-columns: 1fr; padding: 0 1rem 3rem; }}
      .hero {{ padding: 1.5rem 1rem 1rem; }}
      .stats-bar, .toolbar {{ padding: 0 1rem; }}
      .header-inner {{ padding: 0.8rem 1rem; }}
      .btn-excel {{ margin-left: 0; }}
    }}
  </style>
</head>
<body>

<header>
  <div class="header-inner">
    <div class="header-left">
      <div class="header-title">
        Monitor de Noticias
        <span>CEPLAN — Centro Nacional de Planeamiento Estratégico</span>
      </div>
    </div>
    <div class="date-badge">{s['start']} &mdash; {s['end']}</div>
  </div>
</header>

<div class="hero">
  <div class="hero-inner">
    <div class="hero-eyebrow">▸ Vigilancia Prospectiva</div>
    <h1>Reporte de <em>Inteligencia</em> Geopolítica</h1>
    <div class="variable-tag" id="varTag"></div>
  </div>
</div>

<div class="stats-bar" id="statsBar"></div>

<div class="toolbar">
  <div class="filter-group">
    <span class="filter-label">Filtrar:</span>
    <button class="filter-btn active" data-filter="all">Todas</button>
    <button class="filter-btn h1" data-filter="H1">H1</button>
    <button class="filter-btn h2" data-filter="H2">H2</button>
    <button class="filter-btn h3" data-filter="H3">H3</button>
  </div>
  <input class="search-input" id="searchInput" type="text" placeholder="Buscar por título, país, fuente, precursor…"/>
  <button class="btn-excel" id="btnExcel">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
    Descargar Excel
  </button>
</div>

<div class="grid" id="grid"></div>

<footer id="footer"></footer>

<script>
const RAW = {data_json};
const noticias = RAW.noticias || [];
const meta = RAW.metadata || {{}};

// Variable tag
(function() {{
  const el = document.getElementById('varTag');
  const v = "{s['variable']}";
  if (v) el.textContent = v; else el.style.display = 'none';
}})();

// STATS
(function() {{
  const counts = {{H1:0, H2:0, H3:0}};
  noticias.forEach(n => {{
    const h = (n.Hipotesis||n.hipotesis||'').toUpperCase();
    if (counts[h] !== undefined) counts[h]++;
  }});
  const srcs = new Set(noticias.map(n => n.Fuente||n.fuente).filter(Boolean)).size;
  const bar = document.getElementById('statsBar');
  [[noticias.length,'Total Noticias'],[counts.H1,'Hipótesis 1'],
   [counts.H2,'Hipótesis 2'],[counts.H3,'Hipótesis 3'],[srcs,'Fuentes']].forEach(([n,l]) => {{
    const d = document.createElement('div');
    d.className = 'stat';
    d.innerHTML = `<div class="stat-num">${{n}}</div><div class="stat-label">${{l}}</div>`;
    bar.appendChild(d);
  }});
}})();

// CARD
function card(n, i) {{
  const hyp = (n.Hipotesis||n.hipotesis||'').toUpperCase();
  const hc = hyp==='H1'?'h1':hyp==='H2'?'h2':'h3';
  const title = n['Hecho/Titular']||n.titulo||'—';
  const source = n.Fuente||n.fuente||'—';
  const date = n.Fecha||n.fecha||'—';
  const country = n.País||n.pais||'—';
  const precursor = n['Hecho precursor']||n.precursor||'';
  const link = n.Enlace||n.enlace||'#';
  const delay = Math.min(i*0.04, 0.6);
  return `
  <div class="card ${{hc}}" style="animation-delay:${{delay}}s"
       data-hyp="${{hyp}}" data-title="${{title.toLowerCase()}}"
       data-source="${{source.toLowerCase()}}" data-country="${{country.toLowerCase()}}"
       data-precursor="${{precursor.toLowerCase()}}">
    <div class="card-stripe"></div>
    <div class="card-body">
      <div class="card-top">
        <span class="hyp-badge ${{hc}}">${{hyp||'—'}}</span>
        <span class="source-chip">${{source}}</span>
      </div>
      <div class="card-title">${{title}}</div>
      ${{precursor ? `
      <div class="precursor-block">
        <div class="precursor-label">⚡ Hecho Precursor</div>
        <div class="precursor-text">${{precursor}}</div>
      </div>` : ''}}
    </div>
    <div class="card-footer">
      <div class="meta-row">
        <span class="meta-chip">📅 ${{date}}</span>
        <span class="meta-chip">🌍 ${{country}}</span>
      </div>
      ${{link!=='#'?`<a class="card-link" href="${{link}}" target="_blank" rel="noopener">Ver nota →</a>`:''}}
    </div>
  </div>`;
}}

function render(list) {{
  const grid = document.getElementById('grid');
  if (!list.length) {{
    grid.innerHTML = '<div class="empty">No se encontraron noticias con ese criterio.</div>';
    return;
  }}
  grid.innerHTML = list.map((n,i) => card(n,i)).join('');
}}

// FILTER + SEARCH
let activeFilter = 'all', searchTerm = '';

function applyFilters() {{
  let r = noticias;
  if (activeFilter !== 'all')
    r = r.filter(n => (n.Hipotesis||n.hipotesis||'').toUpperCase() === activeFilter);
  if (searchTerm) {{
    const q = searchTerm.toLowerCase();
    r = r.filter(n => {{
      return (n['Hecho/Titular']||n.titulo||'').toLowerCase().includes(q)
          || (n.Fuente||n.fuente||'').toLowerCase().includes(q)
          || (n.País||n.pais||'').toLowerCase().includes(q)
          || (n['Hecho precursor']||n.precursor||'').toLowerCase().includes(q);
    }});
  }}
  render(r);
}}

document.querySelector('.toolbar').addEventListener('click', e => {{
  if (!e.target.matches('.filter-btn')) return;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  e.target.classList.add('active');
  activeFilter = e.target.dataset.filter;
  applyFilters();
}});

document.getElementById('searchInput').addEventListener('input', e => {{
  searchTerm = e.target.value.trim();
  applyFilters();
}});

// EXCEL EXPORT
document.getElementById('btnExcel').addEventListener('click', () => {{
  const rows = noticias.map(n => ({{
    'Hipótesis':       n.Hipotesis||n.hipotesis||'',
    'Hecho/Titular':   n['Hecho/Titular']||n.titulo||'',
    'Hecho Precursor': n['Hecho precursor']||n.precursor||'',
    'Fecha':           n.Fecha||n.fecha||'',
    'Fuente':          n.Fuente||n.fuente||'',
    'País':            n.País||n.pais||'',
    'Enlace':          n.Enlace||n.enlace||'',
  }}));
  const ws = XLSX.utils.json_to_sheet(rows);
  ws['!cols'] = [{{wch:8}},{{wch:62}},{{wch:55}},{{wch:13}},{{wch:14}},{{wch:20}},{{wch:60}}];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Noticias');
  const d = "{s['start']}_al_{s['end']}".replace(/-/g,'');
  XLSX.writeFile(wb, `Vigilancia_Prospectiva_${{d}}.xlsx`);
}});

// FOOTER
(function() {{
  const gen = meta.generated_at ? new Date(meta.generated_at).toLocaleString('es-PE') : '—';
  const errors = meta.stats?.errors ?? 0;
  document.getElementById('footer').innerHTML =
    `CEPLAN — Centro Nacional de Planeamiento Estratégico &nbsp;|&nbsp;
     Generado: ${{gen}} &nbsp;|&nbsp; Modelo: ${{meta.model||'—'}} &nbsp;|&nbsp;
     ${{meta.total_news||noticias.length}} noticias procesadas
     ${{errors>0 ? ' &nbsp;|&nbsp; ⚠️ '+errors+' errores' : ''}} &nbsp;|&nbsp; Sesión válida 24h`;
}})();

render(noticias);
</script>
</body>
</html>"""
    return HTMLResponse(html)

