/**
 * DataMind Frontend Core Logic
 * Matches Figures 5.6, 5.7, 5.8, 5.9 and full functionality
 */

// Global State
const DataMind = {
  currentSection: 'home',
  activeDatasetId: null,
  activeDatasetName: null,
  datasets: [],
  categoryChart: null,
  productsChart: null,
  monthlyTrendChart: null,
  aiCharts: {},
  csrfToken: ''
};

// Helper to get CSRF token
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Navigation Handler
function navigateTo(section, updateHistory = true) {
  DataMind.currentSection = section;

  // Update sidebar active links
  document.querySelectorAll('.nav-link').forEach(link => {
    if (link.getAttribute('data-section') === section) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });

  // Show corresponding view
  document.querySelectorAll('.page-view').forEach(view => {
    if (view.id === `view-${section}`) {
      view.classList.add('active');
    } else {
      view.classList.remove('active');
    }
  });

  if (updateHistory) {
    const path = section === 'home' ? '/dashboard/' : `/dashboard/${section}/`;
    window.history.pushState({ section }, '', path);
  }

  // Section specific lifecycle
  if (section === 'insights') {
    loadInsightsData(DataMind.activeDatasetId);
  } else if (section === 'ask') {
    initMonthlyTrendChart();
  } else if (section === 'history') {
    loadHistoryList();
  } else if (section === 'datasets') {
    loadDatasetsList();
  }
}

// ==========================================
// DATASET UPLOAD LOGIC (Figure 5.7)
// ==========================================
let selectedUploadFile = null;

