# Engine audit — existing CashTokens PSBT generator

Audit of the **current** pipeline (`engine.py` → `vectors/generator.py` → `fixtures/graph.py` → consensus/semantics/codec). **No generator code was modified.** Line numbers refer to `src/ctlab/` unless noted.

## Pipeline (what actually runs)

`engine.generate_from_config` only normalizes a dict and calls `generate_vector` (`engine.py:45–47`). The motor is `vectors/generator.py:135–339`:

1. `copy.deepcopy(scenario)`
2. `build_fixture_graph` twice (`generator.py:140–143`) — first pass so `_resolve_categories` can copy `spent.token.category` from the synthetic genesis tx; second pass rebuilds outputs with those categories filled
3. `_apply_inject` for negative prefix bytes
4. `validate_transaction_tokens` + `interpret_token_semantics`
5. optional sign → `encode_psbt` → **`decode_psbt` of the same bytes** → export fields

Catalog rows are `_e(...)` dicts (`vectors/catalog.py:15–53`): `existing`, `inputs`, `outputs`, plus `extra` merged into the scenario.

---

## Hidden assumptions

| Assumption | Evidence |
|---|---|
| Lab universe is five BIP-44 actors from a fixed mnemonic | `fixtures/keys.py:119–125`; `ctlab/__init__.py:19–24`. Unknown `owner` raises `KeyError`. |
| Custom configs default **Paytaca 145**, catalog defaults **bip174-v0** | `engine.py:15–19` vs `catalog.py:47`. Same engine, different dialect if the caller omits `dialect`. |
| `existing[].token.category` is the **funding txid**, not the token-bearing tx’s txid | `graph.py:134`, `graph.py:118–120`; `_resolve_categories` comment `generator.py:48–50`. |
| Two `existing` keys are **two categories** unless `_same_category_clone` | `graph.py:124–128` vs `169–206`. POST-11/POST-14 set the flag (`catalog.py:306`, `329`). Without it, FT merge would be two genesis categories. |
| Token-bearing prevouts default to **vout=1** (dummy 546-sat BCH at vout=0) | `graph.py:135–167`. Spending those inputs is **not** genesis. |
| `kind=genesis_parent` always spends **prev_index=0** of a one-output funding tx | `graph.py:219–234`. `vout` on that spec is ignored. |
| `genesis_from` is a **vin index**, not `prevout.n` | `graph.py:283–286`; GEN-14 (`catalog.py:133–142`) is the only catalog row that documents the distinction. |
| Signing only if `spent.locking_bytecode == actor.p2pkh()` | `generator.py:116–125`, `158–164`. P2SH20/32/bare (`SCR-02..04`) cannot produce `partial_sigs`. |
| Commitment strings that look like hex are hex; otherwise UTF-8 | `graph.py:78–85`. Catalog `"id"` → `6964`; `"dead"` → `64656164`. Easy to mis-specify. |
| `TxOut.token is None` means “no 0x36” even if locking bytes already contain `0xEF` | `psbt/codec.py:329–330`; inject/raw_prefix paths set `token=None` (`graph.py:288–300`, `generator.py:72–75`). |
| Catalog `extra` keys `record_endianness`, `bcmr`, `raw_prefix_output`, `chip_prefix` are **no-ops** | Present only in `catalog.py:399,404,456,570`; **zero** references in `generator.py` / `graph.py`. BCMR-01 is just OP_RETURN + hybrid genesis. |
| `expected.json` is a **copy of generator output**, not an independent spec | `vectors/exporter.py:36–43`. |

---

## Hardcoded limits

