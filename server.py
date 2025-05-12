#!/usr/bin/env python3

from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from llm import AIAssistant
from portfolio_ai import PortfolioAIAssistant
import json

app = Flask(__name__, template_folder='webpage/templates', static_folder='webpage/static')
CORS(app)  # Enable CORS if needed

# Loading test data
with open("./test_data/sample_new_portfolio_structure.json", 'r') as file:
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

    stocks_list = list(portfolio["assets"].values())

    # Idea: Just pass the whole portfolio JSON to the frontend and do all calculations, sorting there. JSON could be just reloaded

    # To-Do: Build a useful check to handle the case that the stock is not yet evaluated and therefore the key does not exist
    portfolio_informations = {
        'overallUrgency': sum(item["evaluation_results"]['urgency'] for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'overallBuy': sum(item["evaluation_results"]['buy'] for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'overallSell': sum(item["evaluation_results"]['sell'] for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'overallHold': sum(item["evaluation_results"]['hold'] for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'marketSummary': 'Dummy Market Summary',
        'currentOpportunities': 'Sample Opportunities',
        'currentRisks': 'Potential Risks',
        'other': 'Additional Information',
        'languageAssessment': 'Language Analysis'
    }

    return jsonify(portfolio_informations)

@app.route('/api/stocks')
def get_stocks():

    stocks_list = list(portfolio["assets"].values())

    # To-Do: Also build a way to handle case that the stock is not yet evaluated
    stocks_list.sort(key=lambda x: x["evaluation_results"]['urgency'], reverse=True)

    return jsonify(stocks_list)

#####################
# Portfolio LLM API #
#####################

@app.route('/api/evaluate-full-portfolio')
def evaluate_full_portfolio():

    assistant = PortfolioAIAssistant(
        provider="ollama",
        model="deepseek-r1:14b"
    )

    # To-Do: make portfolio variable public available
    # Maybe via the PortfolioAIAssistant object?

    try:
        portfolio = assistant.evaluate_portfolio(portfolio)
        response = {"response" : "Portfolio has been sucessfully evaluated."}
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(response)

@app.route('/api/evaluate-single-asset/<path:identifier>')
def evaluate_single_asset(identifier):

    assistant = PortfolioAIAssistant(
        provider="ollama",
        model="deepseek-r1:14b"
    )

    try:

        #To-Do: Needs to be implemented
        response = {"response" : "Not yet implemented!"}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(response)

##################
# Simple LLM API #
##################

@app.route('/api/simple-llm-request', methods=['POST'])
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
