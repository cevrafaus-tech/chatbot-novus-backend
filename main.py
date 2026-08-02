from flask import Flask, request, jsonify

app = Flask(__name__)

# Novus Product Documentation Links
NOVUS_MANUALS = {
    "N20K48": "https://www.novusautomation.com/downloads/manual_N20K48_en.pdf",
    "FieldLogger": "https://www.novusautomation.com/downloads/manual_FieldLogger_en.pdf",
    "LogBox": "https://www.novusautomation.com/downloads/manual_LogBoxBLE_en.pdf",
    "Climate Air": "https://www.novusautomation.com/downloads/manual_RHT_Climate_en.pdf",
    "Telik": "https://www.novusautomation.com/downloads/manual_Telik_en.pdf",
    "N1040": "https://www.novusautomation.com/downloads/manual_N1040_en.pdf",
    "TL400": "https://www.novusautomation.com/downloads/manual_TL400_en.pdf"
}

# Technical Error Diagnostics Map
ERROR_CODES = {
    "ErR1": "Open or disconnected input sensor. Check wiring continuity at the input terminals.",
    "ErR2": "Value out of range (above upper limit). Verify input type configuration in NXperience or QuickTune.",
    "ErR3": "Value out of range (below lower limit). Check polarity for thermocouple or mV signals.",
    "FAIL": "Internal hardware failure detected. Try power cycling the device or contacting Novus support."
}

@app.route('/', methods=['GET'])
def index():
    return "Novus Automation Bot Backend is Live!"

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(force=True)
    
    # Extract intent name and parameters from Dialogflow request
    intent_name = req.get('queryResult', {}).get('intent', {}).get('displayName', '')
    parameters = req.get('queryResult', {}).get('parameters', {})
    
    # Standardized parameters in English
    device_model = parameters.get('Model_eq') or 'Novus device'
    error_code = parameters.get('Code_error')
    
    fulfillment_text = "Sorry, I could not process your technical request."

    # Intent: Handle Error Codes
    if intent_name == "Support.Error_Code":
        if error_code in ERROR_CODES:
            error_details = ERROR_CODES[error_code]
            fulfillment_text = f"Error code {error_code} on the {device_model} indicates: {error_details}"
        elif error_code:
            fulfillment_text = f"The error code {error_code} requires advanced diagnostics. Please connect your {device_model} to NXperience software."
        else:
            fulfillment_text = f"Please provide the error code displayed on your {device_model} screen."

    # Intent: Handle Wiring and Documentation Requests
    elif intent_name == "Support.Wiring":
        if device_model in NOVUS_MANUALS:
            fulfillment_text = f"You can access the official wiring diagram and manual for the {device_model} here: {NOVUS_MANUALS[device_model]}"
        else:
            fulfillment_text = "Which Novus device model do you need technical documentation for?"

    return jsonify({
        "fulfillmentText": fulfillment_text
    })

if __name__ == '__main__':
    app.run(port=5000)