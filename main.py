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


def expand_user_query(raw_query):
    """
    Expande la consulta del usuario con sinónimos técnicos, parámetros y terminología
    estándar de manuales de Novus antes de generar el embedding para la búsqueda.
    """
    if not OPENAI_API_KEY:
        return raw_query

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    expansion_system_prompt = (
        "You are an industrial automation search optimizer for Novus Automation manuals. "
        "Expand the following user query by adding relevant technical keywords, parameter names "
        "(e.g., inP, OUT, ALM, SP, baud rate), standard synonyms (e.g., zero adjustment, 4-20mA calibration, "
        "wiring terminals), and related device terms. "
        "Output ONLY a single concise, keyword-rich sentence in English to be used for semantic vector retrieval."
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
            # Combinamos la pregunta original con la versión enriquecida
            return f"{raw_query} {expanded_text}"
        else:
            return raw_query
    except Exception:
        # Si la llamada de expansión falla por timeout o red, continuamos con la consulta original
        return raw_query


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
        # =========================================================================
        # 1. EXPANSIÓN INTELIGENTE DE LA PREGUNTA (Query Expansion)
        # =========================================================================
        pregunta_expandida = expand_user_query(pregunta)

        # =========================================================================
        # 2. BÚSQUEDA SEMÁNTICA VECTORIAL EN SUPABASE (Retrieval)
        # =========================================================================
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

        # =====================================================================
        # INSTRUCCIÓN DE DEPURACIÓN / LOGS
        # =====================================================================
        print(f"--- Retrieved {len(resultados)} chunks for query: '{pregunta}' ---")
        for idx, r in enumerate(resultados):
            print(f"[{idx+1}] Device: {r.get('device_name', 'N/A')} | Preview: {r.get('content', '')[:120]}...")
        
        if not resultados:
            respuesta_texto = (
                "I'm sorry, I couldn't find any relevant technical information "
                "regarding that inquiry in the Novus knowledge base."
            )
        else:
            contexto = "\n\n---\n\n".join([item["content"] for item in resultados if "content" in item])

            # =====================================================================
            # 3. GENERACIÓN DE LA RESPUESTA FINAL (Synthesis)
            # =====================================================================
            system_prompt = f"""
            You are an expert Technical Support Engineer at Novus Automation.
            Your task is to answer the user's inquiry accurately using the technical context provided below.

            Strict Instructions:
            1. Language: Answer in clear, professional English.
            2. Tone: Helpful, direct, and precise.
            3. Accuracy: Explain all available connection principles, cable compensation guidelines, terminal assignments, and parameter configurations present in the context.
            4. Formatting: Use Markdown bolding and bullet points for clarity.
            5. Synthesis: If partial technical details are present (e.g., wire resistance compensation, wiring rules), provide those details clearly and mention the relevant manual section.

            --- RETRIEVED MANUAL CONTEXT ---
            {contexto}
            --------------------------------
            """

            # Observación: A la IA generativa final le pasamos la 'pregunta' original del usuario
            # para que responda exactamente a lo que este consultó, no a la lista de palabras clave.
            respuesta_texto = generate_openai_response(system_prompt, pregunta).strip()

    except Exception as e:
        respuesta_texto = f"Error processing query: {str(e)}"

    return jsonify({"fulfillmentText": respuesta_texto})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
