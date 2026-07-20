import { $, api, clearError, renderError, setStatus } from "/ui.js";
import { loadModelCatalog } from "/model-catalog.js";
import { renderModelChoices, selectionSummary } from "/model-picker.js";

let currentCertificate = null;
let modelCatalog = [];
let selectedTiers = new Set();
let modelSelectionTouched = false;

function renderModels(preferred = "") {
  if (!modelSelectionTouched && preferred && modelCatalog.some((row) => row.tier === preferred)) {
    selectedTiers = new Set([preferred]);
  }
  selectedTiers = new Set([...selectedTiers].filter((tier) => modelCatalog.some((row) => row.tier === tier)));
  if (preferred && modelCatalog.some((row) => row.tier === preferred)) selectedTiers.add(preferred);
  if (!selectedTiers.size && modelCatalog.length) {
    selectedTiers.add(modelCatalog.find((row) => row.tier === "fixture:upper-if-skilled")?.tier || modelCatalog[0].tier);
  }
  renderModelChoices($("#verify-tiers"), modelCatalog, selectedTiers, {
    filter: $("#verify-model-filter").value,
    name: "verify-tier",
    onChange: (next) => { modelSelectionTouched = true; selectedTiers = next; renderModels(); },
  });
  $("#verify-selection-note").textContent = `${selectionSummary(modelCatalog, selectedTiers)} selected · Certify and Guard use this same set.`;
}

function emptyRow(message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 4;
  cell.className = "empty-state";
  cell.textContent = message;
  row.appendChild(cell);
  return row;
}

function renderFindings(findings) {
  if (!findings.length) {
    const item = document.createElement("li");
    item.className = "finding clean";
    item.textContent = "No static findings in the inspected skill bytes.";
    $("#finding-list").replaceChildren(item);
    return;
  }
  $("#finding-list").replaceChildren(...findings.map((finding) => {
    const item = document.createElement("li");
    item.className = `finding ${finding.severity}`;
    const title = document.createElement("strong");
    title.textContent = `${finding.severity.toUpperCase()} · ${finding.code}`;
    const detail = document.createElement("span");
    detail.textContent = `${finding.message} — ${finding.location}`;
    item.append(title, detail);
    return item;
  }));
}

function renderTiers(tiers) {
  if (!tiers?.length) {
    $("#tier-results").replaceChildren(emptyRow("No tiers were reported. Select a tier and certify again."));
    return;
  }
  $("#tier-results").replaceChildren(...tiers.map((tier) => {
    const row = document.createElement("tr");
    const coverage = `${tier.coverage.completed} / ${tier.coverage.expected}`;
    const rate = tier.pass_rate == null ? "ungraded" : `${(tier.pass_rate * 100).toFixed(0)}%`;
    [tier.tier, tier.status, coverage, rate].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });
    return row;
  }));
}

