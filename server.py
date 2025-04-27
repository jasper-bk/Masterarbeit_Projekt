#!/usr/bin/env python3

from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from llm import AIAssistant
import json

app = Flask(__name__, template_folder='webpage/templates', static_folder='webpage/static')
CORS(app)  # Enable CORS if needed

###########
# Webpage #
###########

@app.route('/')
def index():
    return render_template('index.html')

# Serve static files (CSS/JS)
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


###############
# Webpage API #
###############

@app.route('/api/portfolio')
def get_portfolio():
    return jsonify({
        'overallUrgency': 34,
        'overallBuy': 70,
        'overallSell': 20,
        'overallHold': 10,
        'marketSummary': 'Dummy Market Summary',
        'currentOpportunities': 'Sample Opportunities',
        'currentRisks': 'Potential Risks',
        'other': 'Additional Information',
        'languageAssessment': 'Language Analysis'
    })

@app.route('/api/stocks')
def get_stocks():

    with open("./test_data/analyzed_example_portfolio.json", 'r') as file:
        test_portfolio = json.load(file)

    return jsonify(list(test_portfolio.values()))

###########
# LLM API #
###########

@app.route('/simple-llm-request', methods=['POST'])
def analyze_portfolio():
    """API endpoint for simple llm request"""
    data = request.json

    assistant = AIAssistant(
        provider=data.get('provider', 'ollama'),
        model=data.get('model', 'deepseek-r1:14b'),
        langchain=data.get('langchain', False)
    )

    try:
        response = assistant.generate_response(data['prompt'])

        return jsonify({
            "response": recommendation,
            "model": assistant.model
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def main():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
