import { $, api, clearError, renderError, setStatus } from "/ui.js";

let currentRun = null;
let stream = null;


function score(value, signed = false) {
  if (value == null) return "ungraded";
  return `${signed && value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}


function renderRow(row) {
  const empty = $("#arena-rows .empty");
  if (empty) empty.parentElement.remove();
  const tableRow = document.createElement("tr");
  const values = [
    row.tier,
    row.trial,
    score(row.without_skill),
    score(row.with_skill),
    score(row.uplift, true),
    row.status,
    row.last_error ? JSON.stringify(row.last_error) : "—",
  ];
  values.forEach((value, index) => {
    const cell = document.createElement("td");
    cell.textContent = value;
    if (index === 6 && row.last_error) cell.className = "table-error";
    tableRow.appendChild(cell);
  });
  $("#arena-rows").appendChild(tableRow);
}


function renderSummary(report) {
  const summary = report.summary;
  $("#metric-without").textContent = score(summary.without_skill);
  $("#metric-with").textContent = score(summary.with_skill);
  $("#metric-uplift").textContent = score(summary.uplift, true);
  $("#metric-coverage").textContent = `${summary.coverage.completed_rows} / ${summary.coverage.expected_rows}`;
}


function setDownloads(runId, enabled) {
  [["#download-csv", "csv"], ["#download-png", "png"]].forEach(([selector, kind]) => {
    const link = $(selector);
    link.classList.toggle("disabled", !enabled);
    link.setAttribute("aria-disabled", String(!enabled));
    if (enabled) {
      link.href = `/api/runs/${runId}/export.${kind}`;
      link.download = `clawreinforce-${runId}.${kind}`;
    } else {
      link.removeAttribute("href");
      link.removeAttribute("download");
    }
  });
}


function finish(type, report) {
  renderSummary(report);
  const complete = type === "run_completed";
  setStatus($("#arena-status"), complete ? "COMPLETE" : "CANCELLED", complete ? "good" : "warn");
  $("#bench-button").disabled = false;
  $("#cancel-button").disabled = true;
  setDownloads(currentRun, true);
  stream.close();
}


function listen(runId) {
  stream = new EventSource(`/api/runs/${runId}/events`);
  stream.addEventListener("model_row", (event) => renderRow(JSON.parse(event.data).row));
  stream.addEventListener("progress", (event) => {
    const value = JSON.parse(event.data);
    $("#metric-coverage").textContent = `${value.completed} / ${value.total}`;
  });
  ["run_completed", "run_cancelled"].forEach((type) => {
    stream.addEventListener(type, (event) => finish(type, JSON.parse(event.data).report));
  });
  stream.addEventListener("run_failed", (event) => {
    const failure = JSON.parse(event.data).error;
    setStatus($("#arena-status"), "FAILED", "bad");
    $("#bench-button").disabled = false;
    $("#cancel-button").disabled = true;
    $("#arena-rows").innerHTML = '<tr><td colspan="7" class="empty">Fix the structured error, then start a new run.</td></tr>';
    renderError($("#arena-error"), failure);
    stream.close();
  });
  stream.onerror = () => {
    if ($("#arena-status").textContent !== "RUNNING") return;
    renderError($("#arena-error"), {
      code: "arena.stream_disconnected",
      kind: "unavailable",
      message: "The live result stream disconnected before the run finished.",
      context: { run_id: runId },
    });
    setStatus($("#arena-status"), "DISCONNECTED", "bad");
  };
}


async function start() {
  if (stream) stream.close();
  clearError($("#arena-error"));
  setDownloads("", false);
  $("#arena-rows").innerHTML = '<tr><td colspan="7" class="empty">Run accepted. Waiting for the first streamed trial…</td></tr>';
  setStatus($("#arena-status"), "RUNNING", "warn");
  $("#bench-button").disabled = true;
  try {
    const result = await api("/api/bench", {
      method: "POST",
      body: JSON.stringify({
        task: $("#arena-task").value.trim(),
        skill: $("#arena-skill").value.trim(),
        tiers: [$("#arena-tier").value],
        trials: Number($("#arena-trials").value),
      }),
    });
    currentRun = result.run_id;
    $("#cancel-button").disabled = false;
    listen(currentRun);
  } catch (failure) {
    $("#bench-button").disabled = false;
    setStatus($("#arena-status"), "ERROR", "bad");
    renderError($("#arena-error"), failure);
  }
}


function options(rows, label) {
  return rows.map((row) => {
    const option = document.createElement("option");
    option.value = row.source || row.tier;
    option.textContent = label(row);
    return option;
  });
}


async function loadPickers() {
  try {
    const [taskData, skillData, modelData] = await Promise.all([api("/api/tasks"), api("/api/skills"), api("/api/models")]);
    $("#arena-task-picker").replaceChildren(...options(taskData.tasks, (row) => `${row.difficulty} · ${row.name}${row.gradeable ? "" : " · ungraded"}`));
    $("#arena-skill-picker").replaceChildren(...options(skillData.skills, (row) => row.name));
    $("#arena-tier").replaceChildren(...options(modelData.models, (row) => row.tier));
    const task = taskData.tasks.find((row) => row.source === "examples/uppercase-task") || taskData.tasks[0];
    const skill = skillData.skills.find((row) => row.source === "examples/uppercase-skill") || skillData.skills[0];
    const tier = modelData.models.find((row) => row.tier === "fixture:upper-if-skilled") || modelData.models[0];
    if (!task || !skill || !tier) throw { code: "arena.pickers_empty", kind: "unavailable", message: "Task, skill, or tier catalog is empty.", context: {} };
    $("#arena-task-picker").value = task.source;
    $("#arena-task").value = task.source;
    $("#arena-skill-picker").value = skill.source;
    $("#arena-skill").value = skill.source;
    $("#arena-tier").value = tier.tier;
  } catch (failure) {
    setStatus($("#arena-status"), "ERROR", "bad");
    renderError($("#arena-error"), failure);
  }
}


export function initArena() {
  $("#arena-task-picker").addEventListener("change", (event) => { $("#arena-task").value = event.target.value; });
  $("#arena-skill-picker").addEventListener("change", (event) => { $("#arena-skill").value = event.target.value; });
  $("#bench-button").addEventListener("click", start);
  $("#cancel-button").addEventListener("click", async () => {
    if (!currentRun) return;
    try {
      await api(`/api/runs/${currentRun}/cancel`, { method: "POST", body: "{}" });
    } catch (failure) {
      renderError($("#arena-error"), failure);
    }
  });
  loadPickers();
}
