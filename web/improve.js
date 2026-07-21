import { $, api, clearError, renderError, setStatus } from "/ui.js";
import { beginHardenEvidence, initHardenEvidence, renderHardenEvidence } from "/harden-evidence.js";
import { loadModelCatalog } from "/model-catalog.js";
import { renderModelChoices, selectionSummary } from "/model-picker.js";
import { createRunProgress } from "/run-progress.js";


let modelCatalog = [];
let selectedGateTiers = new Set();
let authorTier = "";
let authorSelectionTouched = false;
let gateSelectionTouched = false;
let currentRun = null;
let stream = null;

const improveProgress = createRunProgress({
  phase: $("#improve-live-phase"),
  bar: $("#improve-progress-bar"),
  count: $("#improve-progress-count"),
  elapsed: $("#improve-elapsed"),
  eta: $("#improve-eta"),
});


function setPhase(name, state, message) {
  const item = $(`#improve-phases [data-phase="${name}"]`);
  item.className = state;
  item.querySelector("small").textContent = message;
}


function runningPhases() {
  setPhase("measure", "active", "Grading every declared golden case…");
  setPhase("propose", "pending", "Starts only when a case fails.");
  setPhase("remeasure", "pending", "Each proposal is graded again.");
  setPhase("gate", "pending", "Only target-green, zero-regression bodies survive.");
}


function renderPhases(result) {
  const attempts = result.attempts || [];
  setPhase("measure", "complete", `${Object.keys(result.before).length} golden case(s) graded.`);
  if (!attempts.length) {
    setPhase("propose", "skipped", "Skipped: the original body was already green.");
    setPhase("remeasure", "skipped", "Skipped: no candidate was needed.");
    setPhase("gate", "complete", "Kept the original body; no rewrite was needed.");
    return;
  }
  setPhase("propose", "complete", `${attempts.length} model proposal(s) received.`);
  setPhase("remeasure", "complete", `${attempts.length} candidate body/bodies re-graded.`);
  setPhase("gate", result.accepted ? "complete" : "rejected", result.reason);
}


function passRate(cases) {
  const values = Object.values(cases);
  return values.length ? values.filter(Boolean).length / values.length : null;
}


function renderModelLine(result) {
  const rows = result.per_model || [{ tier: result.tier, before: result.before, after: result.after }];
  $("#improve-model-lines").replaceChildren(...rows.map((row) => {
    const before = row.before_pass_rate ?? passRate(row.before);
    const after = row.after_pass_rate ?? passRate(row.after);
    const line = document.createElement("div");
    line.className = "model-score-line";
    const model = document.createElement("code");
    model.textContent = row.tier;
    const scores = document.createElement("strong");
    scores.textContent = before == null || after == null ? "ungraded → ungraded" : `${(before * 100).toFixed(0)}% → ${(after * 100).toFixed(0)}%`;
    const label = document.createElement("small");
    label.textContent = "gate execution · baseline → accepted best body";
    line.append(model, scores, label);
    return line;
  }));
}


function renderUsage(result) {
  const rows = Object.entries(result.usage || {});
  $("#improve-usage").textContent = rows.length
    ? rows.map(([tier, value]) => `${tier}: ${value.calls} calls · ${value.input_tokens || value.output_tokens ? `${value.input_tokens}+${value.output_tokens} tokens` : "tokens n/a"}`).join(" · ")
    : "Provider token usage was not reported.";
  $("#improve-measurement-note").textContent = result.measurement_note || "";
}


function gateItem(gate) {
  const item = document.createElement("li");
  item.innerHTML = `<span>IMPLEMENTED</span><div><strong></strong><p></p></div>`;
  item.querySelector("strong").textContent = gate.name;
  item.querySelector("p").textContent = gate.explanation;
  return item;
}


function caseRow(caseId, before, after) {
  const row = document.createElement("tr");
  const value = (passed) => `<span class="${passed ? "good-text" : "warn-text"}">${passed ? "PASS" : "FAIL"}</span>`;
  row.innerHTML = `<td></td><td>${value(before)}</td><td>${value(after)}</td>`;
  row.firstElementChild.textContent = caseId;
  return row;
}


function renderReport(result) {
  $("#improve-decision").textContent = result.reason;
  $("#improve-run-context").textContent = `Author: ${result.author_tier || result.tier} · Gate: ${(result.gate_tiers || [result.tier]).join(", ")}`;
  $("#improve-apply-state").textContent = result.applied
    ? "Accepted body written to SKILL.md."
    : result.dry_run ? "Dry-run only; SKILL.md was not changed." : "No accepted body was available to write.";
  const ids = [...new Set([...Object.keys(result.before), ...Object.keys(result.after)])];
  renderPhases(result);
  renderModelLine(result);
  renderUsage(result);
  $("#improve-cases").replaceChildren(...ids.map((id) => caseRow(id, result.before[id], result.after[id])));
  renderHardenEvidence(result);
  const tone = result.status === "completed" || result.status === "unchanged" ? "good" : result.status === "partial" ? "warn" : "bad";
  setStatus($("#improve-status"), result.status.toUpperCase(), tone);
}


