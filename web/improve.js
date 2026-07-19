import { $, api, clearError, renderError, setStatus } from "/ui.js";


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
  $("#improve-apply-state").textContent = result.applied
    ? "Accepted body written to SKILL.md."
    : result.dry_run ? "Dry-run only; SKILL.md was not changed." : "No accepted body was available to write.";
  const ids = [...new Set([...Object.keys(result.before), ...Object.keys(result.after)])];
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
  setStatus($("#improve-status"), "RUNNING", "neutral");
  try {
    const result = await api("/api/improve", {
      method: "POST",
      body: JSON.stringify({
        source: $("#improve-source").value.trim(),
        tier: $("#improve-tier").value,
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


function loadOptions(skills, models) {
  const skillPicker = $("#improve-skill");
  skillPicker.replaceChildren(...skills.map((skill) => new Option(`${skill.name} — ${skill.description}`, skill.source)));
  const preferred = skills.find((skill) => skill.name === "improvable-uppercase-skill") || skills[0];
  if (preferred) skillPicker.value = preferred.source;
  $("#improve-source").value = preferred?.source || "";
  skillPicker.addEventListener("change", () => { $("#improve-source").value = skillPicker.value; });
  const tierPicker = $("#improve-tier");
  tierPicker.replaceChildren(...models.map((model) => new Option(model.tier, model.tier)));
  const fixture = models.find((model) => model.tier === "fixture:upper-if-skilled") || models[0];
  if (fixture) tierPicker.value = fixture.tier;
}


export async function initImprove() {
  $("#improve-button").addEventListener("click", runImprove);
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
