#!/usr/bin/env node
/**
 * Proof: libauth sortObjectKeys rebuild + Object.keys integer-index order.
 * Same algorithm as @bitauth/libauth build/lib/format/log.js sortObjectKeys.
 */
function sortObjectKeys(objectOrArray) {
  if (
    typeof objectOrArray !== "object" ||
    objectOrArray === null ||
    objectOrArray.constructor.name !== "Object"
  ) {
    return objectOrArray;
  }
  const keys = Object.keys(objectOrArray).sort((a, b) => a.localeCompare(b, "en"));
  return keys.reduce((all, key) => ({ ...all, [key]: objectOrArray[key] }), {});
}

function demo(label, obj) {
  const sorted = sortObjectKeys(obj);
  console.log(
    JSON.stringify({
      label,
      localeCompare: Object.keys(obj).sort((a, b) => a.localeCompare(b, "en")),
      afterRebuildObjectKeys: Object.keys(sorted),
    }),
  );
}

demo("input types", { "00": 1, "06": 1, "0e": 1, "0f": 1, "10": 1 });
demo("output types", { "03": 1, "04": 1, "36": 1 });
demo("global types", { "00": 1, "02": 1, "03": 1, "04": 1, "05": 1, fb: 1, fc: 1 });

const integerHex = [];
for (let i = 0; i < 256; i++) {
  const h = i.toString(16).padStart(2, "0");
  if (String(Number(h)) === h) integerHex.push(h);
}
console.log(JSON.stringify({ canonicalNumericIndexHexByte: integerHex }));
