import { $, api, clearError, renderError, setStatus } from "/ui.js";


let currentReport = null;


function selection() {
  return {
    author: document.querySelector('input[name="improve-author-tier"]:checked')?.value || "",
    gates: [...document.querySelectorAll('input[name="improve-gate-tier"]:checked')].map((input) => input.value),
  };
}


function syncContext() {
  const { author, gates } = selection();
  $("#trap-model-context").textContent = `Breaker: ${author || "none"} · Gate: ${gates.join(", ") || "none"}`;
}


function textReason(value) {
  if (!value) return "No reason reported.";
  return typeof value === "string" ? value : JSON.stringify(value);
}


function modelRows(rows) {
  return rows.map((model) => {
    const row = document.createElement("tr");
    const rate = model.pass_rate == null ? "ungraded" : `${model.passed}/${model.total}`;
    const reason = model.last_error
      ? textReason(model.last_error)
      : model.passed === model.total ? "all completed traps passed" : `${model.total - model.passed} deterministic failure(s)`;
    [model.tier, rate, `${model.completed}/${model.total}`, reason].forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (index === 3 && model.last_error) {
        cell.className = "table-error";
        cell.title = reason;
      }
      row.appendChild(cell);
    });
    return row;
  });
}


function resultBlock(result, check) {
  const block = document.createElement("div");
  block.className = `trap-model-result ${result.passed === true ? "passed" : result.passed === false ? "failed" : "ungraded"}`;
  const heading = document.createElement("strong");
  heading.textContent = `${result.tier} · ${result.passed === true ? "PASS" : result.passed === false ? "FAIL" : "UNGRADED"}`;
  const reason = document.createElement("p");
  reason.textContent = result.passed === false
    ? `${check.kind} expected ${JSON.stringify(check.value)}; ${textReason(result.reason)}`
    : textReason(result.reason);
  const actual = document.createElement("pre");
  actual.textContent = `actual » ${result.actual == null ? "(no output)" : result.actual === "" ? "(empty string)" : result.actual}`;
  block.append(heading, reason, actual);
  return block;
}


function candidateCard(candidate, freezeAvailable) {
  const card = document.createElement("article");
  card.className = `trap-card ${candidate.tears_now ? "tears" : "holds"}`;
  const header = document.createElement("div");
  header.className = "trap-card-heading";
  const title = document.createElement("strong");
  title.textContent = `${candidate.id} · ${candidate.tears_now ? "TEARS NOW" : "HOLDS ACROSS GATES"}`;
  header.appendChild(title);
  if (candidate.tears_now && freezeAvailable) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "trap-freeze-select";
    input.value = candidate.id;
    label.append(input, document.createTextNode(" select to freeze"));
    header.appendChild(label);
  }
  const hypothesis = document.createElement("p");
  hypothesis.className = "trap-hypothesis";
  hypothesis.textContent = `breaker hypothesis (review it): ${candidate.rationale}`;
  const input = document.createElement("pre");
  input.textContent = `input » ${candidate.input === "" ? "(empty string)" : candidate.input}`;
  const check = document.createElement("code");
  check.textContent = `check » ${candidate.check.kind}: ${JSON.stringify(candidate.check.value)}`;
  const results = document.createElement("div");
  results.className = "trap-result-list";
  results.append(...candidate.results.map((result) => resultBlock(result, candidate.check)));
  card.append(header, hypothesis, input, check, results);
  return card;
}


function renderRejected(rows) {
  if (!rows.length) {
    $("#trap-rejected").replaceChildren();
    return;
  }
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  const list = document.createElement("ul");
  summary.textContent = `${rows.length} breaker candidate(s) rejected before execution`;
  rows.forEach((row) => {
    const item = document.createElement("li");
    item.textContent = `${row.candidate}: ${row.reason}`;
    list.appendChild(item);
  });
  details.append(summary, list);
  $("#trap-rejected").replaceChildren(details);
}


function renderUsage(usage) {
  const rows = Object.entries(usage || {});
  $("#trap-usage").textContent = rows.length
    ? rows.map(([tier, value]) => `${tier}: ${value.calls} calls · ${value.input_tokens + value.output_tokens || "tokens n/a"}`).join(" · ")
    : "Provider usage was not reported.";
}


