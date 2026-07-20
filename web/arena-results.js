import { $ } from "/ui.js";


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
  return value == null ? "n/a" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(0)}pp`;
}


function metric(selector, value) {
  $(selector).textContent = String(value);
}


function reliabilityRow(label, values, k) {
  const row = document.createElement("tr");
  const ci = values.ci95 ? `${percent(values.ci95[0])} – ${percent(values.ci95[1])}` : "n/a";
  [label, percent(values.pass_at_1), percent(values.pass_at_k), percent(values.pass_all_k), ci, `${values.graded_trials} trials`]
    .forEach((value) => row.appendChild(node("td", "", value)));
  row.title = `Pass@1 = observed trial success · Pass@${k} = any of ${k} succeeds · Pass^${k} = all ${k} succeed`;
  return row;
}


function outcomeLabel(row) {
  if (row.outcome !== "unchanged") return row.outcome;
  if (row.with_rate === 1) return "already solved";
  if (row.with_rate === 0) return "still fails";
  return "unchanged";
}


function scoreBlock(label, rate, passed, graded) {
  const block = node("div", "arena-phase-score");
  const heading = node("div", "arena-phase-heading");
  heading.append(node("span", "", label), node("strong", "", percent(rate)));
  const track = node("div", "arena-score-track");
  const fill = node("span");
  fill.style.width = rate == null ? "0" : `${rate * 100}%`;
  track.appendChild(fill);
  block.append(heading, node("small", "", rate == null ? "not graded" : `${passed}/${graded} trials passed`), track);
  return block;
}


function modelImpact(row) {
  const card = node("article", `arena-model-impact ${row.outcome}`);
  const heading = node("div", "arena-impact-heading");
  heading.append(node("code", "", row.tier), node("span", `impact-verdict ${row.outcome}`, outcomeLabel(row)));
  const scores = node("div", "arena-impact-scores");
  scores.append(
    scoreBlock("WITHOUT SKILL", row.without_rate, row.without_passed, row.without_graded),
    node("strong", "arena-impact-delta", delta(row.uplift)),
    scoreBlock("WITH SKILL", row.with_rate, row.with_passed, row.with_graded),
  );
  card.append(heading, scores);
  if (row.reason) {
    const reason = typeof row.reason === "string" ? row.reason : JSON.stringify(row.reason);
    card.appendChild(node("p", "arena-impact-reason", reason));
  }
  return card;
}


export function resetArenaInsights() {
  $("#arena-improved-label").textContent = "EXECUTORS IMPROVED";
  ["#arena-improved", "#arena-solved-before", "#arena-solved-with", "#arena-regressed"].forEach((selector) => metric(selector, "…"));
  $("#arena-impact-story").textContent = "Measuring every selected LLM without and with the skill…";
  $("#arena-model-impact").innerHTML = '<p class="empty-state">Model comparisons appear when the run completes; raw trial rows stream below.</p>';
  $("#arena-reliability-rows").innerHTML = '<tr><td colspan="6" class="empty-state">Reliability metrics appear after all available trials finish.</td></tr>';
}


export function renderArenaInsights(summary) {
  const comparison = summary.comparison || {};
  const models = summary.per_model || [];
  const fixtureOnly = models.length && models.every((row) => row.tier.startsWith("fixture:"));
  const subject = fixtureOnly ? "test fixtures" : models.some((row) => row.tier.startsWith("fixture:")) ? "executors" : "LLMs";
  $("#arena-improved-label").textContent = `${subject.toUpperCase()} IMPROVED`;
  metric("#arena-improved", `${comparison.improved_models || 0}/${comparison.graded_models || 0}`);
  metric("#arena-solved-before", comparison.solved_without || 0);
  metric("#arena-solved-with", comparison.solved_with || 0);
  metric("#arena-regressed", comparison.regressed_models || 0);
  $("#arena-impact-status").textContent = `${comparison.graded_models || 0}/${comparison.model_count || 0} GRADED`;
  const newSolves = (comparison.solved_with || 0) - (comparison.solved_without || 0);
  $("#arena-impact-story").textContent = `The skill improved ${comparison.improved_models || 0} of ${comparison.graded_models || 0} graded ${subject}, changed strict full solves by ${newSolves >= 0 ? "+" : ""}${newSolves}, and regressed ${comparison.regressed_models || 0}.`;

  $("#arena-model-impact").replaceChildren(...models.map(modelImpact));
  if (!models.length) $("#arena-model-impact").innerHTML = '<p class="empty-state">No model evidence was returned. Inspect the structured run error below.</p>';

  const reliability = summary.reliability || {};
  const k = reliability.k || 1;
  $("#arena-reliability-title").textContent = `Reliability · k=${k}`;
  $("#arena-reliability-rows").replaceChildren(
    reliabilityRow("WITHOUT SKILL", reliability.without_skill || {}, k),
    reliabilityRow("WITH SKILL", reliability.with_skill || {}, k),
  );
}
