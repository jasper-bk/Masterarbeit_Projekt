#!/usr/bin/env python3

# To-Do:
# Simplify code
# Restrucure and order code
# Add suitable logging instead of print
# Needs option to see the process of the data and to provide it later on in an interface to understand what happened

from typing import Dict, List, Optional
import yfinance as yf
from llm import AIAssistant
import json
import re

class PortfolioAIAssistant(AIAssistant):
    """AI-powered portfolio analysis assistant with security evaluation capabilities"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.securities_data = {}

    def get_quantitative_data(self, identifier: str) -> Dict:
        """Retrieve quantitative financial data from Yahoo Finance"""
        try:
            # ticker = self._resolve_ticker(identifier) #TODO: Implement the use of this
            ticker = identifier # As long as we save the ticker

            stock = yf.Ticker(ticker)

            # TODO: Add more comprehensive data points
            return {
                "current_price": stock.info.get("currentPrice"),
                "pe_ratio": stock.info.get("trailingPE"),
                "market_cap": stock.info.get("marketCap"),
                "volume": stock.info.get("volume"),
                # TODO: Add historical data, technical indicators, etc.
            }
        except Exception as e:
            print(f"Error fetching quantitative data: {str(e)}")
            return {}


    def get_qualitative_data(self, identifier: str) -> List[str]:
        """Collect qualitative information from multiple sources"""

        llm_analysis = self._get_llm_analysis(identifier)

        news_items = self._get_scraped_news(identifier)

        results = f"""
        Available company informations from LLM:
        {llm_analysis}

        News informations:
        {news_items}
        """

        return results

    def _get_llm_analysis(self, identifier: str) -> List[str]:
        """Ask the LLM for informtaions about the company"""
        prompt = f"""
        Analyze the company with identifier {identifier} considering:
        1. Core business model and market position
        2. Notable recent activities (last 12 months)
        3. Potential risks and opportunities

        Include your knowledge cutoff date.
        """

        try:
            response = self.generate_response(prompt)
            return response
        except Exception as e:
            print(f"LLM analysis failed: {str(e)}")
            return []

    def _get_scraped_news(self, identifier: str) -> List[str]:
        """Scrape aktuelle Nachrichtenartikel"""
        try:
            return "No news implemented yet" #TODO: Implement the scraper

        except Exception as e:
            print(f"News scraping failed: {str(e)}")
            return []

    def assess_security(self,
                  security_data: Dict,
                  portfolio_attributes: Dict) -> Dict:
        """
        Evaluate security using LLM with comprehensive data analysis.
        Returns a dictionary with buy/sell/hold percentages and rationale.

        :param security_data: Dictionary containing quantitative and qualitative data
        :param portfolio_attributes: Dictionary containing portfolio-specific attributes
        :return: Dictionary with keys "buy", "sell", "hold" (summing to 100%) and "rationale"
        """
        # Construct analysis prompt
        prompt = f"""
        Analyze the following investment position and provide recommendations:

        **Company Fundamentals:**
        {json.dumps(security_data.get('quantitative', {}), indent=2)}

        **Market News:**
        {json.dumps(security_data.get('qualitative', []), indent=2)}

        **Portfolio Context:**
        {json.dumps(portfolio_attributes, indent=2)}

        Provide your recommendations in the following JSON format:
        {{
            "buy": <percentage>,
            "sell": <percentage>,
            "hold": <percentage>,
            "rationale": "<detailed explanation>"
        }}
        Ensure that the percentages sum to 100%.
        """

        try:
            print("Generating LLM response for security assessment...")
            response = self.generate_response(prompt)
            print(f"LLM raw response: {response}")

            # Parse the LLM response
            try:
                # Extract json from response via regex
                json_string = re.search(r"```json\n(.*?)\n```", response, re.DOTALL).group(1)

                print(f"LLM extracted JSON response: {json_string}")

                # Attempt to parse the response as JSON
                recommendation = json.loads(json_string)

                # Validate the response structure
                if not all(key in recommendation for key in ["buy", "sell", "hold", "rationale"]):
                    raise ValueError("Missing required keys in LLM response")

                # Validate that percentages sum to 100%
                total = recommendation["buy"] + recommendation["sell"] + recommendation["hold"]
                if not abs(total - 100.0) < 0.01:  # Allow for floating-point inaccuracies
                    raise ValueError(f"Percentages do not sum to 100% (sum: {total})")

                print("Successfully parsed and validated LLM response")
                return recommendation

            except json.JSONDecodeError as e:
                # Fallback: If the response is not valid JSON, extract percentages and rationale
                print("LLM response is not valid JSON. Attempting to extract data...")
                print(f"Assessment failed: {str(e)}")
                return {
                    "buy": 0.0,
                    "sell": 0.0,
                    "hold": 0.0,
                    "rationale": f"Error: {str(e)}"
                }

        except Exception as e:
            print(f"Assessment failed: {str(e)}")
            return {
                "buy": 0.0,
                "sell": 0.0,
                "hold": 0.0,
                "rationale": f"Error: {str(e)}"
            }

    def _resolve_ticker(self, identifier: str, id_type: str = "WKN") -> str:
        """Convert WKN/ISIN to Yahoo Finance ticker (placeholder implementation)"""
        # TODO: Implement proper financial identifier resolution
        # This should handle different identifier types and market data sources

        # Idea: Using an API or Scrape certain pages or always use Ticker in the first place

        return "AAPL"  # Dummy return for testing

    def evaluate_portfolio(self,
                         portfolio: Dict[str, Dict],
                         llm_configs: Optional[List[Dict]] = None) -> Dict:
        """
        Analyze entire portfolio of securities
        Returns aggregated assessments for all positions
        """
        results = {}

        for security_id, attributes in portfolio.items():
            quant_data = self.get_quantitative_data(security_id)
            qual_data = self.get_qualitative_data(security_id)

            assessment = self.assess_security(
                security_data={"quantitative": quant_data, "qualitative": qual_data},
                portfolio_attributes=attributes
            )

            results[security_id] = assessment

        # TODO: Add portfolio-level analysis and risk assessment
        return results


    def evaluate_with_multiple_llms(self,
                                  portfolio: Dict[str, Dict],
                                  llm_configs: List[Dict]) -> Dict:
        """
        Compare assessments from different LLM configurations
        Returns analysis with variance between models
        """
        aggregated_results = {}

        for config in llm_configs:
            assistant = PortfolioAIAssistant(**config)
            results = assistant.evaluate_portfolio(portfolio)
            for security_id, assessment in results.items():
                if security_id not in aggregated_results:
                    aggregated_results[security_id] = []
                aggregated_results[security_id].append(assessment)

        # TODO: Calculate variance and confidence intervals
        # TODO: Implement consensus recommendation logic
        return aggregated_results

    # Additional utility methods (stubs)
    def _calculate_risk_metrics(self, security_data: Dict) -> Dict:
        """Calculate risk metrics (VaR, volatility, etc.)"""
        # TODO: Implement risk calculation logic
        return {}

    def _get_technical_indicators(self, historical_data: Dict) -> Dict:
        """Calculate technical indicators from price history"""
        # TODO: Implement TA calculation (RSI, MACD, etc.)
        return {}


def main():
    """Simple test of PortfolioAIAssistant with tech stocks"""

    # Test portfolio with dummy position data
    test_portfolio = {
        "GOOG": {  # Alphabet (Google)
            "purchase_price": 134.50,
            "quantity": 25,
            "holding_days": 450,
            "current_yield": 0.0045
        },
        "BAYN.DE": {  # Bayer AG
            "purchase_price": 45.30,
            "quantity": 150,
            "holding_days": 600,
            "current_yield": 0.026
        }
    }

    # Initialize assistant with test configuration
    assistant = PortfolioAIAssistant(
        provider="ollama",
        model="deepseek-r1:14b"
    )


    # Run portfolio evaluation
    results = assistant.evaluate_portfolio(test_portfolio)

    # Print formatted results
    print("\nPortfolio Evaluation Report:")
    for ticker, assessment in results.items():
        print(f"\n{ticker} Analysis:")
        print(f" Buy recommendation: {assessment.get('buy', 0):.1f}%")
        print(f" Sell recommendation: {assessment.get('sell', 0):.1f}%")
        print(f" Hold recommendation: {assessment.get('hold', 0):.1f}%")
        print(f" Rationale: {assessment.get('rationale', '')[:200]}...")  # Truncate long text

if __name__ == "__main__":
    main()