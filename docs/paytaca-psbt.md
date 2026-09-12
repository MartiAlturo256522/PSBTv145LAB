# Paytaca PSBT dialect

Source of truth: [paytaca-app/src/lib/multisig/psbt.js](https://github.com/paytaca/paytaca-app/blob/master/src/lib/multisig/psbt.js)

## PSBT version 145 is not a BIP

```javascript
/**
 * TODO: Create CHIP
 * @param {number} [version = 145] Using BCH's bip44 cointype as PSBT version
 */
setPsbtVersion(version = 145){
  const k = new Key(hexToBin(PSBT_GLOBAL_VERSION))  // 0xFB
  const v = new Value(numberToBinUint32LE(version)) // 145 → 91 00 00 00
}
```

Official PSBT versions: **0** (BIP-174) and **2** (BIP-370). Coin type 145 is SLIP-0044 Bitcoin Cash.

## Key type 0x36

```javascript
const PSBT_OUT_CASHTOKEN = '36'  // Version(145) token prefix encoded
```

Value = libauth `encodeTokenPrefix(token)` including `0xef`. Output `PSBT_OUT_SCRIPT` (0x04) is locking bytecode **without** the prefix. Unsigned tx outputs **do** contain the prefix.

There is **no** input-map token key. Input tokens come from `PSBT_IN_NON_WITNESS_UTXO` (full previous tx) via `decodeTransactionBch`.

## Hybrid v0+v2

`sanitizeForVersion(145)` is a no-op: unsigned tx **and** v2 counts/prevouts/amounts are all present. That violates BIP-370 (v2 must exclude unsigned tx).

## Proprietary 0xFC

Identifiers `paytaca` and `metadata`. Subtypes: walletHash, origin, purpose, network, creator. Optional. Not consensus. A hardware signer does not need them.

## What SeedCash must understand

To **sign correctly**: CashTokens tx decoding of unsigned tx + prev txs (0xef). FORKID. Optional SIGHASH_UTXOS.

To **display correctly**: same, plus genesis detection (`prevout.n==0`), hybrid NFT+FT, burns by amount, capability transitions.

SeedCash does **not** currently interpret 0x36 or version 145. Version 145 as uint32 LE `91 00 00 00` is stored via CompactSize-as-varint as 145 and ignored.
