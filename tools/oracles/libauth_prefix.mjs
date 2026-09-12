#!/usr/bin/env node
/**
 * Live libauth encodeTokenPrefix oracle.
 * Usage: node libauth_prefix.mjs <json>
 * JSON: { category_ui_hex, amount, nft?: { capability, commitment_hex } }
 * Prints hex of encodeTokenPrefix. Category is UI/explorer hex (libauth reverses).
 */
import { encodeTokenPrefix, hexToBin, binToHex } from "@bitauth/libauth";

const spec = JSON.parse(process.argv[2]);
const token = {
  category: hexToBin(spec.category_ui_hex),
  amount: BigInt(spec.amount ?? 0),
};
if (spec.nft) {
  token.nft = {
    capability: spec.nft.capability,
    commitment: hexToBin(spec.nft.commitment_hex || ""),
  };
}
process.stdout.write(binToHex(encodeTokenPrefix(token)));
