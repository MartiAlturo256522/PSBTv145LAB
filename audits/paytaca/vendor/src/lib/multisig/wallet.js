/**
 * Load-time stub for Paytaca `transaction-builder.js`.
 *
 * Real `wallet.js` at 9c338d2 imports template/utxo/pst/psbt-wallet/
 * encryption/bsms/coordination (Vuex, axios, eciesjs, ...).
 *
 * `getCompiler` is used only by `estimateFee`. It is not called by
 * `Psbt.serialize`, `Psbt.deserialize`, `Psbt.encode`, or `Psbt.decode`.
 */
export function getCompiler() {
  throw new Error(
    "paytaca vendor stub: getCompiler is omitted; serialize/deserialize do not need wallet.js"
  );
}
