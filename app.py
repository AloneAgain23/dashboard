import base64, json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

class Payload(BaseModel):
    start: str
    end: str
    variable: int = Field(..., ge=1, le=8)
    noticias_json: dict

def to_b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")

@app.post("/generate_outputs")
def generate_outputs(p: Payload):
    data = p.noticias_json
    if "metadata" not in data or "noticias" not in data:
        raise HTTPException(status_code=400, detail="noticias_json debe tener metadata y noticias")

    # 1) archivo JSON
    json_filename = f"noticias_v{p.variable}_{p.start}_{p.end}.json"
    json_text = json.dumps(data, ensure_ascii=False, indent=2)

    # 2) tu HTML (plantilla)
    html_filename = f"dashboard_v{p.variable}_{p.start}_{p.end}.html"
    with open("dashboard_template.html", "r", encoding="utf-8") as f:
        html_template = f.read()

    # OPCIÓN A: inyectar JSON si tu plantilla tiene __JSON_DATA__
    # Si NO quieres inyección, comenta estas 2 líneas y deja el HTML tal cual.
    injected_json = json.dumps(data, ensure_ascii=False)
    html_text = html_template.replace("__JSON_DATA__", injected_json)

    return {
        "openaiFileResponse": [
            {
                "name": json_filename,
                "mime_type": "application/json",
                "content_base64": to_b64(json_text),
            },
            {
                "name": html_filename,
                "mime_type": "text/html",
                "content_base64": to_b64(html_text),
            },
        ]
    }