function setupUploadHandlers() {
  const dropzone = document.getElementById('uploadDropzone');
  const fileInput = document.getElementById('datasetFileInput');
  const filePreview = document.getElementById('fileSelectedBox');
  const uploadBtn = document.getElementById('btnUploadAnalyze');
  const chooseBtn = document.getElementById('btnChooseFile');

  if (!dropzone || !fileInput) return;

  chooseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener('click', () => {
    fileInput.click();
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('drag-over');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('drag-over');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      handleSelectedFile(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (fileInput.files.length > 0) {
      handleSelectedFile(fileInput.files[0]);
    }
  });

  uploadBtn.addEventListener('click', () => {
    if (!selectedUploadFile) return;
    performUploadAndAnalyze(selectedUploadFile);
  });
}

function handleSelectedFile(file) {
  selectedUploadFile = file;
  const filePreview = document.getElementById('fileSelectedBox');
  const fileName = document.getElementById('previewFileName');
  const fileDetails = document.getElementById('previewFileDetails');
  const uploadBtn = document.getElementById('btnUploadAnalyze');

  const sizeKb = Math.round(file.size / 1024);
  const sizeText = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;
  const ext = file.name.split('.').pop().toUpperCase();

  fileName.textContent = file.name;
  fileDetails.textContent = `${sizeText} • ${ext}`;
  filePreview.style.display = 'flex';
  uploadBtn.disabled = false;
}

function performUploadAndAnalyze(file) {
  const uploadBtn = document.getElementById('btnUploadAnalyze');
  const alertBox = document.getElementById('uploadAlertBox');

  uploadBtn.disabled = true;
  uploadBtn.textContent = 'Uploading & Analyzing...';
  alertBox.style.display = 'none';

  const formData = new FormData();
  formData.append('file', file);

  fetch('/api/datasets/upload/', {
    method: 'POST',
    headers: {
      'X-CSRFToken': DataMind.csrfToken
    },
    body: formData
  })
    .then(res => res.json().then(data => ({ status: res.status, body: data })))
    .then(({ status, body }) => {
      uploadBtn.disabled = false;
      uploadBtn.textContent = 'Upload & Analyze';

      if (status === 201) {
        alertBox.className = 'upload-status-alert alert-success';
        alertBox.textContent = 'Dataset uploaded and processed successfully! Redirecting to Insights...';
        alertBox.style.display = 'block';

        DataMind.activeDatasetId = body.dataset.id;
        DataMind.activeDatasetName = body.dataset.name;

        // Auto transition to insights
        setTimeout(() => {
          navigateTo('insights');
        }, 800);
      } else {
        alertBox.className = 'upload-status-alert alert-error';
        const errMsg = body.error || body.detail || (body.file ? (Array.isArray(body.file) ? body.file.join(' ') : body.file) : null) || 'Failed to upload dataset.';
        alertBox.textContent = errMsg;
        alertBox.style.display = 'block';
      }
    })
    .catch(err => {
      uploadBtn.disabled = false;
      uploadBtn.textContent = 'Upload & Analyze';
      alertBox.className = 'upload-status-alert alert-error';
      alertBox.textContent = 'Network or server error during upload.';
      alertBox.style.display = 'block';
    });
}

// ==========================================
// DATA INSIGHTS & CHARTS LOGIC (Figure 5.8)
// ==========================================
function loadInsightsData(datasetId) {
  const url = datasetId ? `/api/analytics/insights/${datasetId}/` : '/api/analytics/insights/';

  fetch(url, {
    headers: { 'X-CSRFToken': DataMind.csrfToken }
  })
    .then(res => res.json())
    .then(data => {
      if (data.success && data.insights) {
        DataMind.activeDatasetId = data.dataset_id;
        DataMind.activeDatasetName = data.dataset_name;
        renderInsightsUI(data.insights);
      }
    })
    .catch(err => console.error('Insights fetch failed:', err));
}

function renderInsightsUI(insights) {
  // 1. KPI Cards
  const totalSalesEl = document.getElementById('kpiTotalSales');
  const growthEl = document.getElementById('kpiGrowth');
  const bestCategoryEl = document.getElementById('kpiBestCategory');

  if (totalSalesEl) totalSalesEl.textContent = insights.total_sales_formatted || '₹ 22,40,000';
  if (growthEl) growthEl.textContent = insights.growth || '27.6 %';
  if (bestCategoryEl) bestCategoryEl.textContent = insights.best_category || 'Electronics';

  // 2. Center of Doughnut
  const centerValEl = document.getElementById('doughnutCenterVal');
  if (centerValEl) {
    centerValEl.textContent = insights.total_sales_compact || '₹ 22.4 L';
  }

  // 3. Render Doughnut Chart
  renderCategoryDoughnut(insights.category_breakdown);

  // 4. Render Top 5 Products Bar Chart
  renderTopProductsBar(insights.top_products);
}

function renderCategoryDoughnut(breakdown) {
  const canvas = document.getElementById('categoryDoughnutChart');
  const legendContainer = document.getElementById('doughnutLegendList');
  if (!canvas) return;

  if (DataMind.categoryChart) {
    DataMind.categoryChart.destroy();
  }

  const defaultBreakdown = [
    { name: 'Electronics', value: 42, percentage: 42, color: '#3b82f6' },
    { name: 'Clothing', value: 24, percentage: 24, color: '#10b981' },
    { name: 'Groceries', value: 18, percentage: 18, color: '#f59e0b' },
    { name: 'Others', value: 16, percentage: 16, color: '#8b5cf6' }
  ];

  const dataItems = (breakdown && breakdown.length > 0) ? breakdown : defaultBreakdown;

  const labels = dataItems.map(d => d.name);
  const values = dataItems.map(d => d.value);
  const colors = dataItems.map(d => d.color);

  // Update custom legend
  if (legendContainer) {
    legendContainer.innerHTML = '';
    dataItems.forEach(item => {
      const row = document.createElement('div');
      row.className = 'legend-item';
      row.innerHTML = `
        <span class="legend-dot" style="background-color: ${item.color}"></span>
        <span>${item.name} (${item.percentage}%)</span>
      `;
      legendContainer.appendChild(row);
    });
  }

  DataMind.categoryChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderWidth: 2,
        borderColor: '#ffffff',
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(context) {
              const item = dataItems[context.dataIndex];
              return ` ${item.name}: ${item.percentage}%`;
            }
          }
        }
      }
    }
  });
}

