const REFRESH_INTERVAL_MS = 5000;
let lastBatchId = null;

const statusBadge = document.getElementById("statusBadge");
const generatedAt = document.getElementById("generatedAt");
const batchId = document.getElementById("batchId");
const rowsCount = document.getElementById("rowsCount");
const alertsCount = document.getElementById("alertsCount");
const latencyMs = document.getElementById("latencyMs");
const trainingMetrics = document.getElementById("trainingMetrics");
const evaluationTable = document.getElementById("evaluationTable");
const riskAccountsTable = document.getElementById("riskAccountsTable");
const dashboardImage = document.getElementById("dashboardImage");
const dashboardImageFrame = document.getElementById("dashboardImageFrame");
const dashboardImageState = document.getElementById("dashboardImageState");
const refreshImageButton = document.getElementById("refreshImageButton");

function numberFormat(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return new Intl.NumberFormat("vi-VN", options).format(value);
}

function currencyFormat(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return numberFormat(value, { maximumFractionDigits: 2 });
}

function percentFormat(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return numberFormat(value, { minimumFractionDigits: 4, maximumFractionDigits: 4 });
}

function timeFormat(value) {
  if (!value) {
    return "--";
  }
  try {
    return new Date(value).toLocaleString("vi-VN");
  } catch {
    return "--";
  }
}

function applyFlash(element) {
  element.classList.remove("flash");
  void element.offsetWidth;
  element.classList.add("flash");
}

function updateStatus(status) {
  const values = Object.values(status);
  const readyCount = values.filter(Boolean).length;

  statusBadge.classList.remove("status-ready", "status-partial", "status-waiting");
  if (readyCount === values.length && status.has_latest_batch) {
    statusBadge.textContent = "Sẵn sàng demo";
    statusBadge.classList.add("status-ready");
    return;
  }

  if (readyCount >= 2) {
    statusBadge.textContent = "Đang cập nhật dữ liệu";
    statusBadge.classList.add("status-partial");
    return;
  }

  statusBadge.textContent = "Đang đợi dữ liệu";
  statusBadge.classList.add("status-waiting");
}

function updateSummary(summary) {
  const isNewBatch = summary.batch_id !== null && summary.batch_id !== lastBatchId;
  batchId.textContent = summary.batch_id ?? "--";
  rowsCount.textContent = numberFormat(summary.rows);
  alertsCount.textContent = numberFormat(summary.alerts);
  latencyMs.textContent = summary.latency_ms !== null && summary.latency_ms !== undefined
    ? `${numberFormat(summary.latency_ms)} ms`
    : "--";

  if (isNewBatch) {
    [batchId, rowsCount, alertsCount, latencyMs].forEach(applyFlash);
    lastBatchId = summary.batch_id;
  }
}

function updateTraining(training) {
  const cards = [
    ["AUC ROC", percentFormat(training.auc_roc)],
    ["AUC PR", percentFormat(training.auc_pr)],
    ["Accuracy", percentFormat(training.accuracy)],
    ["Precision", percentFormat(training.precision)],
    ["Recall", percentFormat(training.recall)],
    ["F1", percentFormat(training.f1)],
  ];

  trainingMetrics.innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="stat-card">
          <p class="stat-label">${label}</p>
          <p class="stat-value">${value}</p>
        </article>
      `,
    )
    .join("");
}

function updateEvaluation(rows) {
  if (!rows.length) {
    evaluationTable.innerHTML = `
      <tr>
        <td colspan="4">Chưa có dữ liệu đánh giá mô hình.</td>
      </tr>
    `;
    return;
  }

  evaluationTable.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${row.model}</td>
          <td>${percentFormat(row.precision)}</td>
          <td>${percentFormat(row.recall)}</td>
          <td>${percentFormat(row.f1)}</td>
        </tr>
      `,
    )
    .join("");
}

function scoreClass(value) {
  if (value === null || value === undefined) {
    return "score-chip-normal";
  }
  if (value >= 0.9) {
    return "score-chip-critical";
  }
  if (value >= 0.75) {
    return "score-chip-strong";
  }
  return "score-chip-normal";
}

function rowClass(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (value >= 0.9) {
    return "risk-critical";
  }
  if (value >= 0.75) {
    return "risk-strong";
  }
  return "";
}

function updateRiskAccounts(rows) {
  if (!rows.length) {
    riskAccountsTable.innerHTML = `
      <tr>
        <td colspan="4">Chưa có danh sách tài khoản rủi ro.</td>
      </tr>
    `;
    return;
  }

  riskAccountsTable.innerHTML = rows
    .map(
      (row) => `
        <tr class="${rowClass(row.avg_score)}">
          <td>${row.account}</td>
          <td>${numberFormat(row.alert_count)}</td>
          <td>${currencyFormat(row.total_amount)}</td>
          <td><span class="score-chip ${scoreClass(row.avg_score)}">${percentFormat(row.avg_score)}</span></td>
        </tr>
      `,
    )
    .join("");
}

function updateDashboardImage(url) {
  if (!url) {
    dashboardImageFrame.classList.add("hidden");
    dashboardImageState.classList.remove("hidden");
    return;
  }

  dashboardImageFrame.classList.remove("hidden");
  dashboardImageState.classList.add("hidden");
  dashboardImage.src = `${url}?ts=${Date.now()}`;
}

async function fetchDashboard() {
  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    generatedAt.textContent = `Lần cập nhật: ${timeFormat(payload.generated_at)}`;
    updateStatus(payload.status);
    updateSummary(payload.summary);
    updateTraining(payload.training);
    updateEvaluation(payload.evaluation || []);
    updateRiskAccounts(payload.top_risk_accounts || []);
    updateDashboardImage(payload.assets?.dashboard_image_url || null);
  } catch (error) {
    statusBadge.textContent = "Không tải được dashboard";
    statusBadge.classList.remove("status-ready", "status-partial");
    statusBadge.classList.add("status-waiting");
    generatedAt.textContent = "Lần cập nhật: lỗi kết nối";
    console.error(error);
  }
}

refreshImageButton.addEventListener("click", () => {
  if (dashboardImage.src) {
    dashboardImage.src = `${dashboardImage.src.split("?")[0]}?ts=${Date.now()}`;
  }
});

fetchDashboard();
setInterval(fetchDashboard, REFRESH_INTERVAL_MS);
