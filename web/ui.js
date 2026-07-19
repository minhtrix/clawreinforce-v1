export const $ = (selector) => document.querySelector(selector);
export const $$ = (selector) => [...document.querySelectorAll(selector)];

export async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || data.error) throw data.error || { code: `http.${response.status}` };
  return data;
}

export function errorText(error) {
  if (typeof error === "string") return error;
  return `${error.code || "error"}: ${error.message || JSON.stringify(error)}`;
}

export function renderError(element, error) {
  element.hidden = false;
  element.textContent = JSON.stringify(error, null, 2);
}

export function clearError(element) {
  element.hidden = true;
  element.textContent = "";
}

export function setStatus(element, text, tone = "neutral") {
  element.textContent = text;
  element.className = `status ${tone}`;
}