function renderTopProductsBar(topProducts) {
  const canvas = document.getElementById('topProductsBarChart');
  if (!canvas) return;

  if (DataMind.productsChart) {
    DataMind.productsChart.destroy();
  }

  const defaultProducts = [
    { name: 'Laptop', value: 500000 },
    { name: 'Phone', value: 380000 },
    { name: 'Headset', value: 270000 },
    { name: 'Watch', value: 190000 },
    { name: 'Tablet', value: 160000 }
  ];

  const items = (topProducts && topProducts.length > 0) ? topProducts : defaultProducts;

  const labels = items.map(p => p.name);
  const values = items.map(p => p.value);

  DataMind.productsChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Sales (₹)',
        data: values,
        backgroundColor: '#3b82f6',
        borderRadius: 4,
        barThickness: 28
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(context) {
              return ` Sales: ₹ ${context.parsed.y.toLocaleString('en-IN')}`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: 'Sales (₹)',
            color: '#64748b',
            font: { size: 11, weight: '500' }
          },
          ticks: {
            color: '#64748b',
            font: { size: 10 },
            callback: function(value) {
              return value >= 100000 ? (value / 100000) + ',00,000' : value;
            }
          },
          grid: { color: '#f1f5f9' }
        },
        x: {
          ticks: { color: '#475569', font: { size: 11 } },
          grid: { display: false }
        }
      }
    }
  });
}

// ==========================================
// ASK WITH AI LOGIC (Figure 5.9)
// ==========================================
function initMonthlyTrendChart() {
  const canvas = document.getElementById('monthlyTrendChart');
  if (!canvas || DataMind.monthlyTrendChart) return;

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May'];
  const values = [270000, 310000, 390000, 460000, 542000];

  DataMind.monthlyTrendChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: months,
      datasets: [{
        label: 'Sales (₹)',
        data: values,
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.15)',
        borderWidth: 2.5,
        pointBackgroundColor: '#38bdf8',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 1.5,
        pointRadius: 4.5,
        fill: true,
        tension: 0.35
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: 'Sales (₹)',
            color: '#64748b',
            font: { size: 11 }
          },
          ticks: {
            color: '#64748b',
            font: { size: 10 },
            callback: function(v) {
              return v >= 100000 ? (v / 100000) + ',00,000' : v;
            }
          },
          grid: { color: '#f1f5f9' }
        },
        x: {
          ticks: { color: '#475569', font: { size: 11 } },
          grid: { display: false }
        }
      }
    }
  });
}

function setupAskAiHandlers() {
  const form = document.getElementById('chatForm');
  const input = document.getElementById('chatInput');
  const messagesArea = document.getElementById('chatMessagesArea');

  if (!form || !input) return;

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    // Append user message bubble
    appendUserMessage(question);
    input.value = '';
    messagesArea.scrollTop = messagesArea.scrollHeight;

    // Send to backend API
    const datasetId = DataMind.activeDatasetId || 1;

    // Show AI loading bubble
    const loadingId = 'ai-loading-' + Date.now();
    appendAiLoadingBubble(loadingId);
    messagesArea.scrollTop = messagesArea.scrollHeight;

    fetch('/api/ai/ask/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': DataMind.csrfToken
      },
      body: JSON.stringify({
        dataset_id: datasetId,
        question: question
      })
    })
      .then(res => res.json())
      .then(data => {
        removeAiLoadingBubble(loadingId);
        if (data.success && data.analysis) {
          appendAiResponse(data.analysis);
        } else {
          appendAiError(data.error || 'Unable to process your query.');
        }
        messagesArea.scrollTop = messagesArea.scrollHeight;
      })
      .catch(err => {
        removeAiLoadingBubble(loadingId);
        appendAiError('Connection error while contacting AI engine.');
        messagesArea.scrollTop = messagesArea.scrollHeight;
      });
  });
}

function appendUserMessage(text) {
  const messagesArea = document.getElementById('chatMessagesArea');
  const row = document.createElement('div');
  row.className = 'chat-row-user';
  row.innerHTML = `
    <div class="bubble-user">${escapeHtml(text)}</div>
    <div class="user-avatar-tiny">
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
      </svg>
    </div>
  `;
  messagesArea.appendChild(row);
}

