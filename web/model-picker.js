export function groupModels(models, filter = "") {
  const query = filter.trim().toLowerCase();
  const groups = new Map();
  models.forEach((row) => {
    const haystack = `${row.provider} ${row.model} ${row.tier}`.toLowerCase();
    if (query && !haystack.includes(query)) return;
    if (!groups.has(row.provider)) groups.set(row.provider, []);
    groups.get(row.provider).push(row);
  });
  return [...groups.entries()].map(([provider, rows]) => ({ provider, rows }));
}


export function updateSelection(selected, tier, checked, multiple = true) {
  const next = multiple ? new Set(selected) : new Set();
  if (checked) next.add(tier);
  else next.delete(tier);
  return next;
}


export function fillTierSelect(select, models, preferred = "") {
  const nodes = groupModels(models).map(({ provider, rows }) => {
    const group = document.createElement("optgroup");
    group.label = provider;
    rows.forEach((row) => group.appendChild(new Option(row.model, row.tier)));
    return group;
  });
  if (!nodes.length) nodes.push(new Option("Discover or configure a provider first", ""));
  select.replaceChildren(...nodes);
  select.value = models.some((row) => row.tier === preferred) ? preferred : models[0]?.tier || "";
}


export function renderModelChoices(container, models, selected, options = {}) {
  const {
    filter = "",
    multiple = true,
    name = "model-tier",
    onChange = () => {},
    emptyMessage = "No matching models. Clear the filter or discover a provider in Models.",
  } = options;
  const groups = groupModels(models, filter);
  if (!groups.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = emptyMessage;
    container.replaceChildren(empty);
    return;
  }
  const nodes = groups.map(({ provider, rows }) => {
    const group = document.createElement("details");
    const summary = document.createElement("summary");
    const choices = document.createElement("div");
    const selectedCount = rows.filter((row) => selected.has(row.tier)).length;
    group.open = Boolean(selectedCount) || groups.length <= 2;
    summary.textContent = `${provider} · ${selectedCount}/${rows.length} selected`;
    choices.className = "model-choice-list";
    group.append(summary, choices);
    rows.forEach((row) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      const text = document.createElement("span");
      input.type = multiple ? "checkbox" : "radio";
      input.name = name;
      input.value = row.tier;
      input.checked = selected.has(row.tier);
      const model = document.createElement("strong");
      const tier = document.createElement("small");
      model.textContent = row.model;
      tier.textContent = row.tier;
      text.append(model, tier);
      input.addEventListener("change", () => {
        onChange(updateSelection(selected, row.tier, input.checked, multiple));
      });
      label.append(input, text);
      choices.appendChild(label);
    });
    return group;
  });
  container.replaceChildren(...nodes);
}


export function renderTierChecks(container, models, selected, filter, onChange) {
  renderModelChoices(container, models, selected, { filter, multiple: true, onChange });
}
