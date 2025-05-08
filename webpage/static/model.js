class Stock {
  constructor(name) {
    this._name = name;
    this._urgency = 0;
    this._hold = 0;
    this._sell = 0;
    this._buy = 0;
    this._quantity = 0;
    this._buyInPrice = 0;
    this._currentReturn = 0;
    this._potentialUpside = 0;
    this._potentialDownside = 0;
    this._languageAssessment = '';
  }

  // Getter
  getName() { return this._name; }
  getUrgency() { return this._urgency; }
  getHold() { return this._hold; }
  getSell() { return this._sell; }
  getBuy() { return this._buy; }
  getQuantity() { return this._quantity; }
  getBuyInPrice() { return this._buyInPrice; }
  getCurrentReturn() { return this._currentReturn; }
  getPotentialUpside() { return this._potentialUpside; }
  getPotentialDownside() { return this._potentialDownside; }

  getLanguageAssessment() { return this._languageAssessment; }

  // Setter
  setName(name) { this._name = name; }
  setUrgency(urgency) { this._urgency = urgency; }
  setHold(hold) { this._hold = hold; }
  setSell(sell) { this._sell = sell; }
  setBuy(buy) { this._buy = buy; }
  setQuantity(quantity) { this._quantity = quantity; }
  setBuyInPrice(buyInPrice) { this._buyInPrice = buyInPrice; }
  setCurrentReturn(currentReturn) { this._currentReturn = currentReturn; }
  setPotentialUpside(potentialUpside) { this._potentialUpside = potentialUpside; }
  setPotentialDownside(potentialDownside) { this._potentialDownside = potentialDownside; }
  setLanguageAssessment(languageAssessment) { this._languageAssessment = languageAssessment; }

   //To-Do: add other important setters and getters
}

class Portfolio {
  constructor() {
    this._stocks = [];
    this._overallUrgency = 0;
    this._overallBuy = 0;
    this._overallSell = 0;
    this._overallHold = 0;
    this._marketSummary = '';
    this._currentOpportunities = '';
    this._currentRisks = '';
    this._other = '';
    this._languageAssessment = '';
  }

  // Stock management
  addStock(stock) { this._stocks.push(stock); }
  getStocks() { return this._stocks; }

  // Full getters
  getOverallUrgency() { return this._overallUrgency; }
  getOverallBuy() { return this._overallBuy; }
  getOverallSell() { return this._overallSell; }
  getOverallHold() { return this._overallHold; }
  getMarketSummary() { return this._marketSummary; }
  getCurrentOpportunities() { return this._currentOpportunities; }
  getCurrentRisks() { return this._currentRisks; }
  getOther() { return this._other; }
  getLanguageAssessment() { return this._languageAssessment; }

  // Full setters
  setOverallUrgency(urgency) { this._overallUrgency = urgency; }
  setOverallBuy(buy) { this._overallBuy = buy; }
  setOverallSell(sell) { this._overallSell = sell; }
  setOverallHold(hold) { this._overallHold = hold; }
  setMarketSummary(summary) { this._marketSummary = summary; }
  setCurrentOpportunities(opportunities) { this._currentOpportunities = opportunities; }
  setCurrentRisks(risks) { this._currentRisks = risks; }
  setOther(other) { this._other = other; }
  setLanguageAssessment(assessment) { this._languageAssessment = assessment; }

}

const portfolio = new Portfolio();