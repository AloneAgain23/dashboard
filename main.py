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

# In-memory storage: {session_id: {"data": {...}, "expires": datetime}}
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
    noticias_json: Any  # accepts object or string


@app.get("/")
def root():
    return {"status": "ok", "service": "Vigilancia Prospectiva API"}


@app.post("/generateOutputs")
def generate_outputs(req: GenerateRequest):
    cleanup_sessions()

    # Accept noticias_json as object or JSON string
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

    # Render base URL — works both locally and on Render
    # We build a relative path; ChatGPT will see the full URL
    view_path = f"/view/{session_id}"

    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "view_url": view_path,
        "message": f"Reporte generado. Abre: {view_path}",
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
        return HTMLResponse("""
        <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
        <title>Sesión expirada</title>
        <style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#0f0f0f;color:#fff;}
        .box{text-align:center;padding:2rem;} h1{color:#e53e3e;} p{color:#aaa;}</style></head>
        <body><div class="box"><h1>⚠️ Sesión no disponible</h1>
        <p>Esta sesión expiró o no existe. Genera un nuevo reporte desde ChatGPT.</p></div></body></html>
        """, status_code=404)

    s = sessions[session_id]
    noticias = s["data"].get("noticias", [])
    metadata = s["data"].get("metadata", {})

    # Serialize data for embedding in HTML
    data_json = json.dumps(s["data"], ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Vigilancia Prospectiva — {s['start']} / {s['end']}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500&family=Lora:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #080b0f;
      --surface: #0e1318;
      --surface2: #151c24;
      --border: #1e2a35;
      --accent: #00d4ff;
      --accent2: #ff6b35;
      --accent3: #7fff6b;
      --text: #e8edf2;
      --muted: #5a6a78;
      --h1c: #ff6b35;
      --h2c: #00d4ff;
      --h3c: #7fff6b;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'Lora', serif;
      font-size: 15px;
      line-height: 1.7;
      min-height: 100vh;
    }}

    /* NOISE OVERLAY */
    body::before {{
      content: '';
      position: fixed; inset: 0;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
      pointer-events: none; z-index: 0;
    }}

    /* HEADER */
    header {{
      position: sticky; top: 0; z-index: 100;
      background: rgba(8,11,15,0.92);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 1rem 2rem;
      display: flex; align-items: center; justify-content: space-between;
      gap: 1rem;
    }}
    .logo {{
      font-family: 'Syne', sans-serif;
      font-weight: 800;
      font-size: 1.1rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent);
    }}
    .logo span {{ color: var(--accent2); }}
    .date-badge {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.72rem;
      color: var(--muted);
      background: var(--surface2);
      border: 1px solid var(--border);
      padding: 0.3rem 0.7rem;
      border-radius: 4px;
    }}

    /* HERO */
    .hero {{
      position: relative;
      padding: 4rem 2rem 3rem;
      max-width: 1200px;
      margin: 0 auto;
    }}
    .hero-label {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.7rem;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 0.8rem;
    }}
    .hero h1 {{
      font-family: 'Syne', sans-serif;
      font-size: clamp(2rem, 5vw, 3.5rem);
      font-weight: 800;
      line-height: 1.1;
      color: var(--text);
      margin-bottom: 1.5rem;
    }}
    .hero h1 em {{ font-style: normal; color: var(--accent); }}

    /* STATS BAR */
    .stats-bar {{
      display: flex; flex-wrap: wrap; gap: 1rem;
      margin-bottom: 2rem;
    }}
    .stat {{
      background: var(--surface2);
      border: 1px solid var(--border);
      padding: 0.8rem 1.2rem;
      border-radius: 6px;
      flex: 1; min-width: 130px;
    }}
    .stat-num {{
      font-family: 'Syne', sans-serif;
      font-size: 1.8rem;
      font-weight: 800;
      color: var(--accent);
      line-height: 1;
    }}
    .stat-label {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.65rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--muted);
      margin-top: 0.2rem;
    }}

    /* FILTERS */
    .filters {{
      max-width: 1200px;
      margin: 0 auto 2rem;
      padding: 0 2rem;
      display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center;
    }}
    .filter-label {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.65rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
      margin-right: 0.3rem;
    }}
    .filter-btn {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.7rem;
      padding: 0.3rem 0.8rem;
      border-radius: 3px;
      border: 1px solid var(--border);
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      transition: all 0.15s;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .filter-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
    .filter-btn.active {{ background: var(--accent); border-color: var(--accent); color: var(--bg); font-weight: 600; }}
    .filter-btn.h1.active {{ background: var(--h1c); border-color: var(--h1c); }}
    .filter-btn.h2.active {{ background: var(--h2c); border-color: var(--h2c); color: var(--bg); }}
    .filter-btn.h3.active {{ background: var(--h3c); border-color: var(--h3c); color: var(--bg); }}

    /* SEARCH */
    .search-wrap {{
      max-width: 1200px;
      margin: 0 auto 2rem;
      padding: 0 2rem;
    }}
    .search-input {{
      width: 100%; max-width: 480px;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.6rem 1rem;
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.8rem;
      color: var(--text);
      outline: none;
      transition: border-color 0.15s;
    }}
    .search-input:focus {{ border-color: var(--accent); }}
    .search-input::placeholder {{ color: var(--muted); }}

    /* GRID */
    .grid {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 2rem 4rem;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 1.2rem;
    }}

    /* CARD */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.4rem;
      display: flex; flex-direction: column; gap: 0.8rem;
      transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
      position: relative;
      overflow: hidden;
      animation: fadeUp 0.4s ease both;
    }}
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .card:hover {{
      transform: translateY(-3px);
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }}
    .card.h1 {{ border-left: 3px solid var(--h1c); }}
    .card.h1:hover {{ border-color: var(--h1c); box-shadow: 0 8px 32px rgba(255,107,53,0.12); }}
    .card.h2 {{ border-left: 3px solid var(--h2c); }}
    .card.h2:hover {{ border-color: var(--h2c); box-shadow: 0 8px 32px rgba(0,212,255,0.12); }}
    .card.h3 {{ border-left: 3px solid var(--h3c); }}
    .card.h3:hover {{ border-color: var(--h3c); box-shadow: 0 8px 32px rgba(127,255,107,0.12); }}

    .card-top {{
      display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;
    }}
    .hyp-badge {{
      font-family: 'Syne', sans-serif;
      font-size: 0.65rem;
      font-weight: 700;
      padding: 0.2rem 0.55rem;
      border-radius: 3px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}
    .hyp-badge.h1 {{ background: rgba(255,107,53,0.15); color: var(--h1c); }}
    .hyp-badge.h2 {{ background: rgba(0,212,255,0.15); color: var(--h2c); }}
    .hyp-badge.h3 {{ background: rgba(127,255,107,0.15); color: var(--h3c); }}

    .source-badge {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.62rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .card-title {{
      font-family: 'Lora', serif;
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--text);
      line-height: 1.5;
    }}
    .card-precursor {{
      font-size: 0.82rem;
      color: var(--muted);
      font-style: italic;
      border-left: 2px solid var(--border);
      padding-left: 0.7rem;
    }}
    .card-footer {{
      display: flex; align-items: center; justify-content: space-between;
      gap: 0.5rem; margin-top: auto;
    }}
    .card-meta {{
      display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap;
    }}
    .meta-chip {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.62rem;
      color: var(--muted);
      background: var(--surface2);
      border: 1px solid var(--border);
      padding: 0.15rem 0.5rem;
      border-radius: 3px;
    }}
    .card-link {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.65rem;
      color: var(--accent);
      text-decoration: none;
      padding: 0.3rem 0.7rem;
      border: 1px solid var(--accent);
      border-radius: 3px;
      white-space: nowrap;
      transition: all 0.15s;
    }}
    .card-link:hover {{ background: var(--accent); color: var(--bg); }}

    /* EMPTY STATE */
    .empty {{
      grid-column: 1/-1;
      text-align: center;
      padding: 4rem;
      color: var(--muted);
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.85rem;
    }}

    /* FOOTER */
    footer {{
      border-top: 1px solid var(--border);
      padding: 1.5rem 2rem;
      text-align: center;
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.65rem;
      color: var(--muted);
      letter-spacing: 0.08em;
    }}

    @media (max-width: 600px) {{
      .grid {{ grid-template-columns: 1fr; padding: 0 1rem 3rem; }}
      .hero {{ padding: 2rem 1rem 1.5rem; }}
      .filters, .search-wrap {{ padding: 0 1rem; }}
      header {{ padding: 0.8rem 1rem; }}
    }}
  </style>