function updateFreezeState() {
  const selected = [...document.querySelectorAll(".trap-freeze-select:checked")];
  const local = Boolean(currentReport?.freeze_available);
  const reviewed = $("#trap-reviewed").checked;
  $("#trap-freeze-button").disabled = !local || !reviewed || !selected.length;
  $("#trap-freeze-note").textContent = !currentReport
    ? "Select one or more failing trap cards after a run."
    : !local ? currentReport.freeze_reason
      : `${selected.length} failing trap(s) selected · review confirmation ${reviewed ? "set" : "required"}.`;
}


function renderReport(report) {
  currentReport = report;
  $("#trap-checked").textContent = report.candidates_checked;
  $("#trap-failing").textContent = report.failing_candidates;
  $("#trap-failures").textContent = report.model_trap_failures;
  $("#trap-model-rows").replaceChildren(...modelRows(report.per_model));
  $("#trap-cards").replaceChildren(...report.candidates.map((candidate) => candidateCard(candidate, report.freeze_available)));
  renderRejected(report.rejected_candidates || []);
  renderUsage(report.usage);
  $("#trap-reviewed").checked = false;
  $("#trap-file-truth").querySelector("code").textContent = report.freeze_available
    ? "unchanged · dry evidence · select and review traps to append"
    : `unchanged · ${report.freeze_reason}`;
  setStatus($("#trap-status"), report.failing_candidates ? "BREAKS FOUND" : "NO BREAK FOUND", report.failing_candidates ? "warn" : "good");
  updateFreezeState();
}


async function runTraps() {
  clearError($("#trap-error"));
  const button = $("#trap-run-button");
  button.disabled = true;
  setStatus($("#trap-status"), "RUNNING", "neutral");
  try {
    const { author, gates } = selection();
    if (!author || !gates.length) {
      throw { code: "traps.models", kind: "validation", message: "Choose one Author / Breaker and at least one Gate model above.", context: {} };
    }
    const report = await api("/api/traps", {
      method: "POST",
      body: JSON.stringify({
        source: $("#improve-source").value.trim(),
        breaker_tier: author,
        gate_tiers: gates,
        max_traps: Number($("#trap-max").value),
      }),
    });
    renderReport(report);
  } catch (failure) {
    setStatus($("#trap-status"), "ERROR", "bad");
    renderError($("#trap-error"), failure);
  } finally {
    button.disabled = false;
  }
}


async function freezeSelected() {
  clearError($("#trap-error"));
  const ids = new Set([...document.querySelectorAll(".trap-freeze-select:checked")].map((input) => input.value));
  const candidates = currentReport.candidates.filter((candidate) => ids.has(candidate.id));
  try {
    const result = await api("/api/traps/freeze", {
      method: "POST",
      body: JSON.stringify({ source: currentReport.source, candidates, reviewed: $("#trap-reviewed").checked }),
    });
    $("#trap-file-truth").querySelector("code").textContent = `${result.added.length ? "changed" : "unchanged"} · ${result.path} · +${result.added.length} append-only trap(s) · ${result.skipped.length} skipped`;
    document.querySelectorAll(".trap-freeze-select:checked").forEach((input) => {
      input.checked = false;
      input.disabled = true;
      input.parentElement.lastChild.textContent = " frozen this run";
    });
    $("#trap-reviewed").checked = false;
    setStatus($("#trap-status"), result.added.length ? "FROZEN" : "UNCHANGED", result.added.length ? "good" : "warn");
    updateFreezeState();
  } catch (failure) {
    setStatus($("#trap-status"), "ERROR", "bad");
    renderError($("#trap-error"), failure);
  }
}


export function initTraps() {
  $("#show-traps-button").addEventListener("click", () => {
    syncContext();
    $("#trap-workbench").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("#trap-run-button").addEventListener("click", runTraps);
  $("#trap-freeze-button").addEventListener("click", freezeSelected);
  $("#trap-reviewed").addEventListener("change", updateFreezeState);
  $("#trap-cards").addEventListener("change", updateFreezeState);
  window.addEventListener("clawreinforce:improve-selection", syncContext);
  syncContext();
}
