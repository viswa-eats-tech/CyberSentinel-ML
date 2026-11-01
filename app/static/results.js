const modelInfo = {
  random_forest: { label: "Random Forest", color: "#c2632b" },
  bagging: { label: "Bagging Classifier", color: "#6658a6" },
  gradient_boosting: { label: "Gradient Boosting", color: "#2879a8" },
};
const metricInfo = [
  ["accuracy", "Accuracy"],
  ["precision_attack", "Attack precision"],
  ["recall_attack", "Attack recall"],
  ["f1_attack", "Attack F1 score"],
  ["roc_auc", "ROC-AUC"],
];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function formatNumber(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(1)}%` : "—";
}

function renderSummary(report) {
  const featureCount = report.numeric_features.length + report.categorical_features.length;
  const values = [
    ["Training flows", formatNumber(report.train_rows)],
    ["Test flows", formatNumber(report.test_rows)],
    ["Input features", formatNumber(featureCount)],
    ["Decision threshold", formatPercent(report.decision_threshold)],
  ];
  document.querySelector("#run-summary").innerHTML = values.map(([label, value]) => `
    <article class="summary-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>
  `).join("");
  const date = new Date(report.generated_at);
  document.querySelector("#generated-at").textContent = `Saved evaluation report${Number.isNaN(date.valueOf()) ? "" : ` · generated ${date.toLocaleString()}`}`;
}

function renderLegend(models) {
  document.querySelector("#model-legend").innerHTML = Object.keys(models).map((key) => {
    const info = modelInfo[key] ?? { label: key, color: "#536770" };
    return `<span class="legend-item"><span class="legend-swatch" style="background:${info.color}"></span>${escapeHtml(info.label)}</span>`;
  }).join("");
}

function renderMetricChart(models) {
  document.querySelector("#metric-chart").innerHTML = metricInfo.map(([key, label]) => `
    <div class="metric-row">
      <div class="metric-name">${escapeHtml(label)}</div>
      <div class="metric-bars">${Object.entries(models).map(([modelKey, metrics]) => {
        const info = modelInfo[modelKey] ?? { label: modelKey, color: "#536770" };
        const value = Number(metrics[key]);
        const width = Number.isFinite(value) ? Math.max(0, Math.min(100, value * 100)) : 0;
        return `<div class="metric-bar-line" aria-label="${escapeHtml(info.label)} ${formatPercent(value)}">
          <div class="bar-track"><div class="bar" style="width:${width}%;background:${info.color}"></div></div>
          <span class="bar-value">${formatPercent(value)}</span>
        </div>`;
      }).join("")}</div>
    </div>
  `).join("");
}

function renderErrorChart(models) {
  const maxCount = Math.max(1, ...Object.values(models).flatMap((metrics) => [
    metrics.confusion_matrix.false_positive,
    metrics.confusion_matrix.false_negative,
  ]));
  document.querySelector("#error-chart").innerHTML = Object.entries(models).map(([modelKey, metrics]) => {
    const info = modelInfo[modelKey] ?? { label: modelKey, color: "#536770" };
    const errors = [
      ["False alarms", metrics.confusion_matrix.false_positive, "#c2632b"],
      ["Missed attacks", metrics.confusion_matrix.false_negative, "#ad3434"],
    ];
    return `<article class="error-group"><h3>${escapeHtml(info.label)}</h3>${errors.map(([label, count, color]) => `
      <div class="error-bar-row"><span>${label}</span><div class="error-track"><div class="error-fill" style="width:${Math.max(0, count / maxCount * 100)}%;background:${color}"></div></div><strong>${formatNumber(count)}</strong></div>
    `).join("")}</article>`;
  }).join("");
}

function matrixCell(value, label, max, correct) {
  const strength = max ? Math.max(0, Math.min(1, value / max)).toFixed(3) : "0";
  return `<td class="${correct ? "correct" : "incorrect"}" style="--strength:${strength}" aria-label="${label}: ${formatNumber(value)}"><strong>${formatNumber(value)}</strong><span>${label}</span></td>`;
}

function renderMatrices(models) {
  document.querySelector("#confusion-matrices").innerHTML = Object.entries(models).map(([modelKey, metrics]) => {
    const info = modelInfo[modelKey] ?? { label: modelKey };
    const matrix = metrics.confusion_matrix;
    const max = Math.max(matrix.true_negative, matrix.false_positive, matrix.false_negative, matrix.true_positive);
    return `<article class="model-card">
      <h3>${escapeHtml(info.label)}</h3><p class="model-subtitle">Decision threshold ${formatPercent(metrics.threshold)}</p>
      <div class="matrix-wrap"><table class="matrix">
        <thead><tr><th></th><th colspan="2">Predicted label</th></tr><tr><th>Actual label</th><th>Normal</th><th>Attack</th></tr></thead>
        <tbody>
          <tr><th>Normal</th>${matrixCell(matrix.true_negative, "Correct normal", max, true)}${matrixCell(matrix.false_positive, "False alarm", max, false)}</tr>
          <tr><th>Attack</th>${matrixCell(matrix.false_negative, "Missed attack", max, false)}${matrixCell(matrix.true_positive, "Detected attack", max, true)}</tr>
        </tbody>
      </table></div>
      <p class="matrix-note">Rows are actual labels; columns are model predictions. Green cells are correct predictions.</p>
    </article>`;
  }).join("");
}

function renderClassReports(models) {
  const classes = ["normal", "attack", "macro avg", "weighted avg"];
  document.querySelector("#classification-reports").innerHTML = Object.entries(models).map(([modelKey, metrics]) => {
    const info = modelInfo[modelKey] ?? { label: modelKey };
    const report = metrics.classification_report ?? {};
    const rows = classes.map((className) => {
      const row = report[className] ?? {};
      return `<tr><td>${escapeHtml(className)}</td><td>${formatPercent(row.precision)}</td><td>${formatPercent(row.recall)}</td><td>${formatPercent(row["f1-score"])}</td><td>${formatNumber(row.support ?? 0)}</td></tr>`;
    }).join("");
    return `<article class="model-card"><h3>${escapeHtml(info.label)}</h3><p class="model-subtitle">Threshold ${formatPercent(metrics.threshold)} · accuracy ${formatPercent(metrics.accuracy)} · ROC-AUC ${formatPercent(metrics.roc_auc)}</p>
      <div class="report-table-wrap"><table class="report-table"><thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th><th>Flows</th></tr></thead><tbody>${rows}</tbody></table></div>
    </article>`;
  }).join("");
}

async function loadTrainingResults() {
  const errorBox = document.querySelector("#load-error");
  try {
    const response = await fetch("/results/training-data", { cache: "no-store" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Could not load the saved training report.");
    if (!body.models || !Object.keys(body.models).length) throw new Error("The report does not contain any model results yet.");
    renderSummary(body);
    renderLegend(body.models);
    renderMetricChart(body.models);
    renderErrorChart(body.models);
    renderMatrices(body.models);
    renderClassReports(body.models);
    document.querySelector("#results-content").hidden = false;
  } catch (error) {
    errorBox.textContent = `${error.message} Run model training to create reports/training_results.json.`;
    errorBox.hidden = false;
  }
}

loadTrainingResults();