function improveFeed(type, message, tone = "") {
  const empty = $("#improve-live-feed .empty-state");
  if (empty) empty.remove();
  const item = document.createElement("li");
  item.className = tone;
  const time = document.createElement("time");
  time.textContent = new Date().toLocaleTimeString();
  const event = document.createElement("strong");
  event.textContent = type.replaceAll("_", " ");
  const detail = document.createElement("span");
  detail.textContent = message;
  item.append(time, event, detail);
  const feed = $("#improve-live-feed");
  feed.appendChild(item);
  feed.scrollTop = feed.scrollHeight;
}


function listenImprove(runId) {
  stream = new EventSource(`/api/runs/${runId}/events`);
  stream.addEventListener("run_started", (event) => {
    const value = JSON.parse(event.data);
    improveFeed("run_started", `${value.case_count} case(s) × ${value.gate_tiers.length} gate model(s); up to ${value.max_rewrites} rewrite(s)`);
  });
  stream.addEventListener("phase_started", (event) => {
    const value = JSON.parse(event.data);
    const attempt = value.attempt ? ` · attempt ${value.attempt}` : "";
    improveProgress.beginPhase(`${value.phase}${attempt}`, value.total);
    setPhase(value.phase, "active", `${value.completed} / ${value.total} real work units complete.`);
    improveFeed("phase_started", `${value.phase}${attempt} · ${value.total} unit(s)`);
  });
  stream.addEventListener("measurement", (event) => {
    const value = JSON.parse(event.data);
    improveProgress.update(value.completed, value.total, `${value.phase}${value.attempt ? ` · attempt ${value.attempt}` : ""}`);
    setPhase(value.phase, "active", `${value.completed} / ${value.total} model × case checks complete.`);
    improveFeed("measurement", `${value.tier} · ${value.case_id} · ${value.passed ? "PASS" : "FAIL"}`, value.passed ? "good" : "warn");
  });
  stream.addEventListener("proposal_received", (event) => {
    const value = JSON.parse(event.data);
    improveProgress.update(1, 1, `proposal · attempt ${value.attempt}`);
    $("#improve-decision").textContent = `Proposal ${value.attempt} received for ${value.target_case}; deterministic re-measurement is next.`;
    improveFeed("proposal_received", `attempt ${value.attempt} · target ${value.target_case} · ${value.verified_examples} verified example(s)`);
  });
  stream.addEventListener("phase_completed", (event) => {
    const value = JSON.parse(event.data);
    improveProgress.update(value.total, value.total, `${value.phase} complete`);
    setPhase(value.phase, "complete", `${value.total} / ${value.total} real work units complete.`);
  });
  stream.addEventListener("phase_skipped", (event) => {
    const value = JSON.parse(event.data);
    setPhase(value.phase, "skipped", `Skipped: ${value.reason}.`);
    improveFeed("phase_skipped", `${value.phase} · ${value.reason}`);
  });
  stream.addEventListener("gate_decision", (event) => {
    const value = JSON.parse(event.data);
    improveProgress.beginPhase(`gate · attempt ${value.attempt}`, 1);
    improveProgress.update(1, 1);
    setPhase("gate", value.accepted || value.attempt === 0 ? "complete" : "rejected", value.reason);
    improveFeed("gate_decision", `${value.accepted ? "ACCEPT" : value.attempt === 0 ? "KEEP ORIGINAL" : "REJECT"} · ${value.reason}`, value.accepted || value.attempt === 0 ? "good" : "warn");
  });
  stream.addEventListener("run_completed", (event) => {
    const result = JSON.parse(event.data).result;
    improveProgress.finish(result.status === "unchanged" ? "Original already green" : `Run ${result.status}`);
    improveFeed("run_completed", result.reason, result.accepted || result.status === "unchanged" ? "good" : "warn");
    renderReport(result);
    $("#improve-button").disabled = false;
    stream.close();
  });
  stream.addEventListener("run_failed", (event) => {
    const failure = JSON.parse(event.data).error;
    improveProgress.fail("Run failed");
    setStatus($("#improve-status"), "FAILED", "bad");
    improveFeed("run_failed", JSON.stringify(failure), "bad");
    renderError($("#improve-error"), failure);
    $("#improve-button").disabled = false;
    stream.close();
  });
  stream.onerror = () => {
    if ($("#improve-status").textContent !== "RUNNING") return;
    const failure = {
      code: "improve.stream_disconnected",
      kind: "unavailable",
      message: "The live evidence stream disconnected before a terminal event.",
      context: { run_id: runId },
    };
    improveProgress.fail("Stream disconnected");
    setStatus($("#improve-status"), "DISCONNECTED", "bad");
    renderError($("#improve-error"), failure);
    $("#improve-button").disabled = false;
  };
}


