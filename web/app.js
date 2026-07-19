const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || data.error) throw data.error || new Error(`HTTP ${response.status}`);
  return data;
}

function errorText(error) {
  if (typeof error === "string") return error;
  return `${error.code || "error"}: ${error.message || JSON.stringify(error)}`;
}

function setStatus(element, text, tone = "neutral") {
  element.textContent = text;
  element.className = `status ${tone}`;
}

function showTab(name) {
  $$(".tab").forEach((button) => {
    const active = button.dataset.tab === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $$(".view").forEach((view) => {
    const active = view.id === name;
    view.classList.toggle("active", active);
    view.hidden = !active;
  });
  history.replaceState(null, "", `#${name}`);
  if (name === "models" && !providers.length) loadModels();
}

$$('.tab').forEach((button) => button.addEventListener("click", () => showTab(button.dataset.tab)));

async function runVerify(mode) {
  const status = $("#verify-status");
  const output = $("#verify-output");
  setStatus(status, "RUNNING", "warn");
  output.textContent = "Inspecting source…";
  try {
    const source = $("#verify-source").value.trim();
    const body = mode === "scan" ? { path: source } : { source, tiers: [$("#verify-tier").value.trim()] };
    const result = await api(`/api/${mode}`, { method: "POST", body: JSON.stringify(body) });
    output.textContent = JSON.stringify(result, null, 2);
    const verdict = result.verdict || (result.findings.length ? "review" : "clean");
    setStatus(status, verdict.toUpperCase(), verdict === "install" || verdict === "clean" ? "good" : verdict === "reject" ? "bad" : "warn");
  } catch (error) {
    output.textContent = errorText(error);
    setStatus(status, "ERROR", "bad");
  }
}

$("#scan-button").addEventListener("click", () => runVerify("scan"));
$("#guard-button").addEventListener("click", () => runVerify("guard"));

$("#rewrite-gate-button").addEventListener("click", async () => {
  const result = $("#gate-result");
  result.textContent = "Evaluating…";
  try {
    const payload = {
      target_case: $("#target-case").value.trim(),
      before: JSON.parse($("#before-map").value),
      after: JSON.parse($("#after-map").value),
    };
    const decision = await api("/api/improve/gate", { method: "POST", body: JSON.stringify(payload) });
    result.textContent = `${decision.accepted ? "ACCEPT" : "REJECT"} — ${decision.reason}`;
    result.style.color = decision.accepted ? "var(--green)" : "var(--red)";
  } catch (error) {
    result.textContent = errorText(error);
    result.style.color = "var(--red)";
  }
});

let currentRun = null;
let stream = null;
let arenaRows = [];

function renderArenaRow(row) {
  const empty = $("#arena-rows .empty");
  if (empty) empty.parentElement.remove();
  const tr = document.createElement("tr");
  const values = [row.tier, row.trial, row.without_skill, row.with_skill, row.uplift, row.status];
  values.forEach((value, index) => {
    const td = document.createElement("td");
    td.textContent = typeof value === "number" ? (index >= 2 ? value.toFixed(2) : value) : value ?? "n/a";
    tr.appendChild(td);
  });
  $("#arena-rows").appendChild(tr);
  arenaRows.push(row);
}

function renderSummary(report) {
  const summary = report.summary;
  const format = (value, signed = false) => value == null ? "n/a" : `${signed && value >= 0 ? "+" : ""}${value.toFixed(2)}`;
  $("#metric-without").textContent = format(summary.without_skill);
  $("#metric-with").textContent = format(summary.with_skill);
  $("#metric-uplift").textContent = format(summary.uplift, true);
  $("#metric-coverage").textContent = `${summary.coverage.completed_rows} / ${summary.coverage.expected_rows}`;
}

function listenToRun(runId) {
  stream = new EventSource(`/api/runs/${runId}/events`);
  stream.addEventListener("model_row", (event) => renderArenaRow(JSON.parse(event.data).row));
  stream.addEventListener("progress", (event) => {
    const value = JSON.parse(event.data);
    $("#metric-coverage").textContent = `${value.completed} / ${value.total}`;
  });
  ["run_completed", "run_cancelled"].forEach((type) => stream.addEventListener(type, (event) => {
    const value = JSON.parse(event.data);
    renderSummary(value.report);
    setStatus($("#arena-status"), type === "run_completed" ? "COMPLETE" : "CANCELLED", type === "run_completed" ? "good" : "warn");
    $("#cancel-button").disabled = true;
    stream.close();
  }));
  stream.addEventListener("run_failed", (event) => {
    setStatus($("#arena-status"), "FAILED", "bad");
    $("#cancel-button").disabled = true;
    $("#arena-rows").innerHTML = `<tr><td colspan="6" class="empty"></td></tr>`;
    $("#arena-rows .empty").textContent = errorText(JSON.parse(event.data).error);
    stream.close();
  });
}

$("#bench-button").addEventListener("click", async () => {
  if (stream) stream.close();
  arenaRows = [];
  $("#arena-rows").innerHTML = '<tr><td colspan="6" class="empty">Starting run…</td></tr>';
  setStatus($("#arena-status"), "RUNNING", "warn");
  try {
    const payload = {
      task: $("#arena-task").value.trim(),
      skill: $("#arena-skill").value.trim(),
      tiers: [$("#arena-tier").value.trim()],
      trials: Number($("#arena-trials").value),
    };
    const result = await api("/api/bench", { method: "POST", body: JSON.stringify(payload) });
    currentRun = result.run_id;
    $("#cancel-button").disabled = false;
    listenToRun(currentRun);
  } catch (error) {
    setStatus($("#arena-status"), "ERROR", "bad");
    $("#arena-rows .empty").textContent = errorText(error);
  }
});

$("#cancel-button").addEventListener("click", async () => {
  if (currentRun) await api(`/api/runs/${currentRun}/cancel`, { method: "POST", body: "{}" });
});

$("#arena-task-preset").addEventListener("change", (event) => {
  $("#arena-task").value = event.target.value;
});

let providers = [];
let models = [];

function selectTier(tier) {
  const option = [...$("#model-select").options].find((row) => row.value === tier);
  if (option) $("#model-select").value = tier;
}

function renderModelPicker(preset) {
  const previous = $("#model-select").value;
  const options = models.map((row) => {
    const option = document.createElement("option");
    option.value = row.tier;
    option.textContent = `${row.model} · ${row.provider}`;
    return option;
  });
  $("#model-select").replaceChildren(...options);
  selectTier(models.some((row) => row.tier === previous) ? previous : preset);
  const selected = $("#model-select").value;
  if (selected) {
    if ($("#verify-tier").value === "ollama-cloud:") $("#verify-tier").value = selected;
    if ($("#arena-tier").value === "ollama-cloud:") $("#arena-tier").value = selected;
  }
}

function renderProviders(filter = "") {
  const query = filter.toLowerCase();
  const rows = providers.filter((row) => `${row.provider} ${row.base_url} ${(row.models || []).join(" ")}`.toLowerCase().includes(query));
  $("#provider-grid").replaceChildren(...rows.map((row) => {
    const article = document.createElement("article");
    article.className = `provider ${row.configured ? "" : "off"}`;
    const title = document.createElement("h2"); title.textContent = row.provider;
    const status = document.createElement("div"); status.className = "provider-status";
    status.textContent = row.configured ? `READY · key source: ${row.key_source}` : "NEEDS CONFIGURATION";
    const code = document.createElement("code"); code.textContent = row.base_url || "built-in deterministic fixture";
    const modelList = document.createElement("div"); modelList.className = "model-list";
    (row.models || []).filter((model) => model.toLowerCase().includes(query) || row.provider.toLowerCase().includes(query)).forEach((model) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = model;
      button.addEventListener("click", () => selectTier(`${row.provider}:${model}`));
      modelList.appendChild(button);
    });
    if (row.last_error) {
      const error = document.createElement("small"); error.className = "provider-error"; error.textContent = errorText(row.last_error);
      modelList.appendChild(error);
    }
    article.append(title, status, code, modelList);
    return article;
  }));
}

async function loadModels(refresh = false) {
  try {
    const data = await api(`/api/models${refresh ? "?refresh=1" : ""}`);
    providers = data.providers;
    models = data.models;
    renderModelPicker(data.preset);
    renderProviders($("#model-filter").value);
  } catch (error) {
    $("#provider-grid").textContent = errorText(error);
  }
}

$("#model-filter").addEventListener("input", (event) => renderProviders(event.target.value));
$("#refresh-models").addEventListener("click", () => loadModels(true));
$("#use-verify-model").addEventListener("click", () => {
  $("#verify-tier").value = $("#model-select").value;
  showTab("verify");
});
$("#use-arena-model").addEventListener("click", () => {
  $("#arena-tier").value = $("#model-select").value;
  showTab("arena");
});

showTab(location.hash.slice(1) || "verify");
loadModels();
