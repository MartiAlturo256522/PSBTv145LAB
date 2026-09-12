#!/usr/bin/env node
/**
 * UR encode/decode using the SAME npm packages Paytaca ships:
 *   @ngraveio/bc-ur
 *   @keystonehq/bc-ur-registry
 *
 * This is not Paytaca app UI code. Compatibility claim is:
 * same libraries + BCR crypto-psbt (CBOR bytes of PSBT).
 *
 * stdin JSON: { op, psbt?: base64 of raw PSBT bytes, hex?: hex fallback, parts?, maxFragment? }
 */
import { URDecoder } from "@ngraveio/bc-ur";
import { CryptoPSBT } from "@keystonehq/bc-ur-registry";

const input = JSON.parse(await readStdin());
const op = input.op || "encode";

try {
  if (op === "encode" || op === "roundtrip") {
    const buf = input.psbt
      ? Buffer.from(String(input.psbt), "base64")
      : Buffer.from(String(input.hex).trim(), "hex");
    if (!buf.length || buf[0] !== 0x70) {
      throw new Error("psbt payload is not binary PSBT (expected magic 0x70 'p')");
    }
    const crypto = new CryptoPSBT(buf);
    const maxFragment = Number(input.maxFragment) || 200;
    const encoder = crypto.toUREncoder(maxFragment);
    const n = encoder.fragmentsLength || 1;
    const parts = [];
    const loops = Math.max(n, 1) * 3;
    for (let i = 0; i < loops; i++) {
      parts.push(String(encoder.nextPart()).toLowerCase());
      if (n === 1 && i === 0) break;
      if (n > 1 && i + 1 >= n * 2) break;
    }
    const unique = [];
    const seen = new Set();
    for (const p of parts) {
      if (!seen.has(p)) {
        seen.add(p);
        unique.push(p);
      }
    }
    const out = {
      ok: true,
      type: "crypto-psbt",
      libraries: ["@ngraveio/bc-ur", "@keystonehq/bc-ur-registry"],
      maxFragment,
      fragmentsLength: n,
      single: n === 1,
      parts: n === 1 ? unique.slice(0, 1) : parts,
      uniqueParts: unique.length,
    };
    if (op === "roundtrip") {
      const dec = new URDecoder();
      for (const p of parts) dec.receivePart(p);
      if (!dec.isComplete()) {
        out.roundtrip = false;
        out.decodeError = "incomplete";
      } else {
        const ur = dec.resultUR();
        const decoded = CryptoPSBT.fromCBOR(ur.cbor).getPSBT();
        const hex = Buffer.from(decoded).toString("hex");
        const originalHex = buf.toString("hex");
        out.roundtrip = hex === originalHex;
        out.decodedHex = hex;
      }
    }
    process.stdout.write(JSON.stringify(out));
  } else if (op === "decode") {
    const dec = new URDecoder();
    for (const p of input.parts || []) dec.receivePart(String(p));
    if (!dec.isComplete()) {
      process.stdout.write(JSON.stringify({ ok: false, error: "incomplete" }));
      process.exit(1);
    }
    const ur = dec.resultUR();
    const decoded = CryptoPSBT.fromCBOR(ur.cbor).getPSBT();
    process.stdout.write(
      JSON.stringify({
        ok: true,
        hex: Buffer.from(decoded).toString("hex"),
        type: ur.type,
      }),
    );
  } else {
    throw new Error("unknown op");
  }
} catch (e) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(e && e.stack ? e.stack : e) }));
  process.exit(1);
}

function readStdin() {
  return new Promise((resolve) => {
    const chunks = [];
    process.stdin.on("data", (c) => chunks.push(c));
    process.stdin.on("end", () => resolve(Buffer.concat(chunks).toString("utf8") || "{}"));
  });
}
