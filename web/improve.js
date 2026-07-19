import { $, api, renderError, setStatus } from "/ui.js";


function gateItem(gate) {
  const item = document.createElement("li");
  const marker = document.createElement("span");
  marker.textContent = "IMPLEMENTED";
  const content = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = gate.name;
  const detail = document.createElement("p");
  detail.textContent = gate.explanation;
  content.append(title, detail);
  item.append(marker, content);
  return item;
}


export async function initImprove() {
  try {
    const result = await api("/api/improve/status");
    $("#improve-explanation").textContent = result.explanation;
    if (result.gates.length) {
      $("#improve-gates").replaceChildren(...result.gates.map(gateItem));
    } else {
      $("#improve-gates").innerHTML = '<li class="empty-state">No gates are implemented yet. Use Verify to gather evidence first.</li>';
    }
    $("#improve-release").textContent = result.orchestrator.message;
    setStatus($("#improve-status"), result.status === "gates_ready" ? "GATES READY" : result.status.toUpperCase(), "good");
  } catch (failure) {
    $("#improve-explanation").textContent = "The capability state could not be loaded. Start the server, then reload this tab.";
    $("#improve-release").textContent = "Status unavailable";
    setStatus($("#improve-status"), "ERROR", "bad");
    renderError($("#improve-error"), failure);
  }
}
