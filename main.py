from flask import Flask, request, jsonify

app = Flask(__name__)

# Official Novus Manuals & Wiring Links
NOVUS_MANUALS = {
    "N20K48": "https://www.novusautomation.com/downloads/manual_N20K48_en.pdf",
    "FieldLogger": "https://www.novusautomation.com/downloads/manual_FieldLogger_en.pdf",
    "LogBox": "https://www.novusautomation.com/downloads/manual_LogBoxBLE_en.pdf",
    "Climate Air": "https://www.novusautomation.com/downloads/manual_RHT_Climate_en.pdf",
    "Telik": "https://www.novusautomation.com/downloads/manual_Telik_en.pdf",
    "N1040": "https://www.novusautomation.com/downloads/manual_N1040_en.pdf",
    "TL400": "https://www.novusautomation.com/downloads/manual_TL400_en.pdf"
}

# Technical Error Diagnostic Map
ERROR_CODES = {
    "ErR1": "Open or disconnected input sensor. Check wiring continuity at the input terminals.",
    "ErR2": "Value out of range (above upper limit). Verify input type configuration in NXperience or QuickTune.",
    "ErR3": "Value out of range (below lower limit). Check polarity for thermocouple or mV signals.",
    "FAIL": "Internal hardware failure detected. Try power cycling the device or contacting Novus support."
}

# Software & Connectivity Troubleshooting Guide
SOFTWARE_GUIDES = {
    "FieldLogger": "For FieldLogger via USB: Ensure Novus USB Drivers are installed. If using RS485/Modbus, verify Baud Rate (default 19200) and Modbus ID.",
    "LogBox": "For LogBox BLE: Enable Bluetooth and Location Services on your smartphone. Open QuickTune App and press the connect button on LogBox.",
    "Telik": "For Telik Peter Gateway: Check cellular SIM card status, APN configuration, and cloud server connection settings in NXperience.",
    "TL400": "For TL400 Ultrasonic Sensor: Ensure 12-24VDC power supply is active before connecting via USB-to-Serial converter to NXperience.",
    "N20K48": "For N20K48 Modular Controller: Connect via USB or Bluetooth using QuickTune. Verify module auto-detection in the main panel.",
    "N1040": "For N1040 Controller: Connect via USB interface with QuickTune/NXperience. Ensure power supply is connected to allow communication.",
    "Climate Air": "For Climate Air / RHT Climate: Verify transmitter power supply and 4-20mA / RS485 connection parameters in NXperience."
}

# Fast Programming Guides
PROGRAMMING_GUIDES = {
    "N1040": "To program the N1040: 1) Press the 'P' key for 2 seconds to enter the Configuration Level. 2) Use UP/DOWN arrows to set input type (TYPE), control action (ACT), and tuning mode (ATun). 3) Press 'P' to save each parameter. For quick setup, connect via USB and use QuickTune software.",
    "N20K48": "To program the N20K48: Connect via Bluetooth or micro-USB using the QuickTune App on your phone/PC. You can configure inputs, control outputs, and optional ClickOn modules intuitively from the main menu.",
    "FieldLogger": "To program FieldLogger: Use NXperience software on your PC. Create a new configuration file to set up active channels (analog/digital), sampling rate, and alarm thresholds, then download to the device via USB/Ethernet."
}

# Device Name Normalization Map
DEVICE_MAP = {
    "fieldlogger": "FieldLogger",
    "fl": "FieldLogger",
    "field logger": "FieldLogger",
    "n1040": "N1040",
    "n20k48": "N20K48",
    "n20k": "N20K48",
    "logbox": "LogBox",
    "logbox ble": "LogBox",
    "climate air": "Climate Air",
    "rht climate": "Climate Air",
    "telik": "Telik",
    "tl400": "TL400"
}


@app.route('/', methods=['GET'])
def index():
    return "Novus Bot Server is Live and Ready!"


@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'GET':
        return "Webhook endpoint is active! Send a POST request from Dialogflow."

    req = request.get_json(force=True)
    
    intent_name = req.get('queryResult', {}).get('intent', {}).get('displayName', '')
    parameters = req.get('queryResult', {}).get('parameters', {})
    
    # Flexible Parameter Extraction
    raw_device = (
        parameters.get('Model_eq') or 
        parameters.get('model_eq') or 
        parameters.get('modelo_equipo') or ''
    )
    
    error_code = (
        parameters.get('Code_error') or 
        parameters.get('code_error') or 
        parameters.get('codigo_error')
    )
    
    software_app = (
        parameters.get('Software_app') or 
        parameters.get('software_app') or 
        parameters.get('software_config') or 'NXperience'
    )
    
    device_model = DEVICE_MAP.get(str(raw_device).lower(), raw_device)
    
    fulfillment_text = "Sorry, I could not process your technical request."

    intent_lower = intent_name.lower().strip()

    # Intent 1: Error Codes
    if "error" in intent_lower:
        if error_code in ERROR_CODES:
            error_details = ERROR_CODES[error_code]
            device_str = f"the {device_model}" if device_model else "your Novus device"
            fulfillment_text = f"Error code {error_code} on {device_str} indicates: {error_details}"
        elif error_code:
            fulfillment_text = f"The error code {error_code} requires advanced diagnostics. Please connect your device to {software_app} software."
        else:
            fulfillment_text = "Please specify the error code displayed on your device screen (e.g., ErR1, ErR2, FAIL)."

    # Intent 2: Wiring / Manuals
    elif "wiring" in intent_lower or "manual" in intent_lower:
        if device_model in NOVUS_MANUALS:
            fulfillment_text = f"You can access the official wiring diagram and manual for the {device_model} here: {NOVUS_MANUALS[device_model]}"
        else:
            fulfillment_text = "Which Novus device model do you need technical documentation for? (e.g., N1040, FieldLogger, N20K48, TL400)"

    # Intent 3: Software / Connectivity
    elif "software" in intent_lower or "config" in intent_lower:
        if device_model in SOFTWARE_GUIDES:
            guide = SOFTWARE_GUIDES[device_model]
            fulfillment_text = f"Troubleshooting {device_model} with {software_app}: {guide}"
        elif device_model:
            fulfillment_text = f"To configure {device_model}, connect it via USB/Bluetooth and open {software_app}. Ensure drivers are updated."
        else:
            fulfillment_text = f"Please specify which Novus device you are trying to configure with {software_app}."

    # Intent 4: Programming / Setup Steps
    elif "program" in intent_lower or "setup" in intent_lower:
        if device_model in PROGRAMMING_GUIDES:
            fulfillment_text = PROGRAMMING_GUIDES[device_model]
        elif device_model:
            fulfillment_text = f"To program the {device_model}, hold the configuration key ('P' or 'PROG') for 2 seconds or connect via QuickTune/NXperience software."
        else:
            fulfillment_text = "Which Novus device would you like programming instructions for?"

    return jsonify({
        "fulfillmentText": fulfillment_text
    })


if __name__ == '__main__':
    app.run(port=5000)