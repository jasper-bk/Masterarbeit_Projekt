// Simulated local storage for JSONs (can later be replaced by real backend)
let jsonFiles = [];

// Initialize settings modal and button events
function initializeSettingsModal() {
  $('#settingsButton').on('click', function () {
    updateJsonDropdown();
    const modal = new bootstrap.Modal(document.getElementById('settingsModal'));
    modal.show();
  });

  $('#uploadJsonBtn').on('click', function () {
    const fileInput = document.getElementById('jsonUpload');
    const file = fileInput.files[0];
    if (file && file.type === 'application/json') {
      const reader = new FileReader();
      reader.onload = function (e) {
        try {
          const content = JSON.parse(e.target.result);
          jsonFiles.push({ name: file.name, data: content });
          updateJsonDropdown();
          alert(`"${file.name}" uploaded successfully.`);
        } catch (err) {
          alert('Invalid JSON file.');
        }
      };
      reader.readAsText(file);
    } else {
      alert('Please select a valid .json file.');
    }
  });

  $('#deleteJsonBtn').on('click', function () {
    const selected = $('#jsonSelect').val();
    if (selected) {
      jsonFiles = jsonFiles.filter(file => file.name !== selected);
      updateJsonDropdown();
      alert(`"${selected}" deleted.`);
    } else {
      alert('No file selected to delete.');
    }
  });
}

// Refresh dropdown with current file list
function updateJsonDropdown() {
  const select = $('#jsonSelect');
  select.empty();
  jsonFiles.forEach(file => {
    select.append(`<option value="${file.name}">${file.name}</option>`);
  });
}

// Modified initialization
$(async function () {
  // Initialize API and UI
  await ApiService.initialize();
  initializeUI();
  initializeSettingsModal();
  await renderDashboard();

  // Button events
  $('#refreshAllBtn').on('click', async function () {
    await handleRefresh(this, async () => {
      await ApiService.initialize(); // Optionally fetch fresh data
      await renderDashboard();
    });
  });

  $('#refreshBtn').on('click', async function () {
    await handleRefresh(this, async () => {
      // Could target specific tab later
      await renderDashboard();
    });
  });
});

// Set up draggable/resizable components
function initializeUI() {
  const container = 'body';
  $('.draggable').draggable({
    cancel: '.ui-resizable-handle',
    grid: [20, 20],
    containment: container
  });
  $('.resizable').resizable({
    grid: [20, 20],
    handles: 'n, e, s, w, ne, se, sw, nw',
    containment: container
  });
}

// Main dashboard rendering logic
async function renderDashboard() {
  // Update urgency indicator
  const urgencyValue = Math.round(portfolio.getOverallUrgency());
  $('#urgency-text').text(`Urgency: ${urgencyValue}%`);
  $('.light').removeClass('active');
  if (urgencyValue >= 66) $('#light-red').addClass('active');
  else if (urgencyValue >= 33) $('#light-yellow').addClass('active');
  else $('#light-green').addClass('active');

  // Fill in market data
  $('#market-summary-text').text(portfolio.getMarketSummary());
  $('#current-opportunities-text').text(portfolio.getCurrentOpportunities());
  $('#current-risks-text').text(portfolio.getCurrentRisks());
  $('#other-text').text(portfolio.getOther());

  // Fill in language-based assessment
  $('#explanation-evaluation-text').text(portfolio.getLanguageAssessment());

  // Render pie chart (destroy existing one if present)
  const ctx = document.getElementById('pieChart').getContext('2d');
  if (window.pieChartInstance) {
    window.pieChartInstance.destroy();
  }
  window.pieChartInstance = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: ['Sell', 'Hold', 'Buy'],
      datasets: [{
        data: [portfolio.getOverallSell(), portfolio.getOverallHold(), portfolio.getOverallBuy()],
        backgroundColor: ['#dc3545', '#6c757d', '#28a745']
      }]
    },
    options: {
      responsive: false,
      plugins: { legend: { display: false } }
    }
  });

  // Refresh urgency list
  renderUrgencyList();
}

// Handle refresh buttons with loading animation
async function handleRefresh(button, action) {
  const $btn = $(button);
  const originalText = $btn.html();
  $btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Refreshing...');
  try {
    await action();
  } catch (e) {
    console.error('Error during refresh:', e);
    alert('An error occurred while refreshing.');
  } finally {
    $btn.prop('disabled', false).html(originalText);
  }
}

// Open a new tab for a specific stock
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

// Close an existing stock tab
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

// Render list of stocks with urgency values
function renderUrgencyList() {
  const container = document.getElementById('urgency-items');
  container.innerHTML = '';
  portfolio.getStocks().forEach(stock => {
    const urgencyPercent = Math.round(stock.getUrgency());
    const li = document.createElement('li');
    li.className = 'list-group-item';
    li.textContent = `${stock.getName()} - ${urgencyPercent}%`;
    li.onclick = () => openStockTab(stock.getName());
    container.appendChild(li);
  });
}
