#!/usr/bin/env node
/**
 * Live Paytaca Psbt oracle (real src/lib/multisig/psbt.js, not a translation).
 *
 * Usage:
 *   node paytaca_psbt.mjs <hex|base64>
 *   node paytaca_psbt.mjs <file.hex|file.base64|vector.json|decoded.json>
 *   echo <hex> | node paytaca_psbt.mjs
 *
 * Prints JSON: { hex, encode_hex? } from Psbt.deserialize+serialize,
 * and encode() when a Paytaca decoded object can be built.
 */
import { existsSync, readFileSync } from "node:fs";
import { Psbt } from "../../audits/paytaca/vendor/src/lib/multisig/psbt.js";
import {
  base64ToBin,
  binToBase64,
  binToHex,
  hexToBin,
  isBase64,
  isHex,
} from "@bitauth/libauth";

function readRaw() {
  const arg = process.argv[2];
  if (!arg || arg === "-") {
    return readFileSync(0, "utf8");
  }
  if (existsSync(arg)) {
    const buf = readFileSync(arg);
    if (arg.endsWith(".binary") || arg.endsWith(".bin")) {
      return buf;
    }
    return buf.toString("utf8");
  }
  return arg;
}

function parsePayload(raw) {
  if (raw instanceof Uint8Array || Buffer.isBuffer(raw)) {
    return { bin: Uint8Array.from(raw) };
  }
  const text = String(raw).trim();
  if (!text) {
    throw new Error("empty input");
  }
  if (text.startsWith("{")) {
    return { json: JSON.parse(text) };
  }
  if (isHex(text)) {
    return { bin: hexToBin(text) };
  }
  if (isBase64(text)) {
    return { bin: base64ToBin(text) };
  }
  throw new Error("input is not hex, base64, JSON, or a readable file");
}

function binFromJson(obj) {
  const hex = obj.psbt_hex || obj.hex || obj.psbtHex;
  if (typeof hex === "string" && isHex(hex)) {
    return hexToBin(hex);
  }
  const b64 = obj.psbt_base64 || obj.base64 || obj.psbt;
  if (typeof b64 === "string" && isBase64(b64)) {
    return base64ToBin(b64);
  }
  return null;
}

function looksLikePaytacaDecoded(obj) {
  return (
    obj &&
    typeof obj === "object" &&
    typeof obj.unsignedTransactionHex === "string" &&
    Array.isArray(obj.inputs) &&
    Array.isArray(obj.outputs)
  );
}

function main() {
  const payload = parsePayload(readRaw());
  const out = {};

  let bin = payload.bin || (payload.json ? binFromJson(payload.json) : null);
  if (bin) {
    const psbt = new Psbt();
    psbt.deserialize(bin);
    out.hex = binToHex(psbt.serialize());

    try {
      const decoded = {};
      const decodedPsbt = new Psbt();
      decodedPsbt.decode(binToBase64(bin), decoded);
      const unsigned = decodedPsbt.globalMap.getUnsignedTx();
      if (unsigned && !decoded.unsignedTransactionHex) {
        decoded.unsignedTransactionHex = binToHex(unsigned);
      }
      if (decoded.network === undefined) {
        decoded.network = "mainnet";
      }
      if (decoded.locktime === undefined) {
        decoded.locktime = 0;
      }
      const encoded = new Psbt();
      encoded.encode(decoded);
      out.encode_hex = binToHex(encoded.serialize());
    } catch (err) {
      out.encode_error = String(err && err.message ? err.message : err);
    }
  }

  const decodedObj = payload.json && looksLikePaytacaDecoded(payload.json)
    ? payload.json
    : null;
  if (decodedObj) {
    try {
      if (decodedObj.network === undefined) {
        decodedObj.network = "mainnet";
      }
      const encoded = new Psbt();
      encoded.encode(decodedObj);
      out.encode_from_json_hex = binToHex(encoded.serialize());
    } catch (err) {
      out.encode_from_json_error = String(
        err && err.message ? err.message : err,
      );
    }
  }

  if (!out.hex && !out.encode_from_json_hex) {
    throw new Error(
      "no PSBT bytes found (need hex/base64/psbt_hex) and JSON is not a Paytaca decoded object",
    );
  }
  process.stdout.write(JSON.stringify(out) + "\n");
}

main();
