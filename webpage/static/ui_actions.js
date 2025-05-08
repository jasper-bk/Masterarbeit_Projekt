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

function initializeChatWidget() {
  const chatToggle = document.getElementById('chat-toggle');
  const chatWindow = document.getElementById('chat-window');
  const chatClose = document.getElementById('chat-close');
  const chatSubmit = document.getElementById('chat-submit');
  const chatInput = document.getElementById('chat-input');
  const chatMessages = document.getElementById('chat-messages');

  chatToggle.addEventListener('click', () => {
    chatWindow.classList.toggle('d-none');
  });

  chatClose.addEventListener('click', () => {
    chatWindow.classList.add('d-none');
  });

  chatSubmit.addEventListener('click', () => {
    const message = chatInput.value.trim();
    if (message !== '') {
      console.log('Chat message:', message);

      const msgDiv = document.createElement('div');
      msgDiv.textContent = message;
      msgDiv.className = 'mb-2 text-end text-primary';
      chatMessages.appendChild(msgDiv);
      chatMessages.scrollTop = chatMessages.scrollHeight;

      chatInput.value = '';
    }
  });

  //To-Do: Planned to send messages with current context to LLM and display response
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
  initializeChatWidget();
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

class StockTab {
  /**
   * @param {Object} stock  — an object holding all your values, e.g.
   *    { name, quantity, value, currentReturn, upside, downside, urgency, sell, hold, buy, assessmentText }
   */
  constructor(stock) {
    this.stock = stock;
    this.tabId = stock.name.replace(/\s+/g, '-').toLowerCase();
  }

  /**
   * Creates the <li> and <div class="tab-pane">,
   * injects them into the DOM and sets up the chart & traffic light.
   */
  init() {
    // 1) Create tab button
    if (!document.getElementById(`tab-${this.tabId}-tab`)) {
      const closeBtn = `<span class="close-tab" onclick="closeTab('${this.tabId}')">&times;</span>`;
      const li = document.createElement('li');
      li.classList.add('nav-item');
      li.innerHTML = `
        <button class="nav-link"
                id="tab-${this.tabId}-tab"
                data-bs-toggle="tab"
                data-bs-target="#tab-${this.tabId}"
                type="button" role="tab">
          ${this.stock.name} ${closeBtn}
        </button>`;
      document.getElementById('dashboardTabs').appendChild(li);

      // 2) Create tab content pane
      const pane = document.createElement('div');
      pane.classList.add('tab-pane', 'fade');
      pane.id = `tab-${this.tabId}`;
      pane.setAttribute('role', 'tabpanel');
      pane.innerHTML = this._template();
      document.getElementById('dashboardTabsContent').appendChild(pane);

      // 3) After injecting HTML, wire up components:
      this._renderValues();
      this._renderTrafficLight();
      this._renderChart();
    }

    // 4) Show it
    bootstrap.Tab.getOrCreateInstance(
      document.getElementById(`tab-${this.tabId}-tab`)
    ).show();
  }

  /** Returns the HTML string for this stock’s dashboard */
  _template() {
    return `
      <div class="container-fluid p-3">
        <div class="row">
          <!-- Stock Info Box -->
          <div class="col-md-3 box draggable resizable">
            <h4>${this.stock.name} Details</h4>
            <strong>Personal Information:</strong><br/>
            <span>Quantity: <span class="text-primary" id="quantity-${this.tabId}">0</span></span><br/>
            <span>Value: <span class="text-primary" id="value-${this.tabId}">€0</span></span><br/>
            <span>Current Return: <span class="text-primary" id="yield-${this.tabId}">+0.0%</span></span><br/>
            <hr/>
            <strong>Assessment:</strong><br/>
            <span>Potential Upside: <span class="text-primary" id="upside-${this.tabId}">+0%</span></span><br/>
            <span>Potential Downside: <span class="text-primary" id="downside-${this.tabId}">+0%</span></span><br/>
          </div>

          <!-- Stock Quick Overview -->
          <div class="col-md-6">
            <div class="col-md-8 box draggable resizable">
              <h5>${this.stock.name} Overview</h5>
              <div class="d-flex align-items-center">
                <div class="traffic-light-container me-3">
                  <div class="traffic-light">
                    <div class="light red"   id="light-red-${this.tabId}"></div>
                    <div class="light yellow" id="light-yellow-${this.tabId}"></div>
                    <div class="light green"  id="light-green-${this.tabId}"></div>
                  </div>
                  <div class="urgency-text" id="urgency-${this.tabId}">Urgency: 0%</div>
                </div>
                <canvas id="pieChart-${this.tabId}" width="120" height="120"></canvas>
              </div>
            </div>

            <!-- Textual Evaluation -->
            <div class="col-md-10 box draggable resizable mt-3">
              <h6>Natural language assessment:</h6>
              <p class="text-primary" id="assessment-${this.tabId}">
                ...
              </p>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /** Fill in all numeric/text fields from this.stock */
  _renderValues() {
    const s = this.stock, id = this.tabId;
    document.getElementById(`quantity-${id}`).textContent = s.quantity;
    document.getElementById(`value-${id}`).textContent = `€${s.value}`;
    document.getElementById(`yield-${id}`).textContent = s.currentReturn;
    document.getElementById(`upside-${id}`).textContent = s.upside;
    document.getElementById(`downside-${id}`).textContent = s.downside;
    document.getElementById(`urgency-${id}`).textContent = `Urgency: ${s.urgency}%`;
    document.getElementById(`assessment-${id}`).textContent = s.assessmentText;
  }

  /** Activate the correct traffic-light color */
  _renderTrafficLight() {
    const u = this.stock.urgency, id = this.tabId;
    [ 'red', 'yellow', 'green' ].forEach(color =>
      document.getElementById(`light-${color}-${id}`).classList.remove('active')
    );
    if (u >= 66) document.getElementById(`light-red-${id}`).classList.add('active');
    else if (u >= 33) document.getElementById(`light-yellow-${id}`).classList.add('active');
    else document.getElementById(`light-green-${id}`).classList.add('active');
  }

  /** Draw the pie chart using Chart.js */
  _renderChart() {
    const id = this.tabId;
    const ctx = document.getElementById(`pieChart-${id}`).getContext('2d');
    if (this._chart) this._chart.destroy();
    this._chart = new Chart(ctx, {
      type: 'pie',
      data: {
        labels: ['Sell','Hold','Buy'],
        datasets: [{
          data: [this.stock.sell, this.stock.hold, this.stock.buy],
          backgroundColor: ['#dc3545','#6c757d','#28a745']
        }]
      },
      options: { responsive: false, plugins: { legend: { display: false } } }
    });
  }
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
function openStockTab(stockObj) {
  // Here you’d look up the real stock object by name:
  const stockTabObj = {
    name: stockObj.getName(),
    quantity: stockObj.getQuantity(),
    value: stockObj.getQuantity() * stockObj.getBuyInPrice(),
    currentReturn: stockObj.getCurrentReturn(),

    upside: "+" + stockObj.getPotentialUpside() + "%",
    downside: "- " + stockObj.getPotentialDownside() + "%",
    urgency: stockObj.getUrgency(),
    sell: stockObj.getSell(),
    hold: stockObj.getHold(),
    buy: stockObj.getBuy(),
    assessmentText: stockObj.getLanguageAssessment()
  };

  // Instantiate and initialize the tab
  const tab = new StockTab(stockTabObj);
  tab.init();
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
    li.onclick = () => openStockTab(stock);
    container.appendChild(li);
  });
}
