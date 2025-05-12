#!/usr/bin/env python3

import json
import re
import yfinance as yf
from typing import Dict, List, Optional
from llm import AIAssistant

# To-Do: Build a more advanced logging and debugging options to check intermediate results

class PortfolioAIAssistant(AIAssistant):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_quantitative_data(self, identifier: str) -> Dict:
        try:

            stock = yf.Ticker(identifier)
            return {
                "current_price": stock.info.get("currentPrice"),
                "pe_ratio": stock.info.get("trailingPE"),
                "market_cap": stock.info.get("marketCap"),
                "volume": stock.info.get("volume"),
            }
        except Exception as e:
            print(f"[Error] Quantitative data: {e}")
            return {}

    def get_qualitative_data(self, identifier: str) -> List[str]:
        try:
            llm_info = self._get_llm_analysis(identifier)
            news_info = self._get_scraped_news(identifier)
            return f"LLM: {llm_info}\n\nNews: {news_info}"
        except Exception as e:
            print(f"[Error] Qualitative data: {e}")
            return []

    def _get_llm_analysis(self, identifier: str) -> str:
        prompt = f"""Analyze {identifier} (business model, recent events, risks/opportunities)."""
        return self.generate_response(prompt)

    def _get_scraped_news(self, identifier: str) -> str:
        return "News scraping not implemented yet"

    def assess_security(self, security_data: Dict, portfolio_attributes: Dict) -> Dict:
        prompt = f"""
        Analyze this investment:

        Quantitative data:
        {json.dumps(security_data.get('quantitative', {}), indent=2)}

        Qualitative data:
        {security_data.get('qualitative', '')}

        Portfolio context:
        {json.dumps(portfolio_attributes, indent=2)}

        Provide JSON with:
        {{
          "urgency_to_act": <percent>,
          "buy": <percent>,
          "sell": <percent>,
          "hold": <percent>,
          "rationale": "<text>"
        }}
        Ensure buy + sell + hold == 100
        """
        try:
            raw = self.generate_response(prompt)
            match = re.search(r"```json\n(.*?)\n```", raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group(1))
                total = parsed["buy"] + parsed["sell"] + parsed["hold"]
                if abs(total - 100) > 1:
                    raise ValueError("Percentages don't sum to 100")
                return parsed
        except Exception as e:
            print(f"[Error] Security assessment: {e}")
        return {
            "urgency_to_act": 0,
            "buy": 0,
            "sell": 0,
            "hold": 0,
            "rationale": "Assessment failed or invalid format"
        }

    def evaluate_portfolio(self, portfolio: Dict) -> Dict:
        assets = portfolio.get("assets", {})
        for ticker, asset in assets.items():
            print(f"Evaluating {ticker}...")
            quant = self.get_quantitative_data(ticker)
            qual = self.get_qualitative_data(ticker)

            # Remove old evaluation_results if present
            asset.pop("evaluation_results", None)

            assessment = self.assess_security(
                security_data={"quantitative": quant, "qualitative": qual},
                portfolio_attributes=asset
            )

            # Store evaluation in asset
            asset["evaluation_results"] = {
                "urgency": assessment["urgency_to_act"],
                "buy": assessment["buy"],
                "sell": assessment["sell"],
                "hold": assessment["hold"],
                "potential_upside": quant.get("pe_ratio", 0), # To-Do: Should be also evaluated from LLM
                "potential_downside": 0,  # Dummy or computed value # To-Do: Should be also evaluated from LLM
                "explanation_evaluation": assessment["rationale"]
            }

        # Run portfolio-level evaluation
        portfolio["portfolio_evaluation_results"] = self.evaluate_portfolio_summary(portfolio)

        return portfolio

    def evaluate_portfolio_summary(self, portfolio: Dict) -> Dict:
        try:
            # Create LLM summary of the full portfolio
            summary_prompt = f"""
            Analyze this portfolio based on the following assets and their evaluations:

            {json.dumps(portfolio["assets"], indent=2)}

            Provide a summary JSON with:
            {{
              "market_summary": "<text>",
              "current_opportunities": "<text>",
              "current_risks": "<text>",
              "other": "<text>",
              "explanation_evaluation": "<longer explanation>"
            }}
            """
            raw_summary = self.generate_response(summary_prompt)
            match = re.search(r"```json\n(.*?)\n```", raw_summary, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception as e:
            print(f"[Error] Portfolio summary: {e}")
        return {
            "market_summary": "N/A",
            "current_opportunities": "N/A",
            "current_risks": "N/A",
            "other": "N/A",
            "explanation_evaluation": "Portfolio summary failed."
        }


### Entry point

# This function is just used for testing without rest of application
def main():
    with open("./test_data/sample_new_portfolio_structure.json", 'r') as f:
        portfolio = json.load(f)

    assistant = PortfolioAIAssistant(
        provider="ollama",
        model="deepseek-r1:14b"
    )

    result = assistant.evaluate_portfolio(portfolio)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
