import urllib.parse
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# Headers para simular una petición web de navegador y evitar bloqueos
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}


def search_novus_website(query_text: str) -> str:
  """Busca la consulta directamente en la web de Novus Automation y extrae los resultados clave."""
  try:
    # Formatear la URL de búsqueda oficial de Novus
    encoded_query = urllib.parse.quote(query_text)
    search_url = (
        f"https://www.novusautomation.com/en/search?q={encoded_query}"
    )

    response = requests.get(search_url, headers=HTTP_HEADERS, timeout=8)

    if response.status_code != 200:
      return (
          f"I tried searching Novus portal for '{query_text}', but the search"
          " service is temporarily unavailable."
      )

    soup = BeautifulSoup(response.text, "html.parser")

    # Extraer enlaces y títulos de los resultados de búsqueda en la web
    results = []
    # Buscar elementos comunes de resultados (links con títulos o descripciones)
    for a_tag in soup.find_all("a", href=True):
      href = a_tag["href"]
      text = a_tag.get_text(strip=True)

      # Filtrar enlaces relevantes (manuales, descargas, páginas de producto)
      if (
          any(
              kw in href.lower()
              for kw in ["download", "product", "manual", "page"]
          )
          and len(text) > 10
      ):
        full_url = (
            href
            if href.startswith("http")
            else f"https://www.novusautomation.com{href}"
        )
        if (text, full_url) not in results:
          results.append((text, full_url))
        if len(results) >= 3:  # Limitar a los 3 mejores resultados
          break

    if results:
      formatted_response = f"Here is what I found on the Novus portal for '{query_text}':\n\n"
      for title, url in results:
        formatted_response += f"• {title}\n  Link: {url}\n\n"
      return formatted_response.strip()
    else:
      # Si no hay resultados directos en el motor interno, ofrecer el buscador abierto de Novus
      return (
          f"I couldn't find an exact document matching '{query_text}' on"
          " Novus website. You can explore the full Novus Downloads Portal"
          f" here: https://www.novusautomation.com/downloads?q={encoded_query}"
      )

  except Exception as e:
    print(f"[ERROR BÚSQUEDA WEB] {str(e)}")
    return (
        f"You can search for technical documentation directly on the Novus"
        f" site: https://www.novusautomation.com/downloads?q={urllib.parse.quote(query_text)}"
    )


@app.route("/", methods=["GET"])
def index():
  return "Novus Live Web-Search Bot Server is Active!"


@app.route("/webhook", methods=["POST", "GET"])
def webhook():
  if request.method == "GET":
    return "Webhook active! Send a POST request from Dialogflow."

  try:
    req = request.get_json(force=True) or {}
    query_result = req.get("queryResult", {})

    # Obtener el texto exacto que escribió el usuario o los parámetros
    user_query = query_result.get("queryText", "")
    parameters = query_result.get("parameters", {})

    raw_device = (
        parameters.get("Model_eq")
        or parameters.get("model_eq")
        or parameters.get("modelo_equipo")
        or ""
    )

    # Armar la palabra clave de búsqueda inteligente
    search_keyword = (
        f"{raw_device} {user_query}".strip() if raw_device else user_query
    )

    print(f"[LOG] Consultando Novus Web dinámicamente con: '{search_keyword}'")

    # Ejecutar búsqueda en tiempo real en la web de Novus
    fulfillment_text = search_novus_website(search_keyword)

  except Exception as e:
    print(f"[ERROR CRÍTICO] {str(e)}")
    fulfillment_text = (
        "An error occurred while connecting to the Novus web resource."
    )

  return jsonify({"fulfillmentText": fulfillment_text})


if __name__ == "__main__":
  app.run(port=5000)