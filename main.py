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

# 2. Anthropic API Key (Sanitized)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")

# 3. Initialize Local Embedding Model
print("⏳ Loading local embedding model...")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def generate_anthropic_synthesis(system_prompt, user_query):
    """
    Sends the manual context to Anthropic (Claude) using the 
    standard 'claude-3-5-haiku-latest' model alias.
    """
    url = "https://api.anthropic.com/v1/messages"
    
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    # Primary model attempt: claude-3-5-haiku-latest
    payload = {
        "model": "claude-3-5-haiku-latest",
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
    
    # Fallback to claude-3-5-sonnet-latest if 404 occurs on haiku
    if response.status_code == 404:
        payload["model"] = "claude-3-5-sonnet-latest"
        response = requests.post(url, headers=headers, json=payload, timeout=15)

    if response.status_code == 200:
        data = response.json()
        return data['content'][0]['text']
    else:
        raise Exception(f"Anthropic API Error (Status {response.status_code}): {response.text}")


@app.route("/", methods=["GET"])
def home():
    return "Novus RAG + Anthropic Claude Webhook Active on Render v2"


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
                "match_count": 3
            }
        ).execute()

        resultados = res.data

        if not resultados:
            respuesta_texto = (
                "I'm sorry, I couldn't find any relevant technical information "
                "regarding that inquiry in the N1040 knowledge base."
            )
        else:
            contexto = "\n\n---\n\n".join([item["content"] for item in resultados])

            # B. System Prompt instructing Claude to synthesize the raw text
            system_prompt = f"""
            You are an expert Technical Support Engineer at Novus Automation.
            Your task is to answer the user's question by synthesizing ONLY the following technical information retrieved from the official N1040 manual.

            Strict instructions:
            1. Language: Answer in clear, professional English.
            2. Tone: Professional, direct, concise, and helpful.
            3. Quality: Rephrase raw text into well-formatted Markdown bullet points or tables. Do NOT copy raw page numbers, broken words, or header fragments.
            4. Precision: Always include exact parameter names, error codes (e.g., nnnn, vvvv, Err1), or values mentioned in the text.
            5. If the provided context is insufficient to answer the question, politely state that the information is not present in the manual.

            --- OFFICIAL MANUAL CONTEXT ---
            {contexto}
            -------------------------------
            """

            respuesta_texto = generate_anthropic_synthesis(system_prompt, pregunta).strip()

    except Exception as e:
        respuesta_texto = f"Error processing query with Claude: {str(e)}"

    return jsonify({"fulfillmentText": respuesta_texto})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)