import { api } from "/ui.js";

let catalogPromise = null;


export function loadModelCatalog(refresh = false) {
  if (!catalogPromise || refresh) {
    const suffix = refresh ? "?refresh=1" : "?discover=configured";
    catalogPromise = api("/api/models" + suffix).catch((failure) => {
      catalogPromise = null;
      throw failure;
    });
  }
  return catalogPromise;
}


export function adoptModelCatalog(catalog) {
  catalogPromise = Promise.resolve(catalog);
  return catalog;
}
