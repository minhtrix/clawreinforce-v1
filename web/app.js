import { $, $$, api, errorText } from "/ui.js";
import { initVerify } from "/verify.js";
import { initImprove } from "/improve.js";
import { initArena } from "/arena.js";

function showTab(name) {
  $$(".tab").forEach((button) => {
    const active = button.dataset.tab === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $$(".view").forEach((view) => {
    const active = view.id === name;
    view.classList.toggle("active", active);
    view.hidden = !active;
  });
  history.replaceState(null, "", `#${name}`);
  if (name === "models" && !providers.length) loadModels();
}

$$('.tab').forEach((button) => button.addEventListener("click", () => showTab(button.dataset.tab)));
window.addEventListener("hashchange", () => showTab(location.hash.slice(1) || "verify"));

let providers = [];
let models = [];

function selectTier(tier) {
  const option = [...$("#model-select").options].find((row) => row.value === tier);
  if (option) $("#model-select").value = tier;
}

function renderModelPicker(preset) {
  const previous = $("#model-select").value;
  const options = models.map((row) => {
    const option = document.createElement("option");
    option.value = row.tier;
    option.textContent = `${row.model} · ${row.provider}`;
    return option;
  });
  $("#model-select").replaceChildren(...options);
  selectTier(models.some((row) => row.tier === previous) ? previous : preset);
  const selected = $("#model-select").value;
  if (selected) {
    if ($("#verify-tier").value === "ollama-cloud:") $("#verify-tier").value = selected;
    if ($("#arena-tier").value === "ollama-cloud:") $("#arena-tier").value = selected;
  }
}

function renderProviders(filter = "") {
  const query = filter.toLowerCase();
  const rows = providers.filter((row) => `${row.provider} ${row.base_url} ${(row.models || []).join(" ")}`.toLowerCase().includes(query));
  $("#provider-grid").replaceChildren(...rows.map((row) => {
    const article = document.createElement("article");
    article.className = `provider ${row.configured ? "" : "off"}`;
    const title = document.createElement("h2"); title.textContent = row.provider;
    const status = document.createElement("div"); status.className = "provider-status";
    status.textContent = row.configured ? `READY · key source: ${row.key_source}` : "NEEDS CONFIGURATION";
    const code = document.createElement("code"); code.textContent = row.base_url || "built-in deterministic fixture";
    const modelList = document.createElement("div"); modelList.className = "model-list";
    (row.models || []).filter((model) => model.toLowerCase().includes(query) || row.provider.toLowerCase().includes(query)).forEach((model) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = model;
      button.addEventListener("click", () => selectTier(`${row.provider}:${model}`));
      modelList.appendChild(button);
    });
    if (row.last_error) {
      const error = document.createElement("small"); error.className = "provider-error"; error.textContent = errorText(row.last_error);
      modelList.appendChild(error);
    }
    article.append(title, status, code, modelList);
    return article;
  }));
}

async function loadModels(refresh = false) {
  try {
    const data = await api(`/api/models${refresh ? "?refresh=1" : ""}`);
    providers = data.providers;
    models = data.models;
    renderModelPicker(data.preset);
    renderProviders($("#model-filter").value);
  } catch (error) {
    $("#provider-grid").textContent = errorText(error);
  }
}

$("#model-filter").addEventListener("input", (event) => renderProviders(event.target.value));
$("#refresh-models").addEventListener("click", () => loadModels(true));
$("#use-verify-model").addEventListener("click", () => {
  $("#verify-tier").value = $("#model-select").value;
  showTab("verify");
});
$("#use-arena-model").addEventListener("click", () => {
  $("#arena-tier").value = $("#model-select").value;
  showTab("arena");
});

showTab(location.hash.slice(1) || "verify");
initVerify();
initImprove();
initArena();
loadModels();
