#!/usr/bin/env python3

from flask import Flask, request, jsonify
from llm import PortfolioAssistant

app = Flask(__name__)

@app.route('/analyze', methods=['POST'])
def analyze_portfolio():
    """API endpoint for portfolio analysis"""
    data = request.json

    assistant = PortfolioAssistant(
        provider=data.get('provider', 'ollama'),
        model=data.get('model', 'deepseek-r1:14b'),
        langchain=data.get('langchain', False)
    )

    try:
        recommendation = assistant.generate_recommendation(data['prompt'])

        return jsonify({
            "recommendation": recommendation,
            "explanation": explanation,
            "model": assistant.model
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def main():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