function renderCertificate(result) {
  currentCertificate = result.certificate;
  $("#certificate-skill").textContent = result.report.skill;
  $("#certificate-fingerprint").textContent = result.report.fingerprint;
  $("#check-signature").disabled = false;
  $("#signature-state").textContent = "Signature has not been checked in this session.";
  if (result.badge_svg) {
    const image = document.createElement("img");
    image.alt = `Verification badge for ${result.report.skill}`;
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(result.badge_svg)}`;
    $("#badge-preview").replaceChildren(image);
  } else {
    $("#badge-preview").textContent = "No badge: this certificate has no scored coverage.";
  }
}

async function runEvidence(kind) {
  const error = $("#verify-error");
  clearError(error);
  setStatus($("#verify-status"), kind === "scan" ? "SCANNING" : "CERTIFYING", "warn");
  try {
    if (kind === "certify" && !selectedTiers.size) {
      throw { code: "verify.tiers", kind: "validation", message: "Choose at least one certification model.", context: {} };
    }
    const source = $("#verify-source").value.trim();
    const payload = kind === "scan"
      ? { path: source }
      : { source, tiers: [...selectedTiers], samples: Number($("#verify-samples").value) };
    const result = await api(`/api/${kind}`, { method: "POST", body: JSON.stringify(payload) });
    renderFindings(result.findings || []);
    if (kind === "certify") {
      renderTiers(result.report.tiers);
      renderCertificate(result);
    }
    const clean = !(result.findings || []).length;
    const passing = kind === "scan" || result.report.tiers.every((tier) => tier.status === "completed" && tier.pass_rate === 1);
    setStatus(
      $("#verify-status"),
      kind === "scan" ? (clean ? "SCANNED" : "REVIEW") : (passing && clean ? "CERTIFIED" : "REVIEW"),
      passing && clean ? "good" : "warn",
    );
  } catch (failure) {
    renderError(error, failure);
    setStatus($("#verify-status"), "ERROR", "bad");
  }
}

async function runGuard() {
  clearError($("#guard-error"));
  const card = $("#guard-verdict");
  card.className = "verdict-card neutral";
  $("#guard-verdict-label").textContent = "CHECKING";
  $("#guard-reasons").innerHTML = "<li>Fetching, scanning, and running declared cases…</li>";
  try {
    if (!selectedTiers.size) {
      throw { code: "guard.tiers", kind: "validation", message: "Choose at least one guard model.", context: {} };
    }
    const result = await api("/api/guard", {
      method: "POST",
      body: JSON.stringify({
        source: $("#guard-source").value.trim(),
        tiers: [...selectedTiers],
        samples: Number($("#verify-samples").value),
      }),
    });
    card.className = `verdict-card ${result.verdict}`;
    $("#guard-verdict-label").textContent = result.verdict.toUpperCase();
    const reasons = result.reasons.length ? result.reasons : ["Clean scan and complete certification coverage."];
    $("#guard-reasons").replaceChildren(...reasons.map((reason) => {
      const item = document.createElement("li");
      item.textContent = reason;
      return item;
    }));
  } catch (failure) {
    card.className = "verdict-card reject";
    $("#guard-verdict-label").textContent = "ERROR";
    $("#guard-reasons").innerHTML = "<li>Resolve the structured error, then run the guard again.</li>";
    renderError($("#guard-error"), failure);
  }
}

async function loadPickers() {
  try {
    const [skillData, modelData] = await Promise.all([api("/api/skills"), loadModelCatalog()]);
    const skills = skillData.skills.map((skill) => {
      const option = document.createElement("option");
      option.value = skill.source;
      option.textContent = `${skill.name} — ${skill.description || "No description"}`;
      return option;
    });
    $("#verify-skill").replaceChildren(...skills);
    const preferred = skillData.skills.find((skill) => skill.source === "examples/uppercase-skill");
    if (preferred) $("#verify-skill").value = preferred.source;
    modelCatalog = modelData.models;
    renderModels(modelData.preset);
    if (skills.length) {
      $("#verify-source").value = $("#verify-skill").value;
      $("#guard-source").value = $("#verify-skill").value;
    }
  } catch (failure) {
    renderError($("#verify-error"), failure);
    setStatus($("#verify-status"), "ERROR", "bad");
  }
}

export function initVerify() {
  $("#verify-skill").addEventListener("change", (event) => {
    $("#verify-source").value = event.target.value;
    $("#guard-source").value = event.target.value;
  });
  $("#scan-button").addEventListener("click", () => runEvidence("scan"));
  $("#certify-button").addEventListener("click", () => runEvidence("certify"));
  $("#guard-button").addEventListener("click", runGuard);
  $("#verify-model-filter").addEventListener("input", () => renderModels());
  window.addEventListener("clawreinforce:models", (event) => {
    modelCatalog = event.detail.models || [];
    renderModels(event.detail.preset);
  });
  window.addEventListener("clawreinforce:model-use", (event) => {
    if (event.detail.target !== "verify") return;
    renderModels(event.detail.tier);
  });
  $("#check-signature").addEventListener("click", async () => {
    clearError($("#verify-error"));
    try {
      const result = await api("/api/certificates/verify", {
        method: "POST",
        body: JSON.stringify({ certificate: currentCertificate, fingerprint: $("#certificate-fingerprint").textContent }),
      });
      $("#signature-state").textContent = result.valid ? "Valid signature and matching fingerprint." : result.message;
      $("#signature-state").className = `signature-state ${result.valid ? "good" : "bad"}`;
    } catch (failure) {
      renderError($("#verify-error"), failure);
    }
  });
  loadPickers();
}
