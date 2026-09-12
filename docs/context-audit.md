# Context audit

## Source Chat (now identified)

On 2026-09-12 the user supplied the Grok Chat URL:

`https://grok.com/c/a6a97e34-c47d-421b-948f-58bf8de55caf`

Authenticated metadata (conversation list API, owner token):

| Field | Value |
|---|---|
| conversationId | `a6a97e34-c47d-421b-948f-58bf8de55caf` |
| title | **Bitcoin Cash PSB v145 Test Transaction Cases** |
| created | 2026-09-12T08:12:49Z |
| modified | 2026-09-12T11:06:46Z |
| duration | ~2h 54m wall-clock (not 18 minutes of model time) |
| public transcript | **not retrievable** — grok.com HTML is an empty SPA shell; message/export endpoints 404; `conversations:read` only returns titles |

Related chats on the same account (titles only, not loaded):

- `14a047be-…` **BCH Genesis Tokens in Multi-Output Transactions** (2026-09-11)
- `f7042a70-…` Gold-backed BCH token creation
- `ec57f3e1-…` FundTokens Beta Live for ETFs

The original assignment said the Chat had been distilled into a repo context document. That file was still missing. The **taxonomy in the CLI prompt** is the distilled hypothesis; this Chat is the likely origin (`PSB v145` in the title is the same “PSBT v145” question).

**Blocked:** ingesting the Chat’s full taxonomy until the user exports it (Share link, copy-paste, or JSON). The laboratory already implements the prompt’s covering set after independent CHIP/Paytaca/libauth/BCHN verification.

---

The prior analysis was **not present as a standalone file** in this workspace. What was available:

1. This assignment’s taxonomy (treated as a hypothesis).
2. The SeedCash security audit at `seedcash/audit/SeedCash-Security-Audit-EN.md` (2026-09-10, commit `4e101663`).
3. SeedCash source (`src/seedcash/models/psbt_parser.py`, `psbt_signer.py`, `views/psbt_views.py`).
4. Independent source from Paytaca, libauth, BCHN, CHIP-2022-02 v2.2.2.

Nothing from Chat was trusted because an LLM said it. Each claim below is confirmed, corrected, or left implementation-specific.

## Confirmed (and kept)

| Claim | Evidence |
|---|---|
| `PREFIX_TOKEN = 0xef` | CHIP v2.2.2; libauth `CashTokens.PREFIX_TOKEN`; BCHN `SPECIAL_TOKEN_PREFIX` |
| Prefix sits before locking bytecode; CompactSize covers both | CHIP *Token Encoding*; libauth `encodeTransactionOutput` |
| Bitfield: `0x80` reserved, `0x40` commitment, `0x20` NFT, `0x10` amount; capability nibble 0/1/2 | CHIP; BCHN `token.h`; libauth |
| Capability 3+ invalid | CHIP invalid vectors; libauth `maximumCapability = 2` |
| Empty commitment omits `HAS_COMMITMENT_LENGTH` | CHIP valid `…20`; libauth encode |
| Amount 0 with `HAS_AMOUNT` invalid | CHIP; libauth `zeroAmount`; BCHN `AmountMustNotBeZeroError` |
| FT max `9223372036854775807` | CHIP; libauth; BCHN INT64_MAX |
| Genesis = **prevout.n == 0**, not vin index | CHIP; BCHN `prevout.GetN() == 0`; libauth `outpointIndex === 0` |
| Multiple genesis inputs → multiple categories | CHIP Figure 1; libauth “mint multiple categories” |
| Spending token-bearing vout=0 **also** genesises a **new** category | CHIP algorithm (index only); BCHN |
| FT cannot be minted after genesis | CHIP *Fungible Token Behavior* |
| Minting NFT may mint unlimited extra NFTs | CHIP; libauth skip if minting-available |
| Mutable → one successor, not minting | CHIP; BCHN `!pdata->IsMintingNFT()` |
| Immutable 1:1 by (category, commitment) | CHIP step 4 |
| Burns by omission | CHIP |
| Hybrid NFT+FT same output, one category | CHIP |
| Category wire = HASH256/P2P order; UI/JSON = explorer order (reverse) | CHIP notes; libauth `category.slice().reverse()` |
| CompactSize must be minimal in prefixes | CHIP; libauth `readCompactUintMinimal` |
| `SIGHASH_UTXOS = 0x20`, after `hashPrevouts`, requires FORKID, forbidden with ANYONECANPAY | CHIP; libauth signing-serialization |
| Token prefix in sighash is **before** coveredBytecode CompactSize, not inside it | CHIP; libauth; SeedCash signer (audit D-01 was a false positive) |
| CashAddr token types 0x10 / 0x18 are **address encoding**, not on-chain scripts | CHIP *CashAddress Token Support*; libauth |
| BIP PSBT versions are 0 and 2 only | BIP-174 / BIP-370 |
| 145 is BIP-44 coin type, not a BIP PSBT version | SLIP-0044; Paytaca `setPsbtVersion(145)` comment |
| Paytaca `PSBT_OUT_CASHTOKEN = 0x36` | `paytaca-app/src/lib/multisig/psbt.js` |
| SeedCash hybrid NFT+FT classified as NFT-only (`if nft elif ft`) | `psbt_parser.py` `arrange_*` |
| SeedCash silent genesis (UI routes on **inputs** only) | `psbt_views.py` LoadingPSBTView — audit SC-04 |
| SeedCash `ft_burning` uses UTXO counts not amounts | `psbt_parser.py` — SC-05 |
| SeedCash NFT burn/mint warning inverted | `get_warning` — SC-05 |
| SeedCash CashAddr token P2PKH uses version 0x08 (`p`) not 0x10 (`z`) | `address_from_script` |
| SeedCash requires GLOBAL unsigned tx (rejects pure v2) | `parse_psbt` |
| SeedCash signs NONE\|FORKID | `psbt_signer.py` — SC-01 |