function appendAiLoadingBubble(id) {
  const messagesArea = document.getElementById('chatMessagesArea');
  const row = document.createElement('div');
  row.className = 'chat-row-ai';
  row.id = id;
  row.innerHTML = `
    <div class="ai-avatar-tiny">
      <div class="brand-bar" style="height:12px;width:3px;background:#2563eb;margin-right:2px;display:inline-block"></div>
      <div class="brand-bar" style="height:16px;width:3px;background:#2563eb;margin-right:2px;display:inline-block"></div>
      <div class="brand-bar" style="height:20px;width:3px;background:#2563eb;display:inline-block"></div>
    </div>
    <div class="ai-message-body">
      <div class="ai-text-para" style="color:#64748b;font-style:italic;">Analyzing dataset and synthesizing response...</div>
    </div>
  `;
  messagesArea.appendChild(row);
}

function removeAiLoadingBubble(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function appendAiError(msg) {
  const messagesArea = document.getElementById('chatMessagesArea');
  const row = document.createElement('div');
  row.className = 'chat-row-ai';
  row.innerHTML = `
    <div class="ai-avatar-tiny">
      <svg viewBox="0 0 24 24" fill="currentColor" style="width:16px;height:16px;">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
      </svg>
    </div>
    <div class="ai-message-body">
      <div class="ai-text-para" style="color:#dc2626;">${escapeHtml(msg)}</div>
    </div>
  `;
  messagesArea.appendChild(row);
}

function appendAiResponse(analysis) {
  const messagesArea = document.getElementById('chatMessagesArea');
  const chartId = 'ai-chart-' + Date.now();
  const row = document.createElement('div');
  row.className = 'chat-row-ai';

  let chartHtml = '';
  const hasChart = analysis.results && analysis.results.chart && analysis.results.chart.type !== 'none' && analysis.results.data && analysis.results.data.length > 0;

  if (hasChart) {
    chartHtml = `
      <div class="ai-embedded-chart-card">
        <div class="chart-inner-title">Analysis Visualization</div>
        <div class="ai-chart-canvas-box">
          <canvas id="${chartId}"></canvas>
        </div>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="ai-avatar-tiny">
      <div class="brand-bar" style="height:10px;width:3px;background:#2563eb;margin-right:2px;display:inline-block"></div>
      <div class="brand-bar" style="height:15px;width:3px;background:#2563eb;margin-right:2px;display:inline-block"></div>
      <div class="brand-bar" style="height:20px;width:3px;background:#2563eb;display:inline-block"></div>
    </div>
    <div class="ai-message-body">
      <div class="ai-text-para">${renderMarkdownSafe(analysis.insights)}</div>
      ${chartHtml}
    </div>
  `;
  messagesArea.appendChild(row);

  // Render dynamic chart if applicable
  if (hasChart) {
    setTimeout(() => {
      renderAiChart(chartId, analysis.results);
    }, 50);
  }
}

function renderAiChart(canvasId, results) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  if (!results || !results.data || !results.data.length) return;

  let chartType = results.chart?.type || 'bar';
  if (chartType === 'doughnut') chartType = 'pie';
  if (!['bar', 'line', 'pie'].includes(chartType)) chartType = 'bar';

  let labels = [];
  let values = [];
  let datasetLabel = 'Count';

  const data = results.data;
  const cols = results.chart?.columns || Object.keys(data[0] || {});

  // Case 1: Wide single-row multi-column aggregate (e.g. missing values or multiple metrics across columns)
  // ONLY use column names as labels if ALL values in the row are numeric or numeric strings (e.g. { total_revenue: 50000, total_profit: 20000 })
  // If the row contains any non-numeric string (e.g. { category: "Python Foundations", total_certificates: 39 }), it is a categorical key-value record, NOT a wide aggregate!
  const isWideMultiMetricRow = data.length === 1 && cols.length > 1 &&
    !('column' in data[0] && 'value' in data[0]) &&
    cols.every(c => {
      const val = data[0][c];
      if (val === null || val === undefined || val === '') return true;
      return typeof val === 'number' || (typeof val === 'string' && val.trim() !== '' && !isNaN(Number(val)));
    }) &&
    !cols.some(c => typeof data[0][c] === 'string' && isNaN(Number(data[0][c])));

  if (isWideMultiMetricRow) {
    const row = data[0];
    labels = cols.map(c => c.replace(/^missing_/i, '').replace(/_/g, ' '));
    values = cols.map(c => {
      const v = Number(row[c]);
      return isNaN(v) ? 0 : v;
    });
    datasetLabel = 'Observations';
  } else {
    // Case 2: Standard records (categorical label + numeric value)
    // Dynamic detection: find the string/categorical column for labels, and numeric column for values
    let labelCol = cols.find(c => {
      const v = data[0][c];
      return typeof v === 'string' && isNaN(Number(v));
    }) || cols[0];

    let valCol = cols.find(c => {
      if (c === labelCol) return false;
      const v = data[0][c];
      return typeof v === 'number' || (typeof v === 'string' && v.trim() !== '' && !isNaN(Number(v)));
    }) || (cols.length > 1 ? (cols[0] === labelCol ? cols[1] : cols[0]) : cols[0]);

    labels = data.map(d => {
      const raw = d[labelCol];
      if (raw === null || raw === undefined) return 'N/A';
      return String(raw).replace(/^missing_/i, '').replace(/_/g, ' ');
    });

    values = data.map(d => {
      const v = Number(d[valCol]);
      return isNaN(v) ? 0 : v;
    });

    datasetLabel = String(valCol).replace(/_/g, ' ');
  }

  // Ensure canvas has parent container and clear previous chart instance if any
  if (typeof Chart !== 'undefined' && Chart.getChart) {
    const existingChart = Chart.getChart(canvas);
    if (existingChart) existingChart.destroy();
  }

  new Chart(canvas, {
    type: chartType,
    data: {
      labels: labels,
      datasets: [{
        label: datasetLabel,
        data: values,
        backgroundColor: chartType === 'line' 
          ? 'rgba(56, 189, 248, 0.15)' 
          : chartType === 'pie'
            ? ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#64748b', '#0ea5e9']
            : '#3b82f6',
        borderColor: chartType === 'pie' ? '#ffffff' : '#2563eb',
        borderWidth: chartType === 'pie' ? 2 : 1.5,
        fill: chartType === 'line',
        tension: 0.25
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: chartType === 'pie' },
        tooltip: {
          callbacks: {
            label: function(context) {
              const val = context.raw;
              return `${context.dataset.label || 'Value'}: ${Number(val).toLocaleString()}`;
            }
          }
        }
      },
      scales: chartType === 'pie' ? {} : {
        y: { 
          beginAtZero: true, 
          grid: { color: '#f1f5f9' },
          ticks: { precision: 0 }
        },
        x: { 
          grid: { display: false },
          ticks: {
            maxRotation: 45,
            minRotation: 0,
            autoSkip: false
          }
        }
      }
    }
  });
}

// ==========================================
// SQL QUERY PAGE LOGIC
// ==========================================
function setupSqlHandlers() {
  const nlBtn = document.getElementById('btnNlToSql');
  const nlInput = document.getElementById('sqlNlInput');
  const sqlEditor = document.getElementById('sqlEditorArea');
  const runBtn = document.getElementById('btnRunSqlQuery');
  const resultsContainer = document.getElementById('sqlResultsBox');

  if (!runBtn || !sqlEditor) return;

  if (nlBtn && nlInput) {
    nlBtn.addEventListener('click', () => {
      const q = nlInput.value.trim();
      if (!q) return;
      nlBtn.disabled = true;
      nlBtn.textContent = 'Generating...';

      fetch('/api/analytics/sql/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': DataMind.csrfToken
        },
        body: JSON.stringify({
          dataset_id: DataMind.activeDatasetId,
          natural_language: q
        })
      })
        .then(res => res.json())
        .then(data => {
          nlBtn.disabled = false;
          nlBtn.textContent = 'Generate SQL';
          if (data.generated_sql) {
            sqlEditor.value = data.generated_sql;
          }
          if (data.results) {
            renderSqlResults(data.results);
          }
        })
        .catch(() => {
          nlBtn.disabled = false;
          nlBtn.textContent = 'Generate SQL';
        });
    });
  }

  runBtn.addEventListener('click', () => {
    const query = sqlEditor.value.trim();
    if (!query) return;

    runBtn.disabled = true;
    runBtn.textContent = 'Executing...';

    fetch('/api/analytics/sql/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': DataMind.csrfToken
      },
      body: JSON.stringify({
        dataset_id: DataMind.activeDatasetId,
        query: query
      })
    })
      .then(res => res.json())
      .then(data => {
        runBtn.disabled = false;
        runBtn.textContent = 'Run Query';
        if (data.results) {
          renderSqlResults(data.results);
        } else if (data.error) {
          resultsContainer.innerHTML = `<div style="color:#dc2626;padding:16px;">Error: ${escapeHtml(data.error)}</div>`;
        }
      })
      .catch(() => {
        runBtn.disabled = false;
        runBtn.textContent = 'Run Query';
      });
  });
}

