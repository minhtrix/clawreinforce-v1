import { $$ } from "/ui.js";
import { initVerify } from "/verify.js";
import { initImprove } from "/improve.js";
import { initArena } from "/arena.js";
import { initModels } from "/models.js";
import { initTraps } from "/traps.js";

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
}

$$('.tab').forEach((button) => button.addEventListener("click", () => showTab(button.dataset.tab)));
window.addEventListener("hashchange", () => showTab(location.hash.slice(1) || "verify"));

showTab(location.hash.slice(1) || "verify");
initVerify();
initImprove();
initArena();
initModels(showTab);
initTraps();
