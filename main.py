from flask import Flask, request, jsonify

app = Flask(__name__)

# Base de datos simplificada de recursos y errores Novus
MANUALES_NOVUS = {
    "N20K48": "https://www.novusautomation.com/downloads/manual_N20K48_es.pdf",
    "FieldLogger": "https://www.novusautomation.com/downloads/manual_FieldLogger_es.pdf",
    "LogBox": "https://www.novusautomation.com/downloads/manual_LogBoxBLE_es.pdf",
    "Climate Air": "https://www.novusautomation.com/downloads/manual_RHT_Climate_es.pdf",
    "Telik": "https://www.novusautomation.com/downloads/manual_Telik_es.pdf",
    "N1040": "https://www.novusautomation.com/downloads/manual_N1040_es.pdf",
    "TL400": "https://www.novusautomation.com/downloads/manual_TL400_es.pdf"
}

CODIGOS_ERROR = {
    "ErR1": "Sensor abierto o desconectado. Verifica la continuidad del sensor en los terminales de entrada.",
    "ErR2": "Valor fuera de escala (por encima del límite). Revisa la configuración de tipo de entrada en NXperience.",
    "ErR3": "Valor fuera de escala (por debajo del límite). Revisa la polaridad del termopar o señal mV."
}

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(force=True)
    
    intent_name = req.get('queryResult', {}).get('intent', {}).get('displayName')
    parameters = req.get('queryResult', {}).get('parameters', {})
    
    equipo = parameters.get('modelo_equipo')
    error = parameters.get('codigo_error')
    
    respuesta_texto = "Lo siento, no pude procesar tu consulta técnica."

    # Intent: Consulta de manuales / cableado
    if intent_name == "Soporte.Cableado":
        if equipo in MANUALES_NOVUS:
            respuesta_texto = (
                f"Puedes consultar el diagrama de cableado y manual técnico del **{equipo}** "
                f"en el siguiente enlace: {MANUALES_NOVUS[equipo]}"
            )
        else:
            respuesta_texto = "¿Para qué modelo de Novus necesitas el esquema de cableado?"

    # Intent: Manejo de Códigos de Error
    elif intent_name == "Soporte.Codigo_Error":
        if error in CODIGOS_ERROR:
            detalle = CODIGOS_ERROR[error]
            respuesta_texto = f"El código **{error}** en el equipo **{equipo or 'Novus'}** significa: {detalle}"
        else:
            respuesta_texto = f"El error **{error}** requiere revisión detallada. Te recomendamos conectarlo a NXperience para un diagnóstico."

    return jsonify({
        "fulfillmentText": respuesta_texto
    })

if __name__ == '__main__':
    app.run(port=5000, debug=True)