function renderSqlResults(results) {
  const container = document.getElementById('sqlResultsBox');
  if (!container) return;

  if (!results.columns || results.columns.length === 0) {
    container.innerHTML = '<div style="padding:16px;color:#64748b;">No results returned.</div>';
    return;
  }

  let html = `
    <div style="padding:12px 18px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12.5px;color:#475569;display:flex;justify-content:space-between;">
      <span>Returned <strong>${results.count}</strong> rows</span>
      <span>Execution time: <strong>${results.execution_time_ms} ms</strong></span>
    </div>
    <div style="overflow-x:auto;">
      <table class="dm-table">
        <thead>
          <tr>
            ${results.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${results.rows.slice(0, 50).map(r => `
            <tr>
              ${results.columns.map(c => `<td>${escapeHtml(String(r[c] !== null && r[c] !== undefined ? r[c] : ''))}</td>`).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
  container.innerHTML = html;
}

// ==========================================
// DATASETS LIST & PREVIEW
// ==========================================
function loadDatasetsList() {
  fetch('/api/datasets/', {
    headers: { 'X-CSRFToken': DataMind.csrfToken }
  })
    .then(res => res.json())
    .then(data => {
      DataMind.datasets = data;
      renderDatasetsTable(data);
    })
    .catch(err => console.error('Failed to load datasets:', err));
}

function renderDatasetsTable(datasets) {
  const tbody = document.getElementById('datasetsTableBody');
  if (!tbody) return;

  if (!datasets || datasets.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:24px;color:#64748b;">No datasets uploaded yet.</td></tr>';
    return;
  }

  tbody.innerHTML = datasets.map((d, idx) => `
    <tr>
      <td class="td-num">${idx + 1}</td>
      <td style="font-weight:600;">${escapeHtml(d.name)}</td>
      <td><span class="type-pill">${escapeHtml(d.source_type.toUpperCase())}</span></td>
      <td>${Number(d.row_count).toLocaleString()}</td>
      <td>${d.column_count}</td>
      <td>${new Date(d.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
      <td>
        <button class="btn-view-outline" onclick="previewDataset(${d.id}, '${escapeHtml(d.name)}')">Preview</button>
        <button class="btn-view-outline" style="margin-left:6px;" onclick="selectDatasetForInsights(${d.id})">Insights</button>
      </td>
    </tr>
  `).join('');
}

function previewDataset(id, name) {
  const modal = document.getElementById('previewModal');
  const title = document.getElementById('modalDatasetTitle');
  const content = document.getElementById('modalPreviewContent');

  title.textContent = `Preview: ${name}`;
  content.innerHTML = '<div style="padding:20px;text-align:center;color:#64748b;">Loading dataset records...</div>';
  modal.classList.add('active');

  fetch(`/api/datasets/${id}/preview/`, {
    headers: { 'X-CSRFToken': DataMind.csrfToken }
  })
    .then(res => res.json())
    .then(data => {
      if (data.columns && data.rows) {
        content.innerHTML = `
          <table class="dm-table">
            <thead>
              <tr>${data.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>
            </thead>
            <tbody>
              ${data.rows.map(r => `
                <tr>${data.columns.map(c => `<td>${escapeHtml(String(r[c] !== null && r[c] !== undefined ? r[c] : ''))}</td>`).join('')}</tr>
              `).join('')}
            </tbody>
          </table>
        `;
      } else {
        content.innerHTML = '<div style="padding:20px;color:#dc2626;">Unable to preview dataset.</div>';
      }
    })
    .catch(() => {
      content.innerHTML = '<div style="padding:20px;color:#dc2626;">Error loading preview.</div>';
    });
}

function closePreviewModal() {
  const modal = document.getElementById('previewModal');
  if (modal) modal.classList.remove('active');
}

function selectDatasetForInsights(id) {
  DataMind.activeDatasetId = id;
  navigateTo('insights');
}

// ==========================================
// HISTORY LIST
// ==========================================
function loadHistoryList() {
  fetch('/api/analytics/history/', {
    headers: { 'X-CSRFToken': DataMind.csrfToken }
  })
    .then(res => res.json())
    .then(data => {
      if (data.success && data.history) {
        renderHistoryTable(data.history);
      }
    })
    .catch(err => console.error('Failed to load history:', err));
}

function renderHistoryTable(items) {
  const tbody = document.getElementById('historyTableBody');
  if (!tbody) return;

  if (!items || items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:#64748b;">No analysis history yet.</td></tr>';
    return;
  }

  tbody.innerHTML = items.map((item, idx) => `
    <tr>
      <td class="td-num">${idx + 1}</td>
      <td style="font-weight:600;">${escapeHtml(item.dataset_name)}</td>
      <td><span class="type-pill">${escapeHtml(item.dataset_type)}</span></td>
      <td>${escapeHtml(item.analysis_type)}</td>
      <td>${escapeHtml(item.date)}</td>
      <td><button class="btn-view-outline" onclick="navigateTo('insights')">View</button></td>
    </tr>
  `).join('');
}

// Helper: Escape HTML
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Helper: Secure Markdown Renderer for AI Responses
function renderMarkdownSafe(text) {
  if (!text) return '';
  let html = '';
  if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
    try {
      html = marked.parse(text);
    } catch (e) {
      console.warn('Marked parse failed, using fallback:', e);
      html = fallbackMarkdown(text);
    }
  } else {
    html = fallbackMarkdown(text);
  }
  return sanitizeHtml(html);
}

