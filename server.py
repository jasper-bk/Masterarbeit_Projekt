#!/usr/bin/env python3

from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from llm import AIAssistant
from portfolio_ai import PortfolioAIAssistant
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
pf.add_asset("MBG.DE", name="Mercedes-Benz Group")
pf.add_trade("MBG.DE", quantity=10, price=50.10, date_str="2023-05-01")
pf.add_trade("MBG.DE", quantity=56, price=52.00, date_str="2023-06-01")

pf.add_asset("GOOG", name="Alphabet")
pf.add_trade("GOOG", quantity=25, price=134.50, date_str="2023-02-15")

pf.add_asset("BAYN.DE", name="Bayer AG")
pf.add_trade("BAYN.DE", quantity=300, price=60.51, date_str="2023-02-15")

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
    global portfolio #should be replaced later with better practice

    try:
        assistant.evaluate_portfolio(pf)
        response = {"response" : "Portfolio has been sucessfully evaluated."}
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(response)

@app.route('/api/evaluate-single-asset/<path:identifier>')
def evaluate_single_asset(identifier):
    global portfolio #should be replaced later with better practice

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

def _build_chat_prompt(user_message: str, portfolio_ctx: dict) -> str:

    # The whole chat prompt thing should be moved to the assistant class later and using LangChain
    # Sould also not rely on portfolio_ctx from frontend. Just get data from portfolio object directly

    # Shallow copy
    ctx = portfolio_ctx or {}

    # Light trimming for safety
    try:
      trimmed = {
          "summary": ctx.get("summary", {}),
          "stocks": []
      }
      stocks = ctx.get("stocks", []) or []
      # Keep up to 30 stocks; for each, keep only relevant keys
      for stock in stocks[:30]:
          trimmed["stocks"].append({
              "identifier": stock.get("identifier"),
              "name": stock.get("name"),
              "quantity": stock.get("quantity"),
              "buyInPrice": stock.get("buyInPrice"),
              "currentReturn": stock.get("currentReturn"),
              "urgency": stock.get("urgency"),
              "buy": stock.get("buy"),
              "sell": stock.get("sell"),
              "hold": stock.get("hold"),
              "potentialUpside": stock.get("potentialUpside"),
              "potentialDownside": stock.get("potentialDownside"),
              # keep assessment but clip to 800 chars to avoid huge prompts
              "languageAssessment": (stock.get("languageAssessment") or "")[:800]
          })
    except Exception:
      trimmed = ctx

    prompt = (
        "You are a helpful investment assistant. "
        "Answer briefly, clearly, and cite concrete figures from the provided context when relevant. "
        "Avoid hallucinating tickers or prices not present in the context. "
        "If information is missing, say so and propose the next best step.\n\n"
        f"USER MESSAGE:\n{user_message}\n\n"
        "PORTFOLIO CONTEXT (JSON):\n"
        f"{json.dumps(trimmed, ensure_ascii=False, indent=2)}\n\n"
        "Now provide your answer to the user:"
    )
    return prompt


@app.route('/api/chat', methods=['POST'])
def chat_with_assistant():
    """
    Accepts: { "message": str, "context": { "portfolio": {...} } }
    Returns: { "reply": str }
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        user_message = (payload.get("message") or "").strip()
        context = payload.get("context") or {}
        portfolio_ctx = context.get("portfolio") or {}

        if not user_message:
            return jsonify({"error": "Missing 'message'"}), 400

        # Build the prompt using the provided frontend context
        prompt = _build_chat_prompt(user_message, portfolio_ctx)

        # Use a lightweight generic assistant for chat
        chat_assistant = AIAssistant(
            provider="ollama",
            model="qwen3:14b",
            langchain=False
        )

        reply = chat_assistant.generate_response(prompt)
        # Ensure string
        if not isinstance(reply, str):
            reply = str(reply)

        return jsonify({"reply": reply})
    except Exception as e:
        # Keep error generic for client; log detail server-side if needed
        return jsonify({"error": str(e)}), 500


def main():
    app.run(debug=True) # for development only
    # app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
