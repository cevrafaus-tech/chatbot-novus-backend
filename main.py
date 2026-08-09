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

# 2. OpenAI API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

# 3. Initialize Embedding Model
print("⏳ Loading local embedding model...")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def generate_openai_response(system_prompt, user_query):
    """
    Calls OpenAI GPT-4o-mini to synthesize retrieved manual context.
    """
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
        data = response.json()
        return data['choices'][0]['message']['content']
    else:
        raise Exception(f"OpenAI API Error ({response.status_code}): {response.text}")


@app.route("/", methods=["GET"])
def home():
    return "Universal Novus RAG Webhook Active on Render"


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

        # Aumentamos match_count a 8 para capturar tablas completas y contexto circundante
        res = supabase.rpc(
            "match_novus_documents",
            {
                "query_embedding": query_vector,
                "match_threshold": 0.05,
                "match_count": 8
            }
        ).execute()

        resultados = res.data or []

        if not resultados:
            respuesta_texto = (
                "I'm sorry, I couldn't find any relevant technical information "
                "regarding that inquiry in the Novus knowledge base."
            )
        else:
            contexto = "\n\n---\n\n".join([item["content"] for item in resultados if "content" in item])

            # B. System Prompt completamente genérico y agnóstico
            system_prompt = f"""
            You are an expert Technical Support Engineer at Novus Automation.
            Your task is to answer the user's inquiry accurately based ONLY on the technical context provided below.

            Strict Instructions:
            1. Language: Answer in clear, professional English.
            2. Tone: Helpful, direct, and precise.
            3. Accuracy: Detail parameter codes (e.g., inP, SP, Out), menu cycles, and exact value options when available in the context.
            4. Formatting: Use Markdown bolding and bullet points for navigation paths and lists.
            5. Fallback: If the provided manual sections do not contain enough information to answer with certainty, state politely that the specific detail is not covered in the retrieved manual sections.

            --- RETRIEVED MANUAL CONTEXT ---
            {contexto}
            --------------------------------
            """

            respuesta_texto = generate_openai_response(system_prompt, pregunta).strip()

    except Exception as e:
        respuesta_texto = f"Error processing query: {str(e)}"

    return jsonify({"fulfillmentText": respuesta_texto})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)