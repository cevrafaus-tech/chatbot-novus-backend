import os
import requests
from flask import Flask, jsonify, request
from supabase import Client, create_client
from fastembed import TextEmbedding

app = Flask(__name__)

# 1. Credenciales Supabase
SUPABASE_URL = "https://cvulaqxjpyemryrccyxb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN2dWxhcXhqcHllbXJ5cmNjeXhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3NjgyNzcsImV4cCI6MjEwMTM0NDI3N30.bZ6bFoJETc1GAJqh4RTqT2dFcjE9ZaBQgkE8AXZchh4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Configuración Gemini API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# 3. Inicializar modelo de embeddings local (fastembed)
print("⏳ Cargando modelo de embeddings local...")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def generar_respuesta_gemini(prompt):
    """Llama directamente a la API REST de Gemini para evitar conflictos de autenticación con el SDK."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    
    if response.status_code == 200:
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text']
    else:
        raise Exception(f"API Gemini Error ({response.status_code}): {response.text}")


@app.route("/", methods=["GET"])
def home():
    return "Servidor Webhook Novus RAG + Gemini Flash Activo en Render"


@app.route("/webhook", methods=["POST"])
def dialogflow_webhook():
    req = request.get_json(silent=True, force=True) or {}

    pregunta = req.get("queryResult", {}).get("queryText", "")
    if not pregunta:
        pregunta = req.get("text", "")

    if not pregunta:
        return jsonify({"fulfillmentText": "No recibí ninguna pregunta válida."})

    try:
        # A. Buscar en Supabase (Retrieval)
        embeddings = list(embedding_model.embed([pregunta]))
        query_vector = embeddings[0].tolist()

        res = supabase.rpc(
            "match_novus_documents",
            {
                "query_embedding": query_vector,
                "match_threshold": 0.2,
                "match_count": 3
            }
        ).execute()

        resultados = res.data

        if not resultados:
            respuesta_texto = "Lo siento, no encontré información técnica relevante sobre esa consulta en la base de conocimientos."
        else:
            contexto = "\n\n---\n\n".join([item["content"] for item in resultados])

            # B. Generar respuesta con Gemini Flash (Synthesis/Generation)
            system_prompt = f"""
            Eres un Ingeniero de Soporte Técnico experto de Novus Automation.
            Tu tarea es responder a la pregunta del usuario utilizando ÚNICAMENTE la siguiente información extraída de los manuales técnicos oficiales.

            Instrucciones estrictas:
            1. Idioma: Si el usuario pregunta en español, responde en un español técnico profesional y claro. Si pregunta en inglés, responde en inglés.
            2. Tono: Profesional, directo y servicial.
            3. Precisión: Utiliza los nombres exactos de los parámetros, códigos de error o esquemas del manual cuando aplique.
            4. Si la información no es suficiente para responder con certeza, indícalo cortésmente.

            --- INFORMACIÓN TÉCNICA DEL MANUAL ---
            {contexto}
            --------------------------------------

            Pregunta del usuario: {pregunta}
            """

            respuesta_texto = generar_respuesta_gemini(system_prompt).strip()

    except Exception as e:
        respuesta_texto = f"Error al procesar la consulta: {str(e)}"

    return jsonify({"fulfillmentText": respuesta_texto})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)