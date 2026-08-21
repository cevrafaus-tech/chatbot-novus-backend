import os
import requests
from flask import Flask, jsonify, request
from supabase import Client, create_client

app = Flask(__name__)

SUPABASE_URL = "https://cvulaqxjpyemryrccyxb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN2dWxhcXhqcHllbXJ5cmNjeXhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3NjgyNzcsImV4cCI6MjEwMTM0NDI3N30.bZ6bFoJETc1GAJqh4RTqT2dFcjE9ZaBQgkE8AXZchh4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()


def get_openai_embedding(text):
    """Generates embedding via OpenAI API in <150ms instead of local CPU."""
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "text-embedding-3-small",
        "input": text
    }
    response = requests.post(url, headers=headers, json=payload, timeout=2.0)
    if response.status_code == 200:
        return response.json()["data"][0]["embedding"]
    return None


def generate_openai_response(system_prompt, user_query):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.0,
        "max_tokens": 120  # Menos tokens = generación en menos de 900 ms
    }
    # Aumentar a 3.8s para evitar el error de Read timed out
    response = requests.post(url, headers=headers, json=payload, timeout=3.8)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    raise Exception(f"OpenAI API Error: {response.text}")


@app.route("/", methods=["GET"])
def home():
    return "Universal Novus RAG Webhook Active on Render"


@app.route("/webhook", methods=["POST"])
def dialogflow_webhook():
    req = request.get_json(silent=True, force=True) or {}
    pregunta = req.get("queryResult", {}).get("queryText", "") or req.get("text", "")

    if not pregunta:
        return jsonify({"fulfillmentText": "No valid query was received."})

    try:
        # 1. Búsqueda directa por texto y filtro de modelo (Ultra rápido, <100ms)
        modelo_detectado = None
        for m in ["N1040", "N1030", "N1050", "N20K48", "TL400", "FieldLogger"]:
            if m.lower() in pregunta.lower():
                modelo_detectado = m
                break

        # Consultar Supabase directamente por relevancia
        query_db = supabase.table("novus_documents").select("content, device_name")
        if modelo_detectado:
            query_db = query_db.ilike("device_name", f"%{modelo_detectado}%")
        
        res_db = query_db.limit(4).execute()
        resultados = res_db.data or []
        contexto = "\n\n---\n\n".join([item["content"] for item in resultados if "content" in item]) if resultados else "Novus standard technical manual."

        # 2. System prompt directo
        system_prompt = f"""
You are a Senior Technical Support Engineer at Novus Automation.
Answer directly and concisely in English using the technical context below.

Rules:
- Specify exact terminal numbers (e.g., **Terminals 1, 2, and 3**) and parameter codes.
- Use clear Markdown bullet points.
- Keep the total response under 100 words.

--- CONTEXT ---
{contexto}
---------------
"""

        respuesta_texto = generate_openai_response(system_prompt, pregunta).strip()

        # 3. Emparejamiento preciso de diagramas
        diagram_btn = None

        # Identificar intención de diagrama
        diag_type = None
        if any(k in pregunta.lower() for k in ["wire", "wiring", "connect", "connection", "terminal", "pt100", "sensor"]):
            diag_type = "wiring"
        elif any(k in pregunta.lower() for k in ["dimension", "cutout", "mount", "size", "panel"]):
            diag_type = "dimensions"
        elif any(k in pregunta.lower() for k in ["menu", "cycle", "navigation", "program"]):
            diag_type = "navigation"

        if diag_type:
            # Detectar el equipo mencionado
            modelos = ["N1040", "N1030", "N1050", "N20K48", "TL400", "FieldLogger", "DigiRail"]
            modelo_detectado = next((m for m in modelos if m.lower() in pregunta.lower()), "N1040")

            # Consulta con doble filtro estricto: Tipo de diagrama + Modelo de equipo
            res_diag = supabase.table("product_diagrams")\
                .select("image_url, button_label")\
                .eq("diagram_type", diag_type)\
                .ilike("product_name", f"%{modelo_detectado}%")\
                .limit(1)\
                .execute()

            # Si no encuentra por product_name, busca por coincidencia en image_url
            if not res_diag.data:
                res_diag = supabase.table("product_diagrams")\
                    .select("image_url, button_label")\
                    .ilike("image_url", f"%{modelo_detectado.lower()}%")\
                    .ilike("image_url", f"%{diag_type}%")\
                    .limit(1)\
                    .execute()

            if res_diag.data:
                img_data = res_diag.data[0]
                label = img_data.get("button_label") or ("🖼️ View Wiring Diagram" if diag_type == "wiring" else "📐 View Dimensions" if diag_type == "dimensions" else "⚙️ View Menu Navigation")
                diagram_btn = {
                    "type": "button",
                    "icon": {"type": "image", "color": "#FF9800"},
                    "text": label,
                    "link": img_data.get("image_url"),
                    "event": {"name": ""}
                }
        # 4. Respuesta Dialogflow
        if diagram_btn:
            response_payload = {
                "fulfillmentText": respuesta_texto,
                "fulfillmentMessages": [
                    {"text": {"text": [respuesta_texto]}},
                    {
                        "payload": {
                            "richContent": [[diagram_btn]]
                        }
                    }
                ]
            }
        else:
            response_payload = {"fulfillmentText": respuesta_texto}

        return jsonify(response_payload)

    except Exception as e:
        return jsonify({"fulfillmentText": f"Technical support error: {str(e)}"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