async function runImprove() {
  if (stream) stream.close();
  clearError($("#improve-error"));
  const button = $("#improve-button");
  button.disabled = true;
  runningPhases();
  beginHardenEvidence();
  $("#improve-live-feed").innerHTML = '<li class="empty-state">Run accepted. Connecting to the live evidence stream…</li>';
  improveProgress.start("Waiting for the first server event");
  setStatus($("#improve-status"), "RUNNING", "neutral");
  try {
    if (!selectedGateTiers.size) {
      throw { code: "improve.gate_tiers", kind: "validation", message: "Choose at least one gate model.", context: {} };
    }
    if (!authorTier) {
      throw { code: "improve.author_tier", kind: "validation", message: "Choose one author model.", context: {} };
    }
    const result = await api("/api/improve/runs", {
      method: "POST",
      body: JSON.stringify({
        source: $("#improve-source").value.trim(),
        author_tier: authorTier,
        gate_tiers: [...selectedGateTiers],
        strategy: $("#improve-strategy").value,
        max_rewrites: Number($("#improve-max").value),
        apply: $("#improve-apply").checked,
      }),
    });
    currentRun = result.run_id;
    listenImprove(currentRun);
  } catch (failure) {
    improveProgress.fail("Run did not start");
    setStatus($("#improve-status"), "ERROR", "bad");
    renderError($("#improve-error"), failure);
    button.disabled = false;
  }
}


function renderModelPickers(models, preferred = "") {
  modelCatalog = models;
  const available = new Set(models.map((model) => model.tier));
  const initial = (!authorSelectionTouched && available.has(preferred) ? preferred : "") || (available.has(authorTier) ? authorTier : "")
    || models.find((model) => model.tier === "fixture:upper-if-skilled")?.tier || models[0]?.tier || "";
  authorTier = initial;
  selectedGateTiers = gateSelectionTouched
    ? new Set([...selectedGateTiers].filter((tier) => models.some((model) => model.tier === tier)))
    : new Set(authorTier ? [authorTier] : []);
  if (!selectedGateTiers.size && authorTier && !gateSelectionTouched) selectedGateTiers.add(authorTier);
  const filter = $("#improve-model-filter").value;
  renderModelChoices($("#improve-author-tiers"), models, new Set(authorTier ? [authorTier] : []), {
    filter,
    multiple: false,
    name: "improve-author-tier",
    onChange: (next) => {
      authorSelectionTouched = true;
      authorTier = [...next][0] || "";
      renderModelPickers(modelCatalog);
    },
  });
  renderModelChoices($("#improve-gate-tiers"), models, selectedGateTiers, {
    filter,
    name: "improve-gate-tier",
    onChange: (next) => {
      gateSelectionTouched = true;
      selectedGateTiers = next;
      renderModelPickers(modelCatalog);
    },
  });
  const authorKind = authorTier.startsWith("fixture:") ? "test fixture" : "LLM";
  $("#improve-selection-note").textContent = `Author: ${authorTier || "none"} (${authorKind}) · Gate: ${selectionSummary(modelCatalog, selectedGateTiers)} · calls scale with models × cases × proposals.`;
  setStatus($("#improve-model-status"), authorTier && selectedGateTiers.size ? `${1 + selectedGateTiers.size} ROLES SET` : "CHOOSE MODELS", authorTier && selectedGateTiers.size ? "good" : "warn");
  window.dispatchEvent(new CustomEvent("clawreinforce:improve-selection"));
}


function loadOptions(skills, models, preset) {
  const skillPicker = $("#improve-skill");
  skillPicker.replaceChildren(...skills.map((skill) => new Option(`${skill.kind === "flagship" ? "FLAGSHIP" : "FIXTURE"} · ${skill.category} · ${skill.name} — ${skill.case_count} cases`, skill.source)));
  const preferred = skills.find((skill) => skill.name === "improvable-uppercase-skill") || skills[0];
  if (preferred) skillPicker.value = preferred.source;
  $("#improve-source").value = preferred?.source || "";
  skillPicker.addEventListener("change", () => { $("#improve-source").value = skillPicker.value; });
  renderModelPickers(models, preset);
}


export async function initImprove() {
  initHardenEvidence();
  $("#improve-button").addEventListener("click", runImprove);
  $("#improve-model-filter").addEventListener("input", () => renderModelPickers(modelCatalog));
  window.addEventListener("clawreinforce:models", (event) => renderModelPickers(event.detail.models || [], event.detail.preset));
  window.addEventListener("clawreinforce:model-use", (event) => {
    if (event.detail.target !== "improve") return;
    const tier = event.detail.tier;
    renderModelPickers(modelCatalog, tier);
  });
  try {
    const [status, skillData, modelData] = await Promise.all([api("/api/improve/status"), api("/api/skills"), loadModelCatalog()]);
    $("#improve-explanation").textContent = status.explanation;
    $("#improve-gates").replaceChildren(...status.gates.map(gateItem));
    setStatus($("#improve-capability"), status.orchestrator.available ? "LOOP READY" : "UNAVAILABLE", status.orchestrator.available ? "good" : "warn");
    loadOptions(skillData.skills, modelData.models, modelData.preset);
  } catch (failure) {
    $("#improve-explanation").textContent = "Improve could not load its API state. Start the server, then reload this tab.";
    setStatus($("#improve-capability"), "ERROR", "bad");
    renderError($("#improve-error"), failure);
  }
}
