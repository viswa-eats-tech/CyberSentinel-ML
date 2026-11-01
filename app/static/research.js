const resultEndpoint = "/research/feature-outages/results";
const statusEndpoint = "/research/feature-outages/status";
const runEndpoint = "/research/feature-outages/run";
const byId = (id) => document.getElementById(id);
let currentResults = null;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function number(value, digits = 1) {
  if (value == null || value === "") return "—";
  return Number.isFinite(Number(value)) ? Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits }) : "—";
}

function percent(value) {
  if (value == null || value === "") return "—";
  return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(1)}%` : "—";
}

function adjustedP(row) {
  return row.fdr_q_value ?? row.sign_test_p_value ?? row.randomization_p_value;
}

function renderSummary(results) {
  const clean = results.scenarios.find((row) => row.scenario === "clean") ?? results.scenarios[0];
  const seeds = results.protocol.training_seed_count ?? 1;
  const tiles = [
    ["Reviewed per scenario", number(clean.reviewed_rows, 0)],
    ["Errors caught by uncertainty", number(clean.uncertainty_errors_caught)],
    ["Random review average", number(clean.random_mean_errors_caught)],
    ["Model seeds", number(seeds, 0)],
  ];
  byId("summary-cards").innerHTML = tiles.map(([label, value]) => `<article class="summary-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join("");
}

function renderScenarioRows(results) {
  byId("scenario-rows").innerHTML = results.scenarios.map((row) => {
    const lift = Number(row.errors_caught_lift_vs_random_mean);
    const consistency = row.seeds_beating_random == null ? "—" : `${row.seeds_beating_random}/${row.training_seed_count}`;
    return `<tr>
      <td class="scenario-name">${escapeHtml(row.scenario === "clean" ? "All features present" : row.scenario.replaceAll("_", " "))}</td>
      <td>${percent(row.review_rate ?? results.protocol.review_budget_target)}</td>
      <td>${number(row.uncertainty_errors_caught)}</td>
      <td>${number(row.random_mean_errors_caught)}</td>
      <td class="${lift >= 0 ? "positive" : "negative"}">${lift >= 0 ? "+" : ""}${number(lift)}</td>
      <td>${consistency}</td>
      <td>${percent(adjustedP(row))}</td>
    </tr>`;
  }).join("");
}

function renderCategoryRows(results, scenario) {
  const rows = results.attack_category_results.filter((row) => row.scenario === scenario)
    .sort((left, right) => Number(right.errors_caught_lift_vs_random_mean) - Number(left.errors_caught_lift_vs_random_mean));
  byId("category-rows").innerHTML = rows.map((row) => {
    const lift = Number(row.errors_caught_lift_vs_random_mean);
    const consistency = row.seeds_beating_random == null ? "—" : `${row.seeds_beating_random}/${row.training_seed_count}`;
    return `<tr>
      <td class="scenario-name">${escapeHtml(row.attack_category)}</td>
      <td>${number(row.rows, 0)}</td><td>${number(row.baseline_errors)}</td>
      <td>${number(row.uncertainty_errors_caught)}</td><td>${number(row.random_mean_errors_caught)}</td>
      <td class="${lift >= 0 ? "positive" : "negative"}">${lift >= 0 ? "+" : ""}${number(lift)}</td>
      <td>${percent(row.uncertainty_error_capture_rate)}</td><td>${consistency}</td>
      <td>${percent(adjustedP(row))}</td>
    </tr>`;
  }).join("") || '<tr><td colspan="9">No category rows found in this saved report.</td></tr>';
}

function renderResults(results) {
  currentResults = results;
  byId("empty-state").hidden = true;
  byId("results").hidden = false;
  renderSummary(results);
  renderScenarioRows(results);
  const protocol = results.protocol ?? {};
  const seedCount = protocol.training_seed_count ?? 1;
  byId("report-meta").textContent = `${number(protocol.official_test_rows, 0)} test flows · ${seedCount} training seed${seedCount === 1 ? "" : "s"} · ${protocol.random_review_repeats ?? 0} random draws per seed`;
  const selector = byId("scenario-select");
  const previous = selector.value;
  selector.innerHTML = results.scenarios.map((row) => `<option value="${escapeHtml(row.scenario)}">${escapeHtml(row.scenario === "clean" ? "All features present" : row.scenario.replaceAll("_", " "))}</option>`).join("");
  if (results.scenarios.some((row) => row.scenario === previous)) selector.value = previous;
  renderCategoryRows(results, selector.value);
}

async function loadResults() {
  const response = await fetch(resultEndpoint, { cache: "no-store" });
  const payload = await response.json();
  if (payload.available && payload.results?.scenarios?.length) {
    renderResults(payload.results);
    const seedCount = payload.results.protocol.training_seed_count ?? 1;
    if (seedCount === 1) setStatus("Showing the saved one-seed report. Run the study to create the multi-seed analysis.");
    else setStatus(`Showing the latest saved study (${seedCount} training seeds).`);
  } else {
    byId("empty-state").hidden = false;
    byId("results").hidden = true;
    setStatus(payload.message || "No saved experiment results yet.");
  }
}

function setStatus(message, isError = false) {
  const status = byId("run-status");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

async function getRunStatus() {
  const response = await fetch(statusEndpoint, { cache: "no-store" });
  if (!response.ok) throw new Error("Could not check experiment status.");
  return response.json();
}

async function pollUntilFinished() {
  while (true) {
    const state = await getRunStatus();
    setStatus(state.message || "The experiment is running…", state.status === "failed");
    if (state.status !== "running") {
      byId("run-button").disabled = false;
      if (state.status === "complete") await loadResults();
      if (state.status === "failed") setStatus(state.message, true);
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 2500));
  }
}

byId("scenario-select").addEventListener("change", (event) => {
  if (currentResults) renderCategoryRows(currentResults, event.target.value);
});

byId("run-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("run-button");
  button.disabled = true;
  setStatus("Starting the experiment. Model fitting can take several minutes…");
  try {
    const response = await fetch(runEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        review_budget: Number(byId("budget").value),
        training_seeds: Number(byId("seeds").value),
        random_repeats: Number(byId("repeats").value),
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.message || "Could not start the experiment.");
    await pollUntilFinished();
  } catch (error) {
    button.disabled = false;
    setStatus(error.message, true);
  }
});

loadResults().catch((error) => setStatus(error.message, true));
