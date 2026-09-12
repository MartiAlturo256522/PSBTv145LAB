/**
 * Proof: Paytaca PsbtInput.serialize emits type 0x10 before 0x00 because
 * libauth sortObjectKeys rebuilds a plain object and "10" is a JS array index.
 *
 * Imports the REAL sortObjectKeys from @bitauth/libauth (same module Paytaca uses).
 * Do not import Paytaca encoder; this is Object.keys mechanics only.
 */
import { sortObjectKeys } from '../../tools/oracles/node_modules/@bitauth/libauth/build/lib/format/log.js';

function isCanonicalNumericIndexString(s) {
  if (s === '-0') return true;
  const n = Number(s);
  return String(n) === s;
}

function isArrayIndex(s) {
  if (!isCanonicalNumericIndexString(s)) return false;
  if (s === '-0') return false;
  const n = Number(s);
  return Number.isInteger(n) && n >= 0 && n < 2 ** 32;
}

function trace(label, obj) {
  const before = Object.keys(obj);
  const localeSorted = [...before].sort((a, b) => a.localeCompare(b, 'en'));
  // Same reduce as log.js sortObjectKeys (lines 62-66), with per-step keys.
  const steps = [];
  const rebuilt = localeSorted.reduce((all, key) => {
    const next = { ...all, [key]: obj[key] };
    steps.push({ added: key, objectKeys: Object.keys(next) });
    return next;
  }, {});
  const libauth = sortObjectKeys(obj);
  const afterLibauth = Object.keys(libauth);
  console.log(JSON.stringify({
    label,
    objectKeysBeforeSort: before,
    afterLocaleCompareSort: localeSorted,
    reduceRebuildSteps: steps,
    objectKeysAfterReduceRebuild: Object.keys(rebuilt),
    objectKeysAfterLibauthSortObjectKeys: afterLibauth,
    sameAsLibauth: JSON.stringify(Object.keys(rebuilt)) === JSON.stringify(afterLibauth),
    arrayIndexKeys: before.filter(isArrayIndex),
    nonIndexKeys: before.filter((k) => !isArrayIndex(k)),
  }, null, 2));
}

trace('input types (lab NON_WITNESS_UTXO..SEQUENCE)', { '00': 1, '06': 1, '0e': 1, '0f': 1, '10': 1 });
trace('output types (AMOUNT, SCRIPT, CASHTOKEN)', { '03': 1, '04': 1, '36': 1 });

const integerIndexHex = [];
const notIndexHex = [];
for (let i = 0; i <= 0xfc; i++) {
  const h = i.toString(16).padStart(2, '0');
  (isArrayIndex(h) ? integerIndexHex : notIndexHex).push(h);
}
console.log(JSON.stringify({
  spec: {
    CanonicalNumericIndexString:
      'ECMA-262: if argument is "-0" return -0; n = ToNumber(argument); if SameValue(ToString(n), argument) is false return undefined; else return n.',
    arrayIndex:
      'ECMA-262 OrdinaryOwnPropertyKeys: own keys that are array indexes (CanonicalNumericIndexString whose numeric value i satisfies 0 <= i < 2**32) are listed FIRST, in ascending numeric order; remaining string keys follow in insertion order.',
    Object_keys:
      'Object.keys uses EnumerableOwnPropertyNames -> OrdinaryOwnPropertyKeys, so integer-index strings always precede non-index strings.',
  },
  psbtTypeHex00toFcThatAreJsIntegerIndices: integerIndexHex,
  count: integerIndexHex.length,
  knownPaytacaTypesThatAreIndices: ['10', '11', '12', '13', '14', '15', '16', '17', '18', '36'].filter(isArrayIndex),
  knownPaytacaTypesThatAreNotIndices: ['00', '01', '02', '03', '04', '05', '06', '07', '08', '09', '0a', '0e', '0f', '1a', '1e', '35', 'fb', 'fc'].map((h) => [h, isArrayIndex(h)]),
}, null, 2));
