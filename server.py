#!/usr/bin/env python3

from flask import Flask, request, jsonify
from llm import AIAssistant

app = Flask(__name__)

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
        recommendation = assistant.generate_response(data['prompt'])

        return jsonify({
            "recommendation": recommendation,
            "model": assistant.model
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def main():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
