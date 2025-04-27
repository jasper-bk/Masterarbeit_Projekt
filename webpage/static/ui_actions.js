$(async function () {
    // Initialize API first
    await ApiService.initialize();

    // UI Setup
    const container = 'body';
    $('.draggable').draggable({ cancel: '.ui-resizable-handle', grid: [20, 20], containment: container });
    $('.resizable').resizable({ grid: [20, 20], handles: 'n, e, s, w, ne, se, sw, nw', containment: container });

    // Urgency Display
    let urgencyValue = portfolio.getOverallUrgency();
    document.getElementById('urgency-text').textContent = `Urgency: ${urgencyValue}%`;

    // Market Info Box
    let marketSummaryText = portfolio.getMarketSummary();
    document.getElementById('market-summary-text').textContent = marketSummaryText;
    let currentOpportunitiesText = portfolio.getCurrentOpportunities();
    document.getElementById('current-opportunities-text').textContent = currentOpportunitiesText;
    let currentRisksText = portfolio.getCurrentRisks();
    document.getElementById('current-risks-text').textContent = currentRisksText;
    let otherText = portfolio.getOther();
    document.getElementById('other-text').textContent = otherText;

    // Traffic light
    if (urgencyValue >= 66) {
      document.getElementById('light-red').classList.add('active');
    } else if (urgencyValue >= 33) {
      document.getElementById('light-yellow').classList.add('active');
    } else {
      document.getElementById('light-green').classList.add('active');
    }

    // Chart Initialization
    const ctx = document.getElementById('pieChart').getContext('2d');
    new Chart(ctx, {
      type: 'pie',
      data: {
        labels: ['Sell', 'Hold', 'Buy'],
        datasets: [{
          data: [portfolio.getOverallSell(), portfolio.getOverallHold(), portfolio.getOverallBuy()],
          backgroundColor: ['#dc3545', '#6c757d', '#28a745']
        }]
      },
      options: { responsive: false, plugins: { legend: { display: false } }
    }});

    // Explanation and Evaluation Box
    let explanationEvaluationText = portfolio.getLanguageAssessment();
    document.getElementById('explanation-evaluation-text').textContent = explanationEvaluationText;

    // Initial render
    renderUrgencyList();
  });


  // Tab management
  function openStockTab(stockName) {
    const tabId = stockName.replace(/\s+/g, '-').toLowerCase();
    if (!document.getElementById(`tab-${tabId}`)) {
      const closeBtn = `<span class="close-tab" onclick="closeTab('${tabId}')">&times;</span>`;
      const newTab = document.createElement('li');
      newTab.classList.add('nav-item');
      newTab.innerHTML = `<button class="nav-link" id="tab-${tabId}-tab" data-bs-toggle="tab" data-bs-target="#tab-${tabId}" type="button" role="tab">${stockName} ${closeBtn}</button>`;
      document.getElementById('dashboardTabs').appendChild(newTab);

      const newTabPane = document.createElement('div');
      newTabPane.classList.add('tab-pane', 'fade');
      newTabPane.id = `tab-${tabId}`;
      newTabPane.setAttribute('role', 'tabpanel');
      newTabPane.innerHTML = `<div class="box">Detailed info for ${stockName}</div>`;
      document.getElementById('dashboardTabsContent').appendChild(newTabPane);
    }
    bootstrap.Tab.getOrCreateInstance(document.querySelector(`#tab-${tabId}-tab`)).show();
  }

  function closeTab(tabId) {
    const tabButton = document.getElementById(`tab-${tabId}-tab`);
    const tabPane = document.getElementById(`tab-${tabId}`);
    if (tabButton && tabPane) {
      const parentLi = tabButton.closest('li');
      if (tabButton.classList.contains('active')) {
        bootstrap.Tab.getOrCreateInstance(document.querySelector('#overview-tab')).show();
      }
      parentLi.remove();
      tabPane.remove();
    }
  }

  // Render urgency list from portfolio data
  function renderUrgencyList() {
    const container = document.getElementById('urgency-items');
    container.innerHTML = '';

    portfolio.getStocks().forEach(stock => {
      const urgencyPercent = Math.round(stock.getUrgency() * 100);
      const li = document.createElement('li');
      li.className = 'list-group-item';
      li.textContent = `${stock.getName()} - ${urgencyPercent}%`;
      li.onclick = () => openStockTab(stock.getName());
      container.appendChild(li);
    });
  }