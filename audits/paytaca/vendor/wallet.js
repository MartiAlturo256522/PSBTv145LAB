/**
 * Load stub for ./wallet.js.
 *
 * Paytaca transaction-builder.js imports getCompiler only for estimateFee().
 * Psbt.serialize / Psbt.deserialize in psbt.js never call it.
 * The real wallet.js pulls template.js, utxo.js, pst.js, Vue, etc. and cannot
 * run in this Node oracle. This is NOT a translation of PSBT logic.
 */
export function getCompiler() {
  throw new Error(
    "wallet.getCompiler stub: unused by Psbt.serialize/deserialize",
  );
}
