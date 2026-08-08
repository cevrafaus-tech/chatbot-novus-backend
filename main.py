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

# 2. Anthropic API Key (Fetched from Render Environment Variables)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

# 3. Initialize Local Embedding Model
print("⏳ Loading local embedding model...")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def generate_anthropic_response(system_prompt, user_query):
    """
    Calls the Anthropic Messages API using claude-3-5-sonnet-20241022 for fast,
    reliable, and accurate technical synthesis.
    """
    url = "https://api.anthropic.com/v1/messages"
    
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": user_query
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    
    if response.status_code == 200:
        data = response.json()
        return data['content'][0]['text']
    else:
        raise Exception(f"Anthropic API Error ({response.status_code}): {response.text}")


@app.route("/", methods=["GET"])
def home():
    return "Novus RAG + Anthropic Claude Webhook Server Active on Render"


@app.route("/webhook", methods=["POST"])
def dialogflow_webhook():
    req = request.get_json(silent=True, force=True) or {}

    pregunta = req.get("queryResult", {}).get("queryText", "")
    if not pregunta:
        pregunta = req.get("text", "")

    if not pregunta:
        return jsonify({"fulfillmentText": "No valid query was received."})

    try:
        # A. Search Supabase (Retrieval)
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
            respuesta_texto = "I'm sorry, I couldn't find any relevant technical information regarding that inquiry in the N1040 knowledge base."
        else:
            contexto = "\n\n---\n\n".join([item["content"] for item in resultados])

            # B. System Prompt for Claude
            system_prompt = f"""
            You are an expert Technical Support Engineer at Novus Automation.
            Your task is to answer the user's question using ONLY the following technical information extracted from the official manuals.

            Strict instructions:
            1. Language: Answer in clear, professional English. If the user asks in another language, adapt professionally.
            2. Tone: Professional, direct, and helpful.
            3. Precision: Use exact parameter names, error codes, or manual diagrams when applicable.
            4. If the provided context is insufficient to answer with certainty, politely state that the information is not available in the manual.

            --- TECHNICAL MANUAL INFORMATION ---
            {contexto}
            ------------------------------------
            """

            respuesta_texto = generate_anthropic_response(system_prompt, pregunta).strip()

    except Exception as e:
        respuesta_texto = f"Error processing query: {str(e)}"

    return jsonify({"fulfillmentText": respuesta_texto})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)