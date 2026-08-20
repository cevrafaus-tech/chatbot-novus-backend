import os
import requests
from flask import Flask, jsonify, request
from supabase import Client, create_client
from fastembed import TextEmbedding

app = Flask(__name__)

# 1. Supabase Credentials
SUPABASE_URL = "https://cvulaqxjpyemryrccyxb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN2dWxhcXhqcHllbXJ5cmNjeXhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3NjgyNzcsImV4cCI6MjEwMTM0NDI3N30.bZ6bFoJETc1GAJqh4RTqT2dFcjE9ZaBQgkE8AXZchh4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

print("⏳ Loading local embedding model...")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def expand_user_query(raw_query):
    if not OPENAI_API_KEY:
        return raw_query

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    expansion_system_prompt = (
        "You are an industrial automation search optimizer for Novus Automation manuals. "
        "Expand the following query with technical keywords, parameter codes (e.g., inP, OUT, ALM, SP), "
        "and physical connection terms (terminals, pinout, wiring diagram, wire resistance compensation, RTD). "
        "Output ONLY a single concise, keyword-rich sentence in English."
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": expansion_system_prompt},
            {"role": "user", "content": raw_query}
        ],
        "temperature": 0.0,
        "max_tokens": 100
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            expanded_text = data['choices'][0]['message']['content'].strip()
            return f"{raw_query} {expanded_text}"
        return raw_query
    except Exception:
        return raw_query


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
        "temperature": 0.2,
        "max_tokens": 800
    }
    response = requests.post(url, headers=headers, json=payload, timeout=15)
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
        # 1. Expansión y recuperación
        pregunta_expandida = expand_user_query(pregunta)
        embeddings = list(embedding_model.embed([pregunta_expandida]))
        query_vector = embeddings[0].tolist()

        res = supabase.rpc(
            "match_novus_documents",
            {
                "query_embedding": query_vector,
                "match_threshold": 0.0,
                "match_count": 10
            }
        ).execute()

        resultados = res.data or []

        if not resultados:
            return jsonify({"fulfillmentText": "I could not find relevant information in the Novus knowledge base."})

        contexto = "\n\n---\n\n".join([item["content"] for item in resultados if "content" in item])

        # 2. System prompt enriquecido
        system_prompt = f"""
You are a Senior Technical Support Engineer at Novus Automation.
Your goal is to provide clear, actionable, and rigorously accurate technical guidance based on the retrieved manual context below.

### RESPONSE GUIDELINES & FORMATTING:
1. **Direct Opening:** Start immediately with the direct technical answer or step-by-step procedure. Drastically minimize conversational filler or introductory setup phrases.
2. **Structural Clarity:**
   - Use **Markdown Bold** for parameter codes (e.g., **inP**, **SP**, **OUT1**, **ALM1**), menu cycles, navigation keys, and terminal identifiers.
   - Use concise **bullet points** or numbered steps for sequences, configuration cycles, and wiring instructions.
   - Use short markdown comparison tables whenever summarizing multi-value configurations, ranges, or error codes.
3. **Hardware & Terminal Connections:**
   - When explaining wiring, state all available pinout assignments, sensor configurations (e.g., 2-wire vs. 3-wire RTD compensation, polarity for thermocouples/transmitters), and power supply ratings present in the context.
   - If interactive visual diagrams or buttons are provided, reference them clearly to guide the user.
4. **Technical Synthesis & Grounding:**
   - Synthesize all relevant parameters, factory defaults, and operating rules directly from the retrieved context.
   - If the retrieved context contains partial technical data (e.g., configuration guidelines without a specific accessory model), clearly explain the available principles and suggest the exact manual section to consult.
   - Only declare information unavailable if the retrieved context contains zero relevant technical details for the subject.

--- RETRIEVED MANUAL CONTEXT ---
{contexto}
--------------------------------
"""

        respuesta_texto = generate_openai_response(system_prompt, pregunta).strip()

        # 3. Buscar si existe diagrama relevante en product_diagrams
        # 3. Buscar el diagrama exacto correspondiente al equipo y al tipo de consulta
        diagram_btn = None
        
        # Detectar el tipo de diagrama solicitado
        diag_type = None
        if any(k in pregunta.lower() for k in ["wire", "wiring", "connect", "terminal", "pt100", "sensor"]):
            diag_type = "wiring"
        elif any(k in pregunta.lower() for k in ["dimension", "cutout", "mount", "size"]):
            diag_type = "dimensions"
        elif any(k in pregunta.lower() for k in ["menu", "cycle", "navigation", "program"]):
            diag_type = "navigation"

        if diag_type:
            # Detectar el modelo mencionado en la consulta (ej. N1040, N1030, TL400)
            query_builder = supabase.table("product_diagrams").select("image_url, button_label, product_name").eq("diagram_type", diag_type)
            
            # Buscar menciones de modelos comunes
            modelos = ["N1040", "N1030", "N1050", "N20K48", "TL400", "FieldLogger", "DigiRail"]
            modelo_detectado = next((m for m in modelos if m.lower() in pregunta.lower()), None)
            
            if modelo_detectado:
                query_builder = query_builder.ilike("product_name", f"%{modelo_detectado}%")

            res_diag = query_builder.limit(1).execute()

            if res_diag.data:
                img_data = res_diag.data[0]
                diagram_btn = {
                    "type": "button",
                    "icon": {"type": "image", "color": "#FF9800"},
                    "text": img_data.get("button_label", "🖼️ View Technical Diagram"),
                    "link": img_data.get("image_url"),
                    "event": {"name": ""}
                }

        # 4. Construir respuesta final para Dialogflow
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
        return jsonify({"fulfillmentText": f"Error processing query: {str(e)}"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