| Limit | Where |
|---|---|
| NFT commitment consensus max **40 bytes** (Upgrade 9) | `cashtokens/prefix.py:26`; `consensus.py:65–69`; GEN-13 / NEG-07. NEG-07 text notes Upgrade 12 (May 2026) raises to 128 — **not implemented**. |
| FT amount max **2^63−1** | `prefix.py:25`; `consensus.py:125–131`; NEG-13 inject `amount_max_plus`. |
| NFT capability ∈ {none, mutable, minting} (0,1,2) | `prefix.py:27–28,89–91,137–138`; NEG-08 inject `cap3`. |
| Dummy padding output **546 sats** | `graph.py:145`, `173`, `261`. |
| Default values: funding 100_000, parent 50_000, existing 10_000, output 1000 | `graph.py:43,132,138,217,297`. |
| tx `version=2`, `sequence=0xFFFFFFFF`, `locktime=0` | `graph.py:46–56,310–314`. |
| Truncated PSBT keeps `max(6, len//2)` bytes | `generator.py:230–231`. |
| `sign_state=partial` signs **all but the last** input | `generator.py:170–171`. |
| Inject vocabulary is a closed dict of 8 gadgets | `generator.py:26–36`. |
| Dialects: `bip174-v0`, `bip370-v2`, `paytaca-145`, `bchn-v0` only | `psbt/codec.py:264–294`. |
| Paytaca GLOBAL_VERSION **145** uint32 LE; extra input-map `0x00` | `codec.py:270`, `146–148`, `203–206`. |
| `_paytaca_type_order`: JS array-index keys (`00` is **not** an index; `10` is) then the rest | `codec.py:63–82`. |
| Actors: alice/bob/carol/dave/change only | `keys.py:125`. |
| `decode_psbt` refuses `n_in==0 or n_out==0` | `codec.py:196–197`. Empty txs are unrepresentable as PSBTs. |

---

## vout=0 always-genesis confusion

CHIP rule in this tree is **unconditional**: every input with `prev_index == 0` contributes a genesis category (display-order txid of the spent tx).

```72:75:src/ctlab/cashtokens/consensus.py
    genesis_categories: list[str] = []
    for inp in inputs:
        if int(inp["prev_index"]) == 0:
            genesis_categories.append(_category_hex_from_outpoint_hash_internal(inp["prev_txid"]))
```

Same rule in `semantics.py:15–20`. There is **no** “only if the output actually creates tokens of that category” check in consensus (correct per CHIP: unused genesis is allowed). Semantics still **emits** a genesis record with `type: "empty"` for unused genesis (`semantics.py:79–89`).

Fixture layer **paper over** the rule so most token spends are not genesis:

- Comment at `graph.py:44`: funding vout=0 “can be a genesis input”.
- Comment at `graph.py:135–136`: default dummy BCH at vout=0 so the token at vout=1 is **not** a new genesis.
- `token_vouts[key] = 0 if dummy is None else 1` (`graph.py:167`).
- Token inputs use `spec.get("vout", g.token_vouts.get(key, 0))` (`graph.py:238`). The fallback **0** is genesis if `token_vouts` is missing.
- `kind=bch` with default `vout=0` **is** genesis-capable. Only `vout != 0` rebuilds a two-output parent (`graph.py:256–265`).
- `_apply_inject` picks category wire from **the first input whose `prev_index==0`**, not from `genesis_from` (`generator.py:64–68`). Fine for current NEG inject rows (single genesis_parent). Wrong if a dummy vout=0 BCH input were listed first.

**GEN-15** is the only catalog row that puts tokens at vout=0 (`catalog.py:143–152`, `extra.token_bearing_vout0`). Spending that UTXO genesises **category = parent txid** (`cc2ca1…` in `vectors/valid/GEN-15/vector.json:32–34,64–70`) **and** must conserve the old FT category (`643a0d…`). That is the CHIP “token-bearing vout=0” case, not “vout=0 is always a *used* genesis.”

**GEN-14** (`catalog.py:133–142`) is the complementary lesson: genesis is `prevout.n==0`, not `vin==0`.

---

## Burns: implicit in catalog, partial in `expected.json`

There is no burn opcode, burn output type, or catalog field `burn: true`. Burns are **omission of conservation**.