</head>
<body>

<header>
  <div class="logo">Vigilancia <span>Prospectiva</span></div>
  <div class="date-badge">{s['start']} — {s['end']}</div>
</header>

<div class="hero">
  <div class="hero-label">▸ Reporte de inteligencia</div>
  <h1>Monitor de <em>Noticias</em><br>Geopolíticas</h1>
  <div class="stats-bar" id="statsBar"></div>
</div>

<div class="search-wrap">
  <input class="search-input" id="searchInput" type="text" placeholder="Buscar por título, país, fuente…"/>
</div>

<div class="filters" id="filterBar">
  <span class="filter-label">Filtrar:</span>
  <button class="filter-btn active" data-filter="all">Todas</button>
  <button class="filter-btn h1" data-filter="H1">H1</button>
  <button class="filter-btn h2" data-filter="H2">H2</button>
  <button class="filter-btn h3" data-filter="H3">H3</button>
</div>

<div class="grid" id="grid"></div>

<footer id="footer"></footer>

<script>
const RAW = {data_json};
const noticias = RAW.noticias || [];
const meta = RAW.metadata || {{}};

// STATS
function buildStats() {{
  const h1 = noticias.filter(n => n.Hipotesis === 'H1').length;
  const h2 = noticias.filter(n => n.Hipotesis === 'H2').length;
  const h3 = noticias.filter(n => n.Hipotesis === 'H3').length;
  const sources = [...new Set(noticias.map(n => n.Fuente || n.fuente).filter(Boolean))].length;
  const bar = document.getElementById('statsBar');
  [
    [noticias.length, 'Total noticias'],
    [h1, 'Hipótesis 1'],
    [h2, 'Hipótesis 2'],
    [h3, 'Hipótesis 3'],
    [sources, 'Fuentes activas'],
  ].forEach(([num, label]) => {{
    bar.innerHTML += `<div class="stat"><div class="stat-num">${{num}}</div><div class="stat-label">${{label}}</div></div>`;
  }});
}}

