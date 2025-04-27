$(function () {
    const container = 'body';
    $('.draggable').draggable({ cancel: '.ui-resizable-handle', grid: [20, 20], containment: container });
    $('.resizable').resizable({ grid: [20, 20], handles: 'n, e, s, w, ne, se, sw, nw', containment: container });
  });

  const urgencyValue = 34;
  document.getElementById('urgency-text').textContent = `Urgency: ${urgencyValue}%`;
  if (urgencyValue >= 66) {
    document.getElementById('light-red').classList.add('active');
  } else if (urgencyValue >= 33) {
    document.getElementById('light-yellow').classList.add('active');
  } else {
    document.getElementById('light-green').classList.add('active');
  }

  const ctx = document.getElementById('pieChart').getContext('2d');
  new Chart(ctx, {
    type: 'pie',
    data: {
      labels: ['Sell', 'Hold', 'Buy'],
      datasets: [{ data: [20, 10, 70], backgroundColor: ['#dc3545', '#6c757d', '#28a745'] }]
    },
    options: { responsive: false, plugins: { legend: { display: false } } }
  });

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

  function renderUrgencyList() {
    const dataStr = '{"Bayer": {"urgency": 0.5}, "BASF": {"urgency": 0.4}, "Meta": {"urgency": 0.25}, "Amazon": {"urgency": 0.0}}';
    const data = JSON.parse(dataStr);
    // fetch('/api/urgency') // Uncomment when connected to API
    //   .then(response => response.json())
    //   .then(data => {

    const container = document.getElementById('urgency-items');
    container.innerHTML = '';
    for (const [stock, info] of Object.entries(data)) {
      const urgencyPercent = Math.round(info.urgency * 100);
      const li = document.createElement('li');
      li.className = 'list-group-item';
      li.textContent = `${stock} - ${urgencyPercent}%`;
      li.onclick = () => openStockTab(stock);
      container.appendChild(li);
    }
  }

  renderUrgencyList();