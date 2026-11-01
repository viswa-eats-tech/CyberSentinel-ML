const fieldGroups = [
  {
    title: "Flow basics",
    keys: ["dur", "proto", "service", "state"],
  },
  {
    title: "Packets and bytes",
    keys: ["spkts", "dpkts", "sbytes", "dbytes", "rate", "sload", "dload"],
  },
  {
    title: "Packet timing",
    keys: ["sinpkt", "dinpkt", "sjit", "djit"],
  },
  {
    title: "Packet characteristics",
    keys: ["sttl", "dttl", "sloss", "dloss", "smean", "dmean"],
  },
  {
    title: "TCP connection details",
    keys: ["swin", "stcpb", "dtcpb", "dwin", "tcprtt", "synack", "ackdat"],
  },
  {
    title: "Connection history",
    keys: [
      "ct_srv_src",
      "ct_state_ttl",
      "ct_dst_ltm",
      "ct_src_dport_ltm",
      "ct_dst_sport_ltm",
      "ct_dst_src_ltm",
      "ct_src_ltm",
      "ct_srv_dst",
    ],
  },
  {
    title: "Application signals",
    keys: [
      "trans_depth",
      "response_body_len",
      "is_ftp_login",
      "ct_ftp_cmd",
      "ct_flw_http_mthd",
      "is_sm_ips_ports",
    ],
  },
];

const friendlyNames = {
  dur: "Flow duration",
  proto: "Protocol",
  service: "Service",
  state: "Connection state",
  spkts: "Source packets",
  dpkts: "Destination packets",
  sbytes: "Source bytes",
  dbytes: "Destination bytes",
  rate: "Flow rate",
  sttl: "Source TTL",
  dttl: "Destination TTL",
  sload: "Source load",
  dload: "Destination load",
  sloss: "Source packet loss",
  dloss: "Destination packet loss",
  sinpkt: "Source packet interval",
  dinpkt: "Destination packet interval",
  sjit: "Source jitter",
  djit: "Destination jitter",
  swin: "Source TCP window",
  stcpb: "Source TCP base",
  dtcpb: "Destination TCP base",
  dwin: "Destination TCP window",
  tcprtt: "TCP round trip time",
  synack: "SYN to ACK time",
  ackdat: "ACK data time",
  smean: "Mean source packet size",
  dmean: "Mean destination packet size",
  trans_depth: "Transaction depth",
  response_body_len: "Response body length",
  ct_srv_src: "Service connections from source",
  ct_state_ttl: "State and TTL count",
  ct_dst_ltm: "Recent destination connections",
  ct_src_dport_ltm: "Recent source and destination-port connections",
  ct_dst_sport_ltm: "Recent destination and source-port connections",
  ct_dst_src_ltm: "Recent destination/source connections",
  is_ftp_login: "FTP login indicator",
  ct_ftp_cmd: "FTP command count",
  ct_flw_http_mthd: "HTTP method count",
  ct_src_ltm: "Recent source connections",
  ct_srv_dst: "Recent service/destination connections",
  is_sm_ips_ports: "Same IP and port indicator",
};

const form = document.querySelector("#flow-form");
const fieldContainer = document.querySelector("#flow-fields");
const resultContent = document.querySelector("#result-content");
const errorBox = document.querySelector("#error-box");
const batchRecords = document.querySelector("#batch-records");
let sampleRecord = null;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });
}

function buildFields(record) {
  fieldContainer.replaceChildren();

  fieldGroups.forEach((group, index) => {
    const details = document.createElement("details");
    details.className = "field-group";
    details.open = index === 0;

    const summary = document.createElement("summary");
    summary.textContent = group.title;
    details.append(summary);

    const grid = document.createElement("div");
    grid.className = "field-grid";

    group.keys.forEach((key) => {
      const value = record[key];
      const control = document.createElement("div");
      control.className = "field-control";

      const label = document.createElement("label");
      label.htmlFor = `field-${key}`;
      label.innerHTML = `<span>${escapeHtml(friendlyNames[key])}</span><code>${escapeHtml(key)}</code>`;

      const input = document.createElement("input");
      input.id = `field-${key}`;
      input.name = key;
      input.required = true;
      input.value = value ?? "";
      if (typeof value === "number") {
        input.type = "number";
        input.min = "0";
        input.step = Number.isInteger(value) ? "1" : "any";
      } else {
        input.type = "text";
        input.maxLength = 40;
      }

      control.append(label, input);
      grid.append(control);
    });

    details.append(grid);
    fieldContainer.append(details);
  });
}

