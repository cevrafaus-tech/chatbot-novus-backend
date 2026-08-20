import os
import requests
from flask import Flask, jsonify, request
from supabase import Client, create_client
from fastembed import TextEmbedding

app = Flask(__name__)

SUPABASE_URL = "https://cvulaqxjpyemryrccyxb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN2dWxhcXhqcHllbXJ5cmNjeXhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3NjgyNzcsImV4cCI6MjEwMTM0NDI3N30.bZ6bFoJETc1GAJqh4RTqT2dFcjE9ZaBQgkE8AXZchh4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

print("⏳ Loading and warming up local embedding model...")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
# Calentamiento inicial en memoria para eliminar latencia en la primera consulta
_ = list(embedding_model.embed(["warmup"]))


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
        "max_tokens": 250  # Generación ultrarrápida (< 1.2 segundos)
    }
    response = requests.post(url, headers=headers, json=payload, timeout=3.5)
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
        # 1. Embedding inmediato
        embeddings = list(embedding_model.embed([pregunta]))
        query_vector = embeddings[0].tolist()

        # 2. Recuperación rápida (top 4 fragmentos)
        res = supabase.rpc(
            "match_novus_documents",
            {
                "query_embedding": query_vector,
                "match_threshold": 0.0,
                "match_count": 4
            }
        ).execute()

        resultados = res.data or []
        contexto = "\n\n---\n\n".join([item["content"] for item in resultados if "content" in item]) if resultados else "No specific manual context found."

        # 3. Prompt conciso
        system_prompt = f"""
You are a Technical Support Engineer at Novus Automation.
Provide a direct, step-by-step technical answer in English using the context below.

Rules:
- State exact terminal connections (e.g., **Terminals 1, 2, and 3**) and parameter codes (e.g., **inP**, **OUT1**).
- Keep the response direct and under 150 words.

--- RETRIEVED CONTEXT ---
{contexto}
-------------------------
"""

        respuesta_texto = generate_openai_response(system_prompt, pregunta).strip()

        # 4. Diagrama asociado a la consulta
        diagram_btn = None
        if any(k in pregunta.lower() for k in ["wire", "wiring", "connect", "terminal", "pt100", "sensor"]):
            res_diag = supabase.table("product_diagrams")\
                .select("image_url, button_label")\
                .ilike("product_name", "%N1040%")\
                .limit(1)\
                .execute()

            if res_diag.data:
                img_data = res_diag.data[0]
                diagram_btn = {
                    "type": "button",
                    "icon": {"type": "image", "color": "#FF9800"},
                    "text": img_data.get("button_label", "🖼️ View Wiring Diagram"),
                    "link": img_data.get("image_url"),
                    "event": {"name": ""}
                }

        # 5. Payload de respuesta compatible con Dialogflow
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