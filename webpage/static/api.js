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

      portfolio.getStocks().splice(0); // Clear existing stocks
      stocksData.forEach(stockData => {
        const stock = new Stock(stockData.name);
        stock.setUrgency(stockData.urgency);
        stock.setBuy(stockData.buy);
        stock.setSell(stockData.sell);
        stock.setHold(stockData.hold);
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