Titles that say burn: XGEN-06, POST-04, POST-09, POST-12, POST-15, POST-16 (`catalog.py:210–211,264,290,312,336,341`).

`expected.json` does **not** have a top-level `burns` array. Exporter writes:

```36:43:src/ctlab/vectors/exporter.py
        expected = {
            "consensus": v.get("expected_consensus"),
            "psbt": v.get("expected_psbt"),
            "semantics": v.get("semantics"),
            "invalid_code": v.get("invalid_code"),
            "txid": v.get("txid"),
        }
```

So burns appear only at `semantics.burns[]`, and the interpreter **always** sets `"implicit": true` (`semantics.py:136–154`).

Examples on disk:

- POST-09 immutable omit → `burns[0].nfts_dropped` + `implicit: true`
- POST-12 FT 100→1 → `ft_burned: 99`
- POST-15 hybrid burn FT keep NFT → `ft_burned: 50`
- POST-16 hybrid burn NFT keep FT → `nfts_dropped` of the immutable
- XGEN-06 genesis A + omit NFT B → burn on **B** only

**Gap:** POST-04 “Mint + burn baton” has `mint[0].baton = "burned"` and **`burns: []`** (`vectors/valid/POST-04/expected.json`). Dropped minting/mutable NFTs are not classified as `nfts_dropped` (heuristic is immutable-in vs immutable-out only, `semantics.py:138–145`). A signer that only reads `semantics.burns` will miss baton destruction.

---

## Same-category FT+NFT hybrid — representable, with a fixture catch

The in-memory model is one `Token` with `amount` **and** optional `nft` (`prefix.py:44–55`). That **is** a hybrid UTXO.

| Shape | How | Catalog |
|---|---|---|
| One output, NFT+FT | `HYB(cap, amt, commit)` | GEN-05, ENC-02, BCMR-01 |
| Split hybrid (NFT out + FT out, same category) | two outputs, `category_from_existing` | POST-13 |
| Merge NFT UTXO + FT UTXO → one hybrid | `_same_category_clone` so both sit on **one** parent tx at vout=1 and vout=2 | POST-14 (`catalog.py:324–335`; POST-11 same trick for FT+FT) |
| Hybrid transfer while genesis of another category | XGEN-03 | |

CHIP allows only **one NFT per output**; two NFTs of the same category need two outputs (GEN-06). That is representable.

Without `_same_category_clone`, two `existing` keys get two funding txids → two categories (`graph.py:129–167`). Same-category multi-input is **not** the default.

---

## Determinism

Intended sources of stability:

- Fixed `LAB_MNEMONIC` / paths (`__init__.py:19–24`, `keys.py:1–6,95–96`)
- Synthetic prevouts `double_sha256(b"ctlab-prevout|" + tag)` (`graph.py:17–19`)
- RFC6979 Schnorr with `extra_entropy=b""` (`signing/schnorr.py:27`)
- Paytaca key order is a pure function of type bytes (`codec.py:77–97`)
- `deepcopy` before mutation (`generator.py:136`)

Tests: `tests/golden/test_determinism.py` only checks GEN-01 unsigned identity, GEN-04 signed identity, and GEN-01 golden **txid**. No corpus-wide golden PSBT hashes.

Residual risk: double `build_fixture_graph` is deterministic **if** tags (`key`) are stable; `kind=bch` with `vout!=0` **mutates** `NamedTx` in place after first encode (`graph.py:258–264`). Re-running the same scenario is still stable; mixing graph objects across calls would not be.

---

## Decoder used as oracle (circular)

`generate_vector` encodes a PSBT, then:

```234:245:src/ctlab/vectors/generator.py
        try:
            decoded = decode_psbt(raw_psbt)
            if sc.get("duplicate_unsigned"):
                psbt_status = "invalid"
                ...
            if sc.get("omit_utxo"):
                psbt_status = "invalid"
                ...
        except PsbtError as e:
            decoded = None
            psbt_status = "invalid"
            psbt_error = e.code
```