// CARD
function card(n, i) {{
  const hyp = (n.Hipotesis || n.hipotesis || '').toUpperCase();
  const hc = hyp === 'H1' ? 'h1' : hyp === 'H2' ? 'h2' : 'h3';
  const title = n['Hecho/Titular'] || n.titulo || n.title || '—';
  const source = n.Fuente || n.fuente || '—';
  const date = n.Fecha || n.fecha || '—';
  const country = n.País || n.pais || n.country || '—';
  const precursor = n['Hecho precursor'] || n.precursor || '';
  const link = n.Enlace || n.enlace || n.url || '#';
  return `
    <div class="card ${{hc}}" style="animation-delay:${{i * 0.04}}s" 
         data-hyp="${{hyp}}" data-title="${{title.toLowerCase()}}" 
         data-source="${{source.toLowerCase()}}" data-country="${{country.toLowerCase()}}">
      <div class="card-top">
        <span class="hyp-badge ${{hc}}">${{hyp || '—'}}</span>
        <span class="source-badge">${{source}}</span>
      </div>
      <div class="card-title">${{title}}</div>
      ${{precursor ? `<div class="card-precursor">${{precursor}}</div>` : ''}}
      <div class="card-footer">
        <div class="card-meta">
          <span class="meta-chip">📅 ${{date}}</span>
          <span class="meta-chip">🌍 ${{country}}</span>
        </div>
        ${{link !== '#' ? `<a class="card-link" href="${{link}}" target="_blank" rel="noopener">Ver →</a>` : ''}}
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
let activeFilter = 'all';
let searchTerm = '';

function applyFilters() {{
  let result = noticias;
  if (activeFilter !== 'all') result = result.filter(n => (n.Hipotesis||n.hipotesis||'').toUpperCase() === activeFilter);
  if (searchTerm) {{
    const q = searchTerm.toLowerCase();
    result = result.filter(n => {{
      const title = (n['Hecho/Titular']||n.titulo||'').toLowerCase();
      const src = (n.Fuente||n.fuente||'').toLowerCase();
      const country = (n.País||n.pais||'').toLowerCase();
      return title.includes(q) || src.includes(q) || country.includes(q);
    }});
  }}
  render(result);
}}

document.getElementById('filterBar').addEventListener('click', e => {{
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

// FOOTER
function buildFooter() {{
  const f = document.getElementById('footer');
  const gen = meta.generated_at ? new Date(meta.generated_at).toLocaleString('es-PE') : '—';
  const model = meta.model || '—';
  f.textContent = `Generado: ${{gen}} · Modelo: ${{model}} · Sesión válida 24h`;
}}

buildStats();
render(noticias);
buildFooter();
</script>
</body>
</html>"""
    return HTMLResponse(html)
