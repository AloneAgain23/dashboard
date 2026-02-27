import base64, json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

class Payload(BaseModel):
    start: str
    end: str
    variable: int = Field(..., ge=1, le=8)
    noticias_json_text: str  # <-- JSON como texto

def to_b64(text: str) -> str:
    import base64
    return base64.b64encode(text.encode("utf-8")).decode("ascii")

@app.post("/generate_outputs")
def generate_outputs(p: Payload):
    try:
        data = json.loads(p.noticias_json_text)  # <-- parsea el texto
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON inválido: {e}")

    if "metadata" not in data or "noticias" not in data:
        raise HTTPException(status_code=400, detail="El JSON debe tener metadata y noticias")

    # Limpieza básica de enlaces (evita saltos de línea)
    for n in data.get("noticias", []):
        if "Enlace" in n and isinstance(n["Enlace"], str):
            n["Enlace"] = n["Enlace"].strip().replace("\n", "").replace("\r", "")

    json_filename = f"noticias_v{p.variable}_{p.start}_{p.end}.json"
    json_text = json.dumps(data, ensure_ascii=False, indent=2)

    html_filename = f"dashboard_v{p.variable}_{p.start}_{p.end}.html"
    with open("dashboard_geopolitico_inyectado.html", "r", encoding="utf-8") as f:
        html_template = f.read()

    injected_json = json.dumps(data, ensure_ascii=False)
    html_text = html_template.replace("__JSON_DATA__", injected_json)

    return {
        "openaiFileResponse": [
            {"name": json_filename, "mime_type": "application/json", "content_base64": to_b64(json_text)},
            {"name": html_filename, "mime_type": "text/html", "content_base64": to_b64(html_text)},
        ]
    }
