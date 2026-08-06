import os
import requests
from flask import Flask, jsonify, request
from supabase import Client, create_client

app = Flask(__name__)

# Credenciales Supabase RAG
SUPABASE_URL = "https://cvulaqxjpyemryrccyxb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN2dWxhcXhqcHllbXJ5cmNjeXhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3NjgyNzcsImV4cCI6MjEwMTM0NDI3N30.bZ6bFoJETc1GAJqh4RTqT2dFcjE9ZaBQgkE8AXZchh4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Hugging Face Feature Extraction API (Gratuita para embeddings)
HF_API_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"


def get_embedding(text):
  """Genera el embedding usando la API de HuggingFace sin consumir RAM local."""
  response = requests.post(HF_API_URL, json={"inputs": text, "options": {"wait_for_model": True}})
  if response.status_code == 200:
    return response.json()
  else:
    raise Exception(f"Error HuggingFace API: {response.status_code} - {response.text}")


@app.route("/", methods=["GET"])
def home():
  return "Servidor Webhook Novus RAG Activo en Render"


@app.route("/webhook", methods=["POST"])
def dialogflow_webhook():
  req = request.get_json(silent=True, force=True) or {}

  pregunta = req.get("queryResult", {}).get("queryText", "")
  if not pregunta:
    pregunta = req.get("text", "")

  if not pregunta:
    return jsonify({"fulfillmentText": "No recibí ninguna pregunta válida."})

  try:
    # 1. Generar vector vía API de Hugging Face
    query_vector = get_embedding(pregunta)

    # Si la respuesta es una lista anidada (ej: [[0.1, 0.2...]]), extraemos el primer elemento
    if isinstance(query_vector, list) and len(query_vector) > 0 and isinstance(query_vector[0], list):
      query_vector = query_vector[0]

    # 2. Buscar en Supabase mediante match_novus_documents
    res = supabase.rpc(
        "match_novus_documents",
        {
            "query_embedding": query_vector,
            "match_threshold": 0.2,
            "match_count": 2,
        },
    ).execute()

    resultados = res.data

    if not resultados:
      respuesta_texto = "Lo siento, no encontré información relevante en el manual del N1040."
    else:
      contexto = "\n\n---\n\n".join([item["content"] for item in resultados])
      respuesta_texto = f"Información técnica del manual N1040 recuperada:\n\n{contexto}"

  except Exception as e:
    respuesta_texto = f"Error al procesar la consulta RAG: {str(e)}"

  return jsonify({"fulfillmentText": respuesta_texto})


if __name__ == "__main__":
  # Escuchar en el puerto dinámico asignado por Render
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)