`decoded` is **never read**. `actual_psbt` is “did our decoder accept our encoder?” plus a few scenario flags (`omit_utxo`, `tamper_0x36_amount`, `token_discrepancy` vs unsigned tx).

This is the same circularity `audits/architecture-map.md` already forbids: “Do not use generator output as the expected oracle for the same generator.” Independent oracles (Paytaca JS, libauth, BCHN) are **outside** this pipeline.

Consequences:

- Paytaca extra `0x00` and JS key order are accepted because **this** decoder special-cases them (`codec.py:203–221`).
- `PSBT-07` duplicate key: decoder `duplicate_key` **and** a forced flag — decoder is still the code that defines the error string.
- `omit_utxo`: BIP-174 bytes can be well-formed; invalidity is **policy**, not decode failure.
- Consensus `actual_*` is the in-tree CHIP clone, not libauth `verifyTransactionTokens` at generate time.
- `psbt_match` is almost a tautology: `psbt_status == expected or (expected == "valid" and status == "valid")` (`generator.py:301–304`).

On-disk drift: `catalog.py:537–543` sets SIG-06 `expected_psbt="valid"` (comment: envelope can be well-formed). `vectors/invalid/SIG-06/vector.json` has `expected_psbt`/`actual_psbt` **invalid**. Export is stale relative to current catalog+generator comments (`generator.py:200–201`).

---

## Catalog coverage vs requested axes

Catalog is ~80 `_e` rows (`GEN-01..15`, `XGEN-01..07`, `POST-01..16`, `NEG-01..16`, `ENC-01..04`, `PSBT-01..10`, `SIG-01..06`, `SCR-01..05`, `BCMR-01`). Most POST/NEG/ENC/SCR are **bip174-v0 + unsigned only**.

### vout=0 non-genesis — **gap**

| Have | Missing |
|---|---|
| Token at vout=1 (default): spend is not genesis | Spend **token-bearing vout=0** **without** creating tokens of the new category (unused genesis + conserve old). GEN-15 always genesises a new NFT. |
| BCH `vout=1` so fee inputs are not genesis (GEN-14, PSBT-10, NEG-05) | Named vector: `kind=bch` vout=0 **unused** genesis (PSBT-09 happens to do this but is a magic-byte test, not a consensus label). |
| GEN-15 token-bearing vout=0 **with** new genesis | Token at vout≥2 except the clone parent’s dummy+tokens layout. |

### Monster multi-category — **gap**

Largest mix is **XGEN-07** (existing FT B + NFT C + genesis A) = **3 categories** (`catalog.py:216–227`). GEN-08 is two genesis categories. No 5–10 category / many-input conservation stress, no many-baton mint storm.

### Minting — **partial**

Have: GEN-03/05/06 minting genesis; POST-01 preserve; POST-02 three mints; POST-03 downgrade; POST-04 burn baton; XGEN-04 genesis A + mint B; NEG-03/16 unsubstantiated minting.

Missing: minting baton **omitted with no successor NFT** (pure BCH outputs); hybrid **minting+FT** post-genesis (conserve FT, mint NFTs); large mint count; minting capability on a **non-vout-0** input that is also a genesis input (GEN-15 is FT, not a baton).

### Burn documented — **partial**

Documented in **titles** and in `semantics.burns` for immutable/FT omission. Not documented: explicit catalog flag; baton burn as a burn; mutable drop; unused-genesis vs burn confusion.

### Hybrid — **covered** for the single-output and split/merge cases (see above).

### Other holes

- Prefix inject negatives (NEG-08..15) are genesis txs with `token=None` + raw `0xEF…`; Paytaca **0x36 is omitted**.
- SCR-02/03/04 unsigned only; no redeem_script in PSBT (`codec.py` never writes `PSBT_IN_REDEEM_SCRIPT`).
- `force_sighash` ORs `0x20\|0x80` onto `ALL\|FORKID` (`generator.py:153–154`) rather than parsing a named `ALL\|FORKID\|UTXOS\|ANYONECANPAY`.
- No vector where `kind=token` overrides `vout` independently of `token_vouts`.

