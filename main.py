import os
import re
from flask import Flask, jsonify, request
from supabase import Client, create_client
from fastembed import TextEmbedding

app = Flask(__name__)

# Credenciales Supabase RAG
SUPABASE_URL = "https://cvulaqxjpyemryrccyxb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN2dWxhcXhqcHllbXJ5cmNjeXhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3NjgyNzcsImV4cCI6MjEwMTM0NDI3N30.bZ6bFoJETc1GAJqh4RTqT2dFcjE9ZaBQgkE8AXZchh4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Modelo de embeddings local
print("⏳ Cargando modelo de embeddings local...")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def limpiar_y_formatear_texto(resultados):
    """Limpia caracteres innecesarios y formatea el contexto de Supabase de manera profesional."""
    textos_limpios = []
    for item in resultados:
        txt = item.get("content", "")
        # Eliminar guiones repetidos y saltos excesivos
        txt = re.sub(r"\.{4,}", "", txt)
        txt = re.sub(r"\n+", "\n", txt).strip()
        textos_limpios.append(txt)

    contexto = "\n\n• ".join(textos_limpios)
    return (
        "🤖 **Soporte Técnico Novus Automation**\n\n"
        "Basado en el manual oficial del controlador **N1040**, aquí tienes la información correspondiente:\n\n"
        f"• {contexto}\n\n"
        "--- \n"
        "¿Necesitas ayuda con algún otro parámetro o configuración?"
    )


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
        # 1. Búsqueda Vectorial en Supabase
        embeddings = list(embedding_model.embed([pregunta]))
        query_vector = embeddings[0].tolist()

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
            respuesta_texto = "Lo siento, no encontré información técnica relevante sobre esa consulta en el manual del N1040."
        else:
            respuesta_texto = limpiar_y_formatear_texto(resultados)

    except Exception as e:
        respuesta_texto = f"Error al procesar la consulta RAG: {str(e)}"

    return jsonify({"fulfillmentText": respuesta_texto})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)