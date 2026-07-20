import { $, api, clearError, renderError, setStatus } from "/ui.js";
import { renderModelChoices } from "/model-picker.js";


let modelCatalog = [];
let selectedGateTiers = new Set();
let authorTier = "";


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


function attemptItem(attempt) {
  const item = document.createElement("li");
  const heading = document.createElement("strong");
  heading.textContent = `#${attempt.number} · ${attempt.target_case} · ${attempt.accepted ? "ACCEPT" : "REJECT"}`;
  const reason = document.createElement("p");
  reason.textContent = attempt.reason;
  const detail = document.createElement("small");
  const regressions = attempt.regressions.length ? attempt.regressions.join(", ") : "none";
  detail.textContent = `regressions: ${regressions} · verified examples: ${attempt.verified_examples.length}`;
  item.className = attempt.accepted ? "accepted" : "rejected";
  item.append(heading, reason, detail);
  return item;
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
  $("#improve-diff").textContent = result.diff || "No accepted body change. Inspect the gate reasons below.";
  if (result.attempts.length) {
    $("#improve-attempts").replaceChildren(...result.attempts.map(attemptItem));
  } else {
    $("#improve-attempts").innerHTML = '<li class="empty-state">No rewrite was needed because every golden case was already green.</li>';
  }
  const tone = result.status === "completed" || result.status === "unchanged" ? "good" : result.status === "partial" ? "warn" : "bad";
  setStatus($("#improve-status"), result.status.toUpperCase(), tone);
}


async function runImprove() {
  clearError($("#improve-error"));
  const button = $("#improve-button");
  button.disabled = true;
  runningPhases();
  setStatus($("#improve-status"), "RUNNING", "neutral");
  try {
    if (!selectedGateTiers.size) {
      throw { code: "improve.gate_tiers", kind: "validation", message: "Choose at least one gate model.", context: {} };
    }
    if (!authorTier) {
      throw { code: "improve.author_tier", kind: "validation", message: "Choose one author model.", context: {} };
    }
    const result = await api("/api/improve", {
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
    renderReport(result);
  } catch (failure) {
    setStatus($("#improve-status"), "ERROR", "bad");
    renderError($("#improve-error"), failure);
  } finally {
    button.disabled = false;
  }
}


function renderModelPickers(models, preferred = "") {
  modelCatalog = models;
  const available = new Set(models.map((model) => model.tier));
  const initial = preferred || (available.has(authorTier) ? authorTier : "")
    || models.find((model) => model.tier === "fixture:upper-if-skilled")?.tier || models[0]?.tier || "";
  authorTier = initial;
  selectedGateTiers = new Set([...selectedGateTiers].filter((tier) => models.some((model) => model.tier === tier)));
  if (!selectedGateTiers.size && authorTier) selectedGateTiers.add(authorTier);
  const filter = $("#improve-model-filter").value;
  renderModelChoices($("#improve-author-tiers"), models, new Set(authorTier ? [authorTier] : []), {
    filter,
    multiple: false,
    name: "improve-author-tier",
    onChange: (next) => {
      authorTier = [...next][0] || "";
      renderModelPickers(modelCatalog);
    },
  });
  renderModelChoices($("#improve-gate-tiers"), models, selectedGateTiers, {
    filter,
    name: "improve-gate-tier",
    onChange: (next) => {
      selectedGateTiers = next;
      renderModelPickers(modelCatalog);
    },
  });
  $("#improve-selection-note").textContent = `Author: ${authorTier || "none"} · ${selectedGateTiers.size} gate model(s) · calls scale with models × cases × proposals.`;
  window.dispatchEvent(new CustomEvent("clawreinforce:improve-selection"));
}


function loadOptions(skills, models) {
  const skillPicker = $("#improve-skill");
  skillPicker.replaceChildren(...skills.map((skill) => new Option(`${skill.name} — ${skill.description}`, skill.source)));
  const preferred = skills.find((skill) => skill.name === "improvable-uppercase-skill") || skills[0];
  if (preferred) skillPicker.value = preferred.source;
  $("#improve-source").value = preferred?.source || "";
  skillPicker.addEventListener("change", () => { $("#improve-source").value = skillPicker.value; });
  renderModelPickers(models);
}


export async function initImprove() {
  $("#improve-button").addEventListener("click", runImprove);
  $("#improve-model-filter").addEventListener("input", () => renderModelPickers(modelCatalog));
  window.addEventListener("clawreinforce:models", (event) => renderModelPickers(event.detail.models || []));
  window.addEventListener("clawreinforce:model-use", (event) => {
    if (event.detail.target !== "improve") return;
    const tier = event.detail.tier;
    renderModelPickers(modelCatalog, tier);
  });
  try {
    const [status, skillData, modelData] = await Promise.all([api("/api/improve/status"), api("/api/skills"), api("/api/models")]);
    $("#improve-explanation").textContent = status.explanation;
    $("#improve-gates").replaceChildren(...status.gates.map(gateItem));
    setStatus($("#improve-capability"), status.orchestrator.available ? "LOOP READY" : "UNAVAILABLE", status.orchestrator.available ? "good" : "warn");
    loadOptions(skillData.skills, modelData.models);
  } catch (failure) {
    $("#improve-explanation").textContent = "Improve could not load its API state. Start the server, then reload this tab.";
    setStatus($("#improve-capability"), "ERROR", "bad");
    renderError($("#improve-error"), failure);
  }
}