---

## Gap list (actionable)

1. **Circular PSBT oracle** — `actual_psbt` is self-decode of `encode_psbt`. Independent check belongs in differential tests, not `generate_vector`.
2. **`expected.json` is derived** — cannot detect generator regressions except via the tiny GEN-01 golden txid.
3. **Default existing UTXO vout=1** hides the genesis rule; only GEN-15 exercises token-bearing vout=0; **unused genesis of a token-bearing vout=0 is absent**.
4. **`token_vouts.get(key, 0)` fallback** would silently mark a token spend as genesis if the key were missing (`graph.py:238`).
5. **Same-category multi-UTXO requires a private extra** (`_same_category_clone`). Easy to generate consensus-invalid “merge” configs without it.
6. **Burns are implicit** and **baton burns are not in `semantics.burns`**.
7. **No monster multi-category** vector (cap is 3).
8. **Minting coverage** stops at a handful of NFTs; no “burn baton, emit only BCH”.
9. **Dialect default split** (`engine` Paytaca vs catalog BIP-174) will surprise custom JSON.
10. **Sign oracle is P2PKH-only**; script catalog rows do not test token sighash for P2SH.
11. **Catalog `extra` dead keys** (`bcmr`, `record_endianness`, `chip_prefix`, `raw_prefix_output`) look like coverage they do not provide.
12. **SIG-06 catalog vs exported vectors disagree** on `expected_psbt`.
13. **`_apply_inject` genesis = first `prev_index==0`**, not `genesis_from` — fragile if input order changes.
14. **Upgrade-12 128-byte commitment** is documented in NEG-07 only; encoder/consensus still cap at 40.

---

## Addendum (post-expansion, 2026-09-12)

Later work addressed several gaps without rewriting the pipeline:

| Gap | Status now |
| --- | --- |
| vout=0 ≠ genesis | `VOUT0-NO-GENESIS`, `VOUT0-MIXED`, `BCH-VOUT1`; tests in `tests/genesis/test_vout0.py` |
| Monster multi-category | `MONSTER-01`..`05` (genesis + vout1 tokens + burns + BCH vout1); Paytaca JS **18/18** including MONSTER-01 2907 B |
| Same-cat FT+NFT split | `SAMECAT-01` |
| Multi burn | `BURN-MULTI` |
| `expected.json` burns | exporter now writes top-level `genesis` / `mint` / `burns` as well as `semantics` |
| `generate(id, seed)` | `ctlab.engine.generate`; seed mixed into parent tags |
| Paytaca circular oracle | live `psbt.js` deserialize+serialize is the byte oracle (`compare_paytaca_real.py`) |

Still open from this audit: baton burn not in `semantics.burns`; `_same_category_clone` private extra; SIG-06 catalog vs export; dead `extra` keys; P2SH unsigned-only; BCHN; SeedCash live parse; unused genesis of token-bearing vout=0.
15. **0x36 vs unsigned-tx** check runs only for `dialect==paytaca-145` and `psbt_status==valid` (`generator.py:255–271`); inject invalids never test “UI trusts 0x36” because 0x36 is skipped when `token is None`.

---

## What is solid

- Consensus clone matches the CHIP conservation sketch: genesis iff `prev_index==0`; minting set = genesis ∪ minting inputs; FT cannot increase except at genesis; immutable matching + mutable downgrade (`consensus.py:72–187`).
- Semantics are derived from unsigned tx + source UTXOs, **not** from 0x36 (`semantics.py:1–4`).
- Hybrid is a first-class `Token` (amount + nft), including GEN-05.
- GEN-14 / GEN-15 exist specifically to un-confuse vin vs vout=0.
- Fixture graphs are self-contained (synthetic parents + `NON_WITNESS_UTXO`).
- Deterministic keys + RFC6979 make GEN-01/GEN-04 bit-stable when the graph tags do not change.