## Uncertain / era-dependent

| Claim | Status |
|---|---|
| Commitment max 40 | CHIP v2.2.2 / Upgrade 9 **CONFIRMED**. Current BCHN master has Upgrade 12 (May 2026) raising to **128**. Lab default is **40**; NEG-07 is invalid under Upgrade 9 and may be valid on Upgrade 12. |
| Dust for token outputs | Standardness, not CHIP consensus. Lab uses 1000 sats carriers. |
| BCH Schnorr RFC6979 extra entropy | SeedCash uses `extra_entropy=b""`. Lab matches SeedCash. Cross-check vs libauth still SKIPPED (no JS runtime). |

## Wrong / outdated (from Chat or secondary writeups)

| Claim | Correction |
|---|---|
| “PSBT v145 is a standard” | **False.** Paytaca dialect: `TODO: Create CHIP` / “Using BCH's bip44 cointype as PSBT version”. |
| “Key 0x36 is BIP-174” | **False.** BIP registry jumps 0x35 (DNSSEC) → 0xFC. 0x36 is Paytaca-only. |
| “At most one new category per transaction” | **False.** One per genesis input; many genesis inputs per tx. |
| “Immutable NFTs can never be duplicated” | **False if a minting baton (or genesis) of that category is spent.** CHIP allows unlimited immutables when minting-available. |
| Early CHIP `PREFIX_TOKEN = 0xd0` | Superseded. Final is `0xef` (v2.2.0). |
| Early CHIP commitment 40 as standardness only | Final v2.2.0 restored **consensus** 40. |
| Bitcoin ABC implements CashTokens | **False.** ABC left BCH; eCash does not implement CHIP-2022-02. |
| Token-aware address ⇒ token-aware script | **False.** On-chain P2PKH remains `76a914…88ac` plus optional `0xef` prefix. |
| SeedCash `PSBT_GLOBAL_VERSION` CompactSize | BIP-174 is **uint32 LE**. SeedCash `read_varint` happens to work for 0, 2, 145 because the first byte is `< 0xFD`. |

## Implementation-specific (must not be treated as consensus)

| Item | Who |
|---|---|
| `PSBT_GLOBAL_VERSION = 145` + hybrid v0+v2 fields | Paytaca only |
| `PSBT_OUT_CASHTOKEN 0x36` | Paytaca only; redundant copy of `encodeTokenPrefix` |
| Proprietary `0xFC` identifier `paytaca` / `metadata` | Wallet metadata. **Not authoritative for amounts.** |
| BCHN `PSBT_IN_UTXO` (type 0x00) is a **single CTxOut**, not a full prev tx | Breaks BIP-174. SeedCash expects full prev tx. Lab dialect `bchn-v0`. |
| SeedCash UI token review | Input-only, hybrid-blind, genesis-blind |
| BCMR OP_RETURN | Not consensus |

## Must be tested against BCHN / libauth / Paytaca

- Prefix valid/invalid encodings (CHIP JSON; lab unit tests copy the palindrome-category vectors).
- `verifyTransactionTokens` / `CheckTxTokens` for genesis, mint, mutate, burn, overspend.
- Sighash preimage with token prefix + `SIGHASH_UTXOS`.
- Paytaca round-trip of a `paytaca-145` PSBT through `Psbt.decode` (JS; not executed here).
- BCHN `decodepsbt` vs BIP-174 `NON_WITNESS_UTXO` (expected mismatch).
- SeedCash parser on `vectors/seed_signer/*`.
