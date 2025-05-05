#!/usr/bin/env python3

from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from llm import AIAssistant
import json

app = Flask(__name__, template_folder='webpage/templates', static_folder='webpage/static')
CORS(app)  # Enable CORS if needed

# Loading test data
with open("./test_data/analyzed_example_portfolio.json", 'r') as file:
        portfolio = json.load(file)

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

    stocks_list = list(portfolio.values())

    portfolio_informations = {
        'overallUrgency': sum(item['urgency'] for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'overallBuy': sum(item['buy'] for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'overallSell': sum(item['sell'] for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'overallHold': sum(item['hold'] for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'marketSummary': 'Dummy Market Summary',
        'currentOpportunities': 'Sample Opportunities',
        'currentRisks': 'Potential Risks',
        'other': 'Additional Information',
        'languageAssessment': 'Language Analysis'
    }

    return jsonify(portfolio_informations)

@app.route('/api/stocks')
def get_stocks():

    stocks_list = list(portfolio.values())

    stocks_list.sort(key=lambda x: x['urgency'], reverse=True)

    return jsonify(stocks_list)

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
    app.run(debug=True) # for development only
    # app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
