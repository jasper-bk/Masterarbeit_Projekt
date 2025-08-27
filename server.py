#!/usr/bin/env python3

from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS

from llm import AIAssistant

from portfolio_ai import PortfolioAIAssistant
from portfolio_chat import PortfolioChat

import re
import json
import dotenv

app = Flask(__name__, template_folder='webpage/templates', static_folder='webpage/static')
CORS(app)  # Enable CORS if needed


# replace with faster LLM
#assistant = PortfolioAIAssistant(
#    provider="ollama",
#    model="deepseek-r1:14b"
#)

dotenv.load_dotenv()

assistant = PortfolioAIAssistant(
    provider="ollama",
    model="qwen3:14b",
    finance_provider="yfinance",
    ensemble=False,
)

pf = assistant.new_portfolio("Sample Portfolio", "Long-term growth / balanced risk")
pf.add_asset("MBGAF", name="Mercedes-Benz Group")
pf.add_trade("MBGAF", quantity=10, price=50.10, date_str="2023-05-01")
pf.add_trade("MBGAF", quantity=56, price=52.00, date_str="2023-06-01")

pf.add_asset("GOOG", name="Alphabet")
pf.add_trade("GOOG", quantity=25, price=134.50, date_str="2023-02-15")

pf.add_asset("ASML", name="ASML Holding N.V.")
pf.add_trade("ASML", quantity=4, price=460.44, date_str="2022-06-08")

pf.add_asset("DKILY", name="Daikin Industries")
pf.add_trade("DKILY", quantity=4, price=150.12, date_str="2022-06-08")

chat = PortfolioChat(assistant, pf, use_rag=True)

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

    portfolio_dict = pf.to_dict()

    stocks_list = list(portfolio_dict["assets"].values())

    default_if_empty_str = "Not evaluated yet. Run evaluation to see results."

    # Idea: Just pass the whole portfolio JSON to the frontend and do all calculations, sorting there. JSON could be just reloaded

    # To-Do: Build a useful check to handle the case that the stock is not yet evaluated and therefore the key does not exist
    portfolio_informations = {
        'overallUrgency': sum(item["evaluation_results"].get('urgency', 0) for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'overallBuy': sum(item["evaluation_results"].get('buy', 0) for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'overallSell': sum(item["evaluation_results"].get('sell', 0) for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'overallHold': sum(item["evaluation_results"].get('hold', 0) for item in stocks_list) / len(stocks_list) if stocks_list else 0,
        'marketSummary': portfolio_dict.get("portfolio_evaluation_results", {}).get("market_summary", default_if_empty_str),
        'currentOpportunities': portfolio_dict.get("portfolio_evaluation_results", {}).get("current_opportunities", default_if_empty_str),
        'currentRisks': portfolio_dict.get("portfolio_evaluation_results", {}).get("current_risks", default_if_empty_str),
        'other': portfolio_dict.get("portfolio_evaluation_results", {}).get("other", default_if_empty_str),
        'languageAssessment': portfolio_dict.get("portfolio_evaluation_results", {}).get("explanation_evaluation", default_if_empty_str)
    }


    return jsonify(portfolio_informations)

@app.route('/api/stocks')
def get_stocks():

    # Moving original key into the dictionary as new attribute
    stocks_list = [{"identifier": key, **value} for key, value in pf.to_dict()["assets"].items()]

    # To-Do: Also build a way to handle case that the stock is not yet evaluated
    stocks_list.sort(key=lambda x: x["evaluation_results"].get('urgency',0), reverse=True)

    return jsonify(stocks_list)

#####################
# Portfolio LLM API #
#####################

@app.route('/api/evaluate-full-portfolio')
def evaluate_full_portfolio():

    try:
        assistant.evaluate_portfolio(pf)
        response = {"response" : "Portfolio has been sucessfully evaluated."}
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(response)

@app.route('/api/evaluate-single-asset/<path:identifier>')
def evaluate_single_asset(identifier):

    try:
        assistant.evaluate_portfolio(pf, specific_assets=[identifier])
        response = {"response" : f"{identifier} has been sucessfully evaluated."}

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
        model=data.get('model', 'deepseek-r1:1.5b'),
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


# =========================
# ADDED: Chat API endpoint
# =========================

@app.route('/api/chat', methods=['POST'])
def chat_with_assistant():
    """
    Accepts: { "message": str, "context": { "portfolio": {...} } }
    Returns: { "reply": str }
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        user_message = (payload.get("message") or "").strip()
        # To-Do: give context about what the user currently sees

        if not user_message:
            return jsonify({"error": "Missing 'message'"}), 400

        session_id = "default"

        reply = chat.ask(session_id, user_message)

        flag_remove_think = True

        if flag_remove_think:
            reply = re.sub(r'<think>.*?</think>', '', reply, flags=re.DOTALL).strip()

        # Ensure string
        if not isinstance(reply, str):
            reply = str(reply)

        return jsonify({"reply": reply})
    except Exception as e:
        # Keep error generic for client; log detail server-side if needed
        return jsonify({"error": str(e)}), 500


def main():
    #app.run(debug=True) # for development only
    app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    main()
