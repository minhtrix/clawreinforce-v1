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


export function renderTierChecks(container, models, selected, filter, onChange) {
  const groups = groupModels(models, filter);
  if (!groups.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No matching gate models. Clear the filter or discover a provider in Models.";
    container.replaceChildren(empty);
    return;
  }
  const nodes = groups.map(({ provider, rows }) => {
    const group = document.createElement("fieldset");
    const legend = document.createElement("legend");
    legend.textContent = provider;
    group.appendChild(legend);
    rows.forEach((row) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      const text = document.createElement("span");
      input.type = "checkbox";
      input.value = row.tier;
      input.checked = selected.has(row.tier);
      text.textContent = row.model;
      input.addEventListener("change", () => {
        const next = new Set(selected);
        input.checked ? next.add(row.tier) : next.delete(row.tier);
        onChange(next);
      });
      label.append(input, text);
      group.appendChild(label);
    });
    return group;
  });
  container.replaceChildren(...nodes);
}
