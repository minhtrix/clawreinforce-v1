import { $ } from "/ui.js";

let bestBody = "";


function node(tag, className = "", text = "") {
  const value = document.createElement(tag);
  if (className) value.className = className;
  value.textContent = text;
  return value;
}


function percent(value) {
  return value == null ? "ungraded" : `${(value * 100).toFixed(0)}%`;
}


function delta(value) {
  return value == null ? "n/a" : `${value >= 0 ? "+" : ""}${value.toFixed(0)}pp`;
}


function measurementTable(rows, baselineOnly = false) {
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>Gate model</th><th>Baseline</th><th>Measured</th><th>Delta</th><th>Diagnosis</th></tr></thead>";
  const body = document.createElement("tbody");
  rows.forEach((model) => {
    const row = document.createElement("tr");
    const before = model.baseline_score ?? model.before_pass_rate;
    const after = baselineOnly ? before : (model.measured_score ?? model.after_pass_rate);
    const measuredDelta = model.delta_pp ?? (before == null || after == null ? null : (after - before) * 100);
    const values = [model.tier, percent(before), percent(after), baselineOnly ? "+0pp" : delta(measuredDelta), baselineOnly ? "starting measurement" : model.diagnosis];
    values.forEach((value) => row.appendChild(node("td", "", value)));
    body.appendChild(row);
  });
  table.appendChild(body);
  return table;
}


function baselineCard(result) {
  const card = node("article", "iteration-card baseline");
  const heading = node("div", "iteration-heading");
  heading.append(node("strong", "", `Baseline · ${percent(result.metrics.baseline_score)}`), node("span", "status neutral", "STARTING VALUE"));
  card.append(heading, measurementTable(result.per_model || [], true));
  return card;
}


function attemptCard(attempt) {
  const card = node("details", `iteration-card ${attempt.accepted ? "accepted" : "rejected"}`);
  card.open = Boolean(attempt.accepted);
  const summary = document.createElement("summary");
  summary.append(
    node("strong", "", `Iteration ${attempt.number} · ${percent(attempt.measured_score)}`),
    node("span", attempt.accepted ? "good-text" : "warn-text", attempt.accepted ? "ACCEPTED" : "REJECTED"),
    node("code", "", delta(attempt.delta_pp)),
    node("span", "iteration-diagnosis", attempt.diagnosis),
  );
  const context = node("p", "iteration-context", `Target: ${attempt.target_case} · ${attempt.reason} · ${attempt.verified_examples.length} verified example(s)`);
  const diff = node("pre", "diff-output", attempt.diff || "The author returned no effective body change.");
  card.append(summary, context, measurementTable(attempt.models || []), diff);
  return card;
}


function historyRow(run) {
  const row = node("article", "history-row");
  const metrics = run.metrics || {};
  const recorded = run.recorded_at ? new Date(run.recorded_at).toLocaleString() : "time unavailable";
  row.append(
    node("strong", "", `${run.status} · ${percent(metrics.baseline_score)} → ${percent(metrics.best_score)} · ${delta(metrics.gain_pp)}`),
    node("time", "", recorded),
    node("p", "", `${run.run_id} · author ${run.author_tier || run.tier} · gate ${(run.gate_tiers || [run.tier]).join(", ")} · ${run.write_state} · ${run.output_path}`),
  );
  return row;
}


function patternCard(pattern) {
  const card = node("article", `pattern-card ${pattern.outcome}`);
  const label = pattern.outcome === "helped" ? "HELPED" : pattern.outcome === "hurt" ? "HURT" : "NO EFFECT";
  card.append(
    node("span", "pattern-label", label),
    node("strong", "", `${pattern.strategy} · iteration ${pattern.iteration} · ${delta(pattern.delta_pp)}`),
    node("p", "", pattern.diagnosis || "No diagnosis was recorded."),
    node("small", "", pattern.run_id || "run id unavailable"),
  );
  if (pattern.diff) {
    const detail = document.createElement("details");
    detail.append(node("summary", "", "Show proposal diff"), node("pre", "diff-output", pattern.diff));
    card.appendChild(detail);
  }
  return card;
}


export function beginHardenEvidence() {
  ["#harden-baseline", "#harden-best", "#harden-delta", "#harden-iteration"].forEach((selector) => { $(selector).textContent = "…"; });
  $("#harden-file-truth").textContent = "measuring · SKILL.md remains untouched until the gate accepts and Apply is enabled";
  $("#harden-iterations").innerHTML = '<p class="empty-state">Measuring baseline, asking the author, re-measuring, then applying the deterministic gate…</p>';
}


export function renderHardenEvidence(result) {
  const metrics = result.metrics || {};
  $("#harden-baseline").textContent = percent(metrics.baseline_score);
  $("#harden-best").textContent = percent(metrics.best_score);
  $("#harden-delta").textContent = delta(metrics.gain_pp);
  $("#harden-iteration").textContent = metrics.accepted_iteration == null ? "NO ACCEPT" : `ITER ${metrics.accepted_iteration}`;
  $("#harden-file-truth").textContent = `${result.write_state} · ${result.output_path} · ${result.run_id}`;

  const attempts = result.attempts || [];
  $("#harden-attempt-count").textContent = `${attempts.length} ATTEMPT${attempts.length === 1 ? "" : "S"}`;
  $("#harden-iterations").replaceChildren(baselineCard(result), ...attempts.map(attemptCard));

  const history = result.history || [];
  $("#harden-history-count").textContent = `${history.length} run${history.length === 1 ? "" : "s"}`;
  $("#harden-run-history").replaceChildren(...history.map(historyRow));

  const patterns = result.learned_patterns || [];
  $("#harden-pattern-count").textContent = `${patterns.length} PATTERN${patterns.length === 1 ? "" : "S"}`;
  if (patterns.length) $("#harden-patterns").replaceChildren(...patterns.map(patternCard));
  else $("#harden-patterns").innerHTML = '<p class="empty-state">No proposal was needed, so this run produced no rewrite pattern.</p>';

  bestBody = result.candidate_body || result.original_body || "";
  $("#harden-before").textContent = result.original_body || "Original body unavailable.";
  $("#harden-after").textContent = bestBody || "No accepted result yet.";
  $("#copy-hardened-skill").disabled = !bestBody;
}


export function initHardenEvidence() {
  $("#copy-hardened-skill").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    try {
      await navigator.clipboard.writeText(bestBody);
      button.textContent = "Copied";
      setTimeout(() => { button.textContent = "Copy best body"; }, 1600);
    } catch (failure) {
      button.textContent = "Copy failed";
      button.title = String(failure);
    }
  });
}
