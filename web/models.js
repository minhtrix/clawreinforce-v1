import { $, api, clearError, renderError, setStatus } from "/ui.js";
import { adoptModelCatalog, loadModelCatalog } from "/model-catalog.js";
import { renderModelChoices } from "/model-picker.js";

let catalog = { providers: [], models: [], preset: "" };
let selectedTier = "";


function publishCatalog() {
  window.dispatchEvent(new CustomEvent("clawreinforce:models", { detail: catalog }));
}


function selectTier(tier) {
  if (catalog.models.some((row) => row.tier === tier)) selectedTier = tier;
  renderPicker($("#model-filter").value);
}


function renderPicker(filter = "") {
  const query = filter.toLowerCase();
  const rows = catalog.models.filter((row) => `${row.provider} ${row.model} ${row.tier}`.toLowerCase().includes(query));
  if (!catalog.models.some((row) => row.tier === selectedTier)) {
    selectedTier = catalog.models.find((row) => row.tier === "fixture:upper-if-skilled")?.tier
      || catalog.preset || catalog.models[0]?.tier || "";
  }
  renderModelChoices($("#model-choices"), catalog.models, new Set(selectedTier ? [selectedTier] : []), {
    filter,
    multiple: false,
    name: "catalog-tier",
    emptyMessage: filter
      ? "No matching models. Clear the filter or Discover a provider."
      : "No models discovered. Use a provider Discover action below.",
    onChange: (next) => {
      selectedTier = [...next][0] || "";
      renderPicker(filter);
    },
  });
  const available = Boolean(selectedTier && rows.some((row) => row.tier === selectedTier));
  $("#use-verify-model").disabled = !available;
  $("#use-improve-model").disabled = !available;
  $("#use-arena-model").disabled = !available;
}


function modelCell(row) {
  const container = document.createElement("div");
  container.className = "model-list";
  if (!row.models.length) {
    container.className = "table-empty";
    container.textContent = row.configured ? "No cached models. Click Discover." : "Configure this provider, then Discover.";
    return container;
  }
  row.models.forEach((model) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = model;
    button.addEventListener("click", () => selectTier(`${row.provider}:${model}`));
    container.appendChild(button);
  });
  return container;
}


function errorCell(lastError) {
  if (!lastError) {
    const empty = document.createElement("span");
    empty.className = "table-empty";
    empty.textContent = "None reported.";
    return empty;
  }
  const error = document.createElement("pre");
  error.className = "provider-error";
  error.textContent = JSON.stringify(lastError, null, 2);
  return error;
}


async function discover(provider) {
  clearError($("#models-error"));
  setStatus($("#models-status"), `DISCOVERING ${provider}`, "warn");
  try {
    const result = await api("/api/models/discover", {
      method: "POST",
      body: JSON.stringify({ provider }),
    });
    catalog = adoptModelCatalog(result);
    publishCatalog();
    renderPicker($("#model-filter").value);
    renderRows($("#model-filter").value);
    setStatus(
      $("#models-status"),
      result.discovery.status === "completed" ? `${provider} READY` : `${provider} ERROR`,
      result.discovery.status === "completed" ? "good" : "bad",
    );
  } catch (failure) {
    renderError($("#models-error"), failure);
    setStatus($("#models-status"), "ERROR", "bad");
  }
}


function providerRow(provider) {
  const row = document.createElement("tr");
  const name = document.createElement("td");
  const strong = document.createElement("strong");
  strong.textContent = provider.provider;
  const base = document.createElement("code");
  base.textContent = provider.base_url || "built-in deterministic fixture";
  name.append(strong, base);
  const configured = document.createElement("td");
  configured.textContent = provider.configured ? "ready" : "key missing";
  configured.title = provider.configured ? "Provider is ready to call." : "Set the provider environment variable or add an api_key to the ignored providers.json file.";
  configured.className = provider.configured ? "good-text" : "warn-text";
  const key = document.createElement("td");
  key.textContent = provider.key_source;
  const models = document.createElement("td");
  models.appendChild(modelCell(provider));
  const lastError = document.createElement("td");
  lastError.appendChild(errorCell(provider.last_error));
  const action = document.createElement("td");
  const button = document.createElement("button");
  button.className = "secondary discover-button";
  button.type = "button";
  button.textContent = `Discover ${provider.provider}`;
  button.addEventListener("click", () => discover(provider.provider));
  action.appendChild(button);
  row.append(name, configured, key, models, lastError, action);
  return row;
}


function renderRows(filter = "") {
  const query = filter.toLowerCase();
  const rows = catalog.providers.filter((row) => {
    const searchable = `${row.provider} ${row.base_url || ""} ${(row.models || []).join(" ")}`;
    return searchable.toLowerCase().includes(query);
  });
  if (!rows.length) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="6" class="empty">No provider matches this filter. Clear it to restore the registry.</td>';
    $("#provider-rows").replaceChildren(row);
    return;
  }
  $("#provider-rows").replaceChildren(...rows.map(providerRow));
}


export async function initModels(showTab) {
  $("#model-filter").addEventListener("input", (event) => {
    renderPicker(event.target.value);
    renderRows(event.target.value);
  });
  $("#use-verify-model").addEventListener("click", () => {
    window.dispatchEvent(new CustomEvent("clawreinforce:model-use", { detail: { target: "verify", tier: selectedTier } }));
    showTab("verify");
  });
  $("#use-arena-model").addEventListener("click", () => {
    window.dispatchEvent(new CustomEvent("clawreinforce:model-use", { detail: { target: "arena", tier: selectedTier } }));
    showTab("arena");
  });
  $("#use-improve-model").addEventListener("click", () => {
    window.dispatchEvent(new CustomEvent("clawreinforce:model-use", { detail: { target: "improve", tier: selectedTier } }));
    showTab("improve");
  });
  try {
    catalog = await loadModelCatalog();
    publishCatalog();
    renderPicker();
    renderRows();
    setStatus($("#models-status"), `${catalog.llm_count || 0} LLMS READY`, catalog.llm_count ? "good" : "warn");
  } catch (failure) {
    renderError($("#models-error"), failure);
    $("#provider-rows").innerHTML = '<tr><td colspan="6" class="empty">Start the server, then reload to read provider status.</td></tr>';
    setStatus($("#models-status"), "ERROR", "bad");
  }
}
