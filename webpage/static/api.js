class ApiService {
  static async loadPortfolioData() {
    try {
      const response = await fetch('/api/portfolio');
      const data = await response.json();

      portfolio.setOverallUrgency(data.overallUrgency);
      portfolio.setOverallBuy(data.overallBuy);
      portfolio.setOverallSell(data.overallSell);
      portfolio.setOverallHold(data.overallHold);
      portfolio.setMarketSummary(data.marketSummary);
      portfolio.setCurrentOpportunities(data.currentOpportunities);
      portfolio.setCurrentRisks(data.currentRisks);
      portfolio.setOther(data.other);
      portfolio.setLanguageAssessment(data.languageAssessment);
    } catch (error) {
      console.error('Error loading portfolio data:', error);
    }
  }

  static async loadStockData() {
    try {
      const response = await fetch('/api/stocks');
      const stocksData = await response.json();

      console.log('Debug - StockData:', (stocksData));

      portfolio.getStocks().splice(0); // Clear existing stocks
      stocksData.forEach(stockData => {
        const stock = new Stock(stockData.name);

        stock.setQuantity(stockData.quantity);
        stock.setBuyInPrice(stockData.purchase_price);
        stock.setCurrentReturn(stockData.current_yield);

        stock.setUrgency(stockData.evaluation_results.urgency);
        stock.setBuy(stockData.evaluation_results.buy);
        stock.setSell(stockData.evaluation_results.sell);
        stock.setHold(stockData.evaluation_results.hold);
        stock.setPotentialUpside(stockData.evaluation_results.potential_upside);
        stock.setPotentialDownside(stockData.evaluation_results.potential_downside);
        stock.setLanguageAssessment(stockData.evaluation_results.explanation_evaluation);

        portfolio.addStock(stock);
      });
    } catch (error) {
      console.error('Error loading stock data:', error);
    }
  }

  static async initialize() {
    await this.loadPortfolioData();
    await this.loadStockData();
  }
}