function sanitizeHtml(html) {
  const temp = document.createElement('div');
  temp.innerHTML = html;
  const dangerous = temp.querySelectorAll('script, style, iframe, object, embed');
  dangerous.forEach(el => el.remove());
  const allElements = temp.querySelectorAll('*');
  allElements.forEach(el => {
    Array.from(el.attributes).forEach(attr => {
      const name = attr.name.toLowerCase();
      const val = attr.value.trim().toLowerCase();
      if (name.startsWith('on') || val.startsWith('javascript:') || val.startsWith('data:text/html')) {
        el.removeAttribute(attr.name);
      }
    });
  });
  return temp.innerHTML;
}

function fallbackMarkdown(text) {
  let escaped = escapeHtml(text);
  // Headings
  escaped = escaped.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  escaped = escaped.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  escaped = escaped.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  // Bold & Italic
  escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Code block & inline code
  escaped = escaped.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Simple lists
  escaped = escaped.replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>');
  // Newlines
  escaped = escaped.replace(/\n\n/g, '<p></p>');
  escaped = escaped.replace(/\n/g, '<br>');
  return escaped;
}

// ==========================================
// APPLICATION INITIALIZATION
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
  const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
  DataMind.csrfToken = (csrfInput ? csrfInput.value : '') || getCookie('csrftoken') || '';

  // 1. Setup Navigation
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const sec = link.getAttribute('data-section');
      if (sec) navigateTo(sec);
    });
  });

  // Feature cards on home dashboard
  document.querySelectorAll('.feature-card').forEach(card => {
    card.addEventListener('click', (e) => {
      e.preventDefault();
      const sec = card.getAttribute('data-nav');
      if (sec) navigateTo(sec);
    });
  });

  // Popstate for browser back/forward
  window.addEventListener('popstate', (e) => {
    if (e.state && e.state.section) {
      navigateTo(e.state.section, false);
    }
  });

  // 2. User profile dropdown
  const userBtn = document.getElementById('userProfileBtn');
  const userMenu = document.getElementById('userDropdownMenu');
  if (userBtn && userMenu) {
    userBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      userMenu.classList.toggle('active');
    });
    document.addEventListener('click', () => {
      userMenu.classList.remove('active');
    });
  }

  // 3. Setup modules
  setupUploadHandlers();
  setupAskAiHandlers();
  setupSqlHandlers();

  // 4. Initial Section activation based on dataset or page
  const initialSection = document.body.getAttribute('data-initial-section') || 'home';
  navigateTo(initialSection, false);

  // Initialize charts in background
  initMonthlyTrendChart();
  loadInsightsData();
});