function readForm() {
  const record = {};
  for (const [key, value] of new FormData(form).entries()) {
    const sampleValue = sampleRecord[key];
    record[key] = typeof sampleValue === "number" ? Number(value) : value;
  }
  return record;
}

async function requestJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body.message || body.detail?.[0]?.msg || `Request failed (${response.status}).`;
    throw new Error(message);
  }
  return body;
}

function formatPercent(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function getDecisionCopy(decision) {
  if (decision === "attack") {
    return {
      title: "Potential attack pattern",
      description: "The model score met or exceeded its attack threshold.",
    };
  }
  if (decision === "review") {
    return {
      title: "Needs a closer look",
      description: "This flow was among the least certain records in its batch.",
    };
  }
  return {
    title: "Predicted normal",
    description: "The model score was below its attack threshold.",
  };
}

function renderSingleResult(result) {
  const decision = result.prediction_label;
  const copy = getDecisionCopy(decision);
  const score = Number(result.attack_probability);
  const threshold = Number(result.threshold);
  const tone = decision === "attack" ? "attack" : "normal";

  resultContent.innerHTML = `
    <article class="result-card ${tone}">
      <span class="decision-label ${tone}"><span class="decision-icon"></span>${escapeHtml(decision === "attack" ? "ATTACK" : "NORMAL")}</span>
      <h3 class="result-title">${escapeHtml(copy.title)}</h3>
      <p class="result-explanation">${escapeHtml(copy.description)}</p>
      <div class="score-row"><span>Model attack score</span><strong class="score-value">${formatPercent(score)}</strong></div>
      <div class="meter" role="img" aria-label="Attack score ${formatPercent(score)}"><div class="meter-fill ${score >= threshold ? "high" : ""}" style="width:${Math.max(0, Math.min(100, score * 100))}%"></div></div>
      <div class="threshold-note"><span>Below threshold: normal</span><span>Threshold ${formatPercent(threshold)}</span></div>
      <div class="result-details">
        <div class="detail-row"><span>Model</span><strong>${escapeHtml(result.model_name)}</strong></div>
        <div class="detail-row"><span>Prediction label</span><strong>${escapeHtml(result.prediction_label)}</strong></div>
      </div>
    </article>`;
  document.querySelector(".result-heading h2").textContent = "Flow checked";
  document.querySelector(".result-heading .muted").textContent = "Here’s what the model returned.";
}

function renderBatchResult(result) {
  const reviewed = result.items.filter((item) => item.decision === "review").length;
  const attacks = result.items.filter((item) => item.decision === "attack").length;
  const normals = result.items.filter((item) => item.decision === "normal").length;
  const items = result.items
    .map((item, index) => {
      const label = item.decision === "review" ? "REVIEW" : item.decision.toUpperCase();
      const missing = item.missing_features ?? [];
      const missingText = missing.length
        ? ` · missing: ${missing.slice(0, 3).map((key) => friendlyNames[key] || key).join(", ")}${missing.length > 3 ? ` +${missing.length - 3} more` : ""}`
        : "";
      return `
        <div class="batch-item">
          <span class="batch-index">${String(index + 1).padStart(2, "0")}</span>
          <div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(item.prediction_label)} prediction${escapeHtml(missingText)}</small></div>
          <span class="batch-score">${formatPercent(item.attack_probability)}<br />attack score</span>
        </div>`;
    })
    .join("");

  resultContent.innerHTML = `
    <div class="batch-summary">
      <div class="summary-stat"><span>Sent to review</span><strong>${reviewed}</strong></div>
      <div class="summary-stat"><span>Attack labels</span><strong>${attacks}</strong></div>
      <div class="summary-stat"><span>Normal labels</span><strong>${normals}</strong></div>
    </div>
    <p class="muted" style="margin:0 0 10px">Model: ${escapeHtml(result.items[0]?.model_name || "selected model")} · ${result.items.length} records · ${formatPercent(result.review_rate)} reviewed · threshold ${formatPercent(result.threshold)}</p>
    <div class="batch-list">${items}</div>`;
  document.querySelector(".result-heading h2").textContent = "Batch reviewed";
  document.querySelector(".result-heading .muted").textContent = "Each row shows the model label and attack score. REVIEW means it needs human attention.";
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function clearError() {
  errorBox.textContent = "";
  errorBox.hidden = true;
}

function setBusy(button, busy, busyLabel) {
  if (!button.dataset.label) button.dataset.label = button.textContent.trim();
  button.disabled = busy;
  button.textContent = busy ? busyLabel : button.dataset.label;
}

async function loadSample() {
  const response = await fetch("/sample-input");
  if (!response.ok) throw new Error("Could not load the sample flow.");
  sampleRecord = await response.json();
  buildFields(sampleRecord);
  document.querySelector("#single-json").value = JSON.stringify(sampleRecord, null, 2);
  batchRecords.value = JSON.stringify([sampleRecord], null, 2);
}

async function fetchRandomExamples(url) {
  const response = await fetch(url);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Could not generate random flow examples.");
  }
  return body;
}

async function updateServiceStatus() {
  const status = document.querySelector("#service-status");
  try {
    const response = await fetch("/health");
    const health = await response.json();
    if (health.model_loaded) {
      status.className = "service-status status-ready";
      status.innerHTML = '<span class="status-dot"></span>Model ready';
    } else {
      status.className = "service-status status-degraded";
      status.innerHTML = '<span class="status-dot"></span>Model unavailable';
    }
  } catch {
    status.className = "service-status status-degraded";
    status.innerHTML = '<span class="status-dot"></span>Service unavailable';
  }
}

async function loadAvailableModels() {
  const select = document.querySelector("#model-choice");
  const help = document.querySelector("#model-choice-help");
  try {
    const response = await fetch("/models", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error("Could not load the trained-model list.");
    const availableModels = payload.models.filter((model) => model.available);
    if (!availableModels.length) {
      select.innerHTML = '<option value="">No trained models available</option>';
      help.textContent = "Train a model before making predictions.";
      return;
    }
    select.innerHTML = availableModels.map((model) =>
      `<option value="${escapeHtml(model.name)}">${escapeHtml(model.display_name)}${model.is_default ? " (default)" : ""}</option>`,
    ).join("");
    select.value = availableModels.some((model) => model.name === payload.default_model)
      ? payload.default_model
      : availableModels[0].name;
    help.textContent = "Choose a trained model. Additional model files load only when selected.";
  } catch (error) {
    select.innerHTML = '<option value="random_forest">Random Forest</option>';
    help.textContent = error.message;
  }
}

function setMode(mode) {
  const isSingle = mode === "single";
  document.querySelector("#single-view").hidden = !isSingle;
  document.querySelector("#batch-view").hidden = isSingle;
  document.querySelector("#single-mode").classList.toggle("active", isSingle);
  document.querySelector("#single-mode").setAttribute("aria-selected", String(isSingle));
  document.querySelector("#batch-mode").classList.toggle("active", !isSingle);
  document.querySelector("#batch-mode").setAttribute("aria-selected", String(!isSingle));
  document.querySelector("#input-title").textContent = isSingle ? "Flow details" : "Batch of flows";
  document.querySelector("#input-description").textContent = isSingle
    ? "The example is preloaded. You can change any value before checking it."
    : "Paste a JSON array of flow records, then choose how many should be reviewed.";
  clearError();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  const button = form.querySelector('button[type="submit"]');
  setBusy(button, true, "Checking flow…");
  try {
    const result = await requestJson(
      `/predict?model_name=${encodeURIComponent(document.querySelector("#model-choice").value)}`,
      readForm(),
    );
    renderSingleResult(result);
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(button, false);
  }
});

document.querySelector("#check-batch").addEventListener("click", async (event) => {
  clearError();
  let records;
  try {
    records = JSON.parse(batchRecords.value);
    if (!Array.isArray(records)) throw new Error("Enter a JSON array, for example: [{ ... }, { ... }].");
    if (!records.length) throw new Error("Add at least one flow record.");
  } catch (error) {
    showError(`Could not read the batch: ${error.message}`);
    return;
  }

  const button = event.currentTarget;
  setBusy(button, true, "Reviewing batch…");
  try {
    const result = await requestJson(
      `/predict/batch?model_name=${encodeURIComponent(document.querySelector("#model-choice").value)}`,
      {
      records,
      review_budget: Number(document.querySelector("#review-budget").value),
      },
    );
    renderBatchResult(result);
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(button, false);
  }
});

document.querySelector("#single-mode").addEventListener("click", () => setMode("single"));
document.querySelector("#batch-mode").addEventListener("click", () => setMode("batch"));
document.querySelector("#load-example").addEventListener("click", async () => {
  clearError();
  try {
    await loadSample();
    resultContent.innerHTML = '<div class="empty-state" aria-hidden="true"><div class="empty-icon">↗</div><span>Example loaded. Check it when ready.</span></div>';
  } catch (error) {
    showError(error.message);
  }
});
document.querySelector("#generate-random-flow").addEventListener("click", async (event) => {
  clearError();
  const button = event.currentTarget;
  setBusy(button, true, "Generating flow…");
  try {
    sampleRecord = await fetchRandomExamples("/sample-random-input");
    buildFields(sampleRecord);
    document.querySelector("#single-json").value = JSON.stringify(sampleRecord, null, 2);
    batchRecords.value = JSON.stringify([sampleRecord], null, 2);
    resultContent.innerHTML = '<div class="empty-state" aria-hidden="true"><div class="empty-icon">↻</div><span>Random flow is ready. Check it when you are ready.</span></div>';
    document.querySelector(".result-heading h2").textContent = "Random flow generated";
    document.querySelector(".result-heading .muted").textContent = "A synthetic flow was generated within the feature constraints.";
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(button, false);
  }
});
document.querySelector("#apply-single-json").addEventListener("click", () => {
  clearError();
  try {
    const record = JSON.parse(document.querySelector("#single-json").value);
    if (!record || Array.isArray(record) || typeof record !== "object") {
      throw new Error("Paste one JSON object, not an array.");
    }
    const expectedKeys = fieldGroups.flatMap((group) => group.keys);
    const missingKeys = expectedKeys.filter((key) => !(key in record));
    if (missingKeys.length) {
      throw new Error(`This record is missing ${missingKeys.length} required field(s): ${missingKeys.slice(0, 4).join(", ")}${missingKeys.length > 4 ? ", …" : ""}.`);
    }
    buildFields(record);
    document.querySelector("#flow-fields").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showError(`Could not use this JSON: ${error.message}`);
  }
});
document.querySelector("#load-demo-batch").addEventListener("click", () => {
  clearError();
  fetch("/sample-batch-input")
    .then((response) => {
      if (!response.ok) throw new Error("Could not load the varied demo records.");
      return response.json();
    })
    .then((records) => {
      batchRecords.value = JSON.stringify(records, null, 2);
    })
    .catch((error) => showError(error.message));
});
document.querySelector("#generate-random-batch").addEventListener("click", async (event) => {
  clearError();
  const button = event.currentTarget;
  setBusy(button, true, "Generating flows…");
  try {
    const records = await fetchRandomExamples("/sample-random-batch?count=10");
    batchRecords.value = JSON.stringify(records, null, 2);
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(button, false);
  }
});

loadSample().catch((error) => showError(error.message));
loadAvailableModels();
updateServiceStatus();
