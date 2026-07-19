import { $, api } from "/ui.js";


function value(score, signed = false) {
  if (score == null) return "ungraded";
  return `${signed && score >= 0 ? "+" : ""}${score.toFixed(2)}`;
}


function historyRow(record) {
  const row = document.createElement("article");
  row.className = "history-row";
  const heading = document.createElement("strong");
  heading.textContent = record.run_id || "run without id";
  const time = document.createElement("time");
  time.textContent = record.recorded_at ? new Date(record.recorded_at).toLocaleString() : "time unavailable";
  const summary = document.createElement("p");
  summary.textContent = `baseline ${value(record.summary?.without_skill)} → skill ${value(record.summary?.with_skill)} · uplift ${value(record.summary?.uplift, true)}`;
  row.append(heading, time, summary);
  return row;
}


export async function loadHistory() {
  try {
    const result = await api("/api/history");
    const runs = (result.bench_runs || []).slice().reverse().slice(0, 20);
    $("#arena-history-count").textContent = `${runs.length} saved`;
    if (!runs.length) {
      $("#arena-history").innerHTML = '<p class="empty-state">No saved runs yet. Complete a benchmark to append the first ledger entry.</p>';
      return;
    }
    $("#arena-history").replaceChildren(...runs.map(historyRow));
  } catch (failure) {
    $("#arena-history-count").textContent = "ledger error";
    const error = document.createElement("pre");
    error.className = "provider-error";
    error.textContent = JSON.stringify(failure, null, 2);
    $("#arena-history").replaceChildren(error);
  }
}
