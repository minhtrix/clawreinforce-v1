import test from "node:test";
import assert from "node:assert/strict";

import { groupModels, updateSelection } from "./model-picker.js";


const models = [
  { provider: "fixture", model: "echo", tier: "fixture:echo" },
  { provider: "openai", model: "gpt-5.6-sol", tier: "openai:gpt-5.6-sol" },
  { provider: "fixture", model: "upper-if-skilled", tier: "fixture:upper-if-skilled" },
];


test("groupModels preserves provider groups and filters every model field", () => {
  assert.deepEqual(groupModels(models).map((group) => [group.provider, group.rows.length]), [
    ["fixture", 2],
    ["openai", 1],
  ]);
  assert.deepEqual(groupModels(models, "5.6").map((group) => group.provider), ["openai"]);
  assert.deepEqual(groupModels(models, "upper")[0].rows.map((row) => row.tier), ["fixture:upper-if-skilled"]);
});


test("model choice state supports one author and many gate models", () => {
  const gates = updateSelection(new Set(["fixture:echo"]), "openai:gpt-5.6-sol", true, true);
  assert.deepEqual([...gates], ["fixture:echo", "openai:gpt-5.6-sol"]);
  const author = updateSelection(gates, "fixture:upper-if-skilled", true, false);
  assert.deepEqual([...author], ["fixture:upper-if-skilled"]);
});
