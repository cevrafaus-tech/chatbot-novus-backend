import os
import re
from flask import Flask, jsonify, request
from supabase import Client, create_client
from fastembed import TextEmbedding

app = Flask(__name__)

# 1. Supabase Credentials
SUPABASE_URL = "https://cvulaqxjpyemryrccyxb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN2dWxhcXhqcHllbXJ5cmNjeXhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3NjgyNzcsImV4cCI6MjEwMTM0NDI3N30.bZ6bFoJETc1GAJqh4RTqT2dFcjE9ZaBQgkE8AXZchh4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Initialize Local Embedding Model
print("⏳ Loading local embedding model...")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def format_technical_response(results, query):
    """
    Cleans raw PDF text chunks from Supabase and builds a clean, 
    professional technical answer in English.
    """
    clean_chunks = []
    for item in results:
        content = item.get("content", "")
        # Remove PDF dot leaders, page numbers, and excess line breaks
        content = re.sub(r"\.{4,}", "", content)
        content = re.sub(r"\n+", "\n", content).strip()
        clean_chunks.append(content)

    formatted_context = "\n\n• ".join(clean_chunks)

    return (
        "🤖 **Novus Automation Technical Support**\n\n"
        "Based on the official **N1040 Controller Manual**, here is the relevant technical information:\n\n"
        f"• {formatted_context}\n\n"
        "--- \n"
        "Do you need further assistance with parameter configurations, wiring diagrams, or error codes?"
    )


@app.route("/", methods=["GET"])
def home():
    return "Novus RAG Webhook Server Active on Render"


@app.route("/webhook", methods=["POST"])
def dialogflow_webhook():
    req = request.get_json(silent=True, force=True) or {}

    pregunta = req.get("queryResult", {}).get("queryText", "")
    if not pregunta:
        pregunta = req.get("text", "")

    if not pregunta:
        return jsonify({"fulfillmentText": "No valid query was received."})

    try:
        # A. Vector Search in Supabase (Retrieval)
        embeddings = list(embedding_model.embed([pregunta]))
        query_vector = embeddings[0].tolist()

        res = supabase.rpc(
            "match_novus_documents",
            {
                "query_embedding": query_vector,
                "match_threshold": 0.2,
                "match_count": 2
            }
        ).execute()

        resultados = res.data

        if not resultados:
            respuesta_texto = (
                "I'm sorry, I couldn't find any relevant technical information "
                "regarding that inquiry in the N1040 knowledge base."
            )
        else:
            # B. Format technical synthesis directly
            respuesta_texto = format_technical_response(resultados, pregunta)

    except Exception as e:
        respuesta_texto = f"Error processing query: {str(e)}"

    return jsonify({"fulfillmentText": respuesta_texto})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)