"""CashTokens PSBT Test Vector Laboratory.

Layers are intentionally separate:

1. CashTokens consensus semantics
2. CashTokens token-prefix serialization
3. Bitcoin Cash transaction serialization
4. BCH sighash / signing serialization
5. PSBT envelope serialization (BIP-174 / BIP-370)
6. Paytaca PSBT v145 dialect (NOT a BIP standard)
7. Wallet-specific metadata
8. SeedSigner / SeedCash parser representation
"""

__version__ = "0.1.0"
GENERATOR_VERSION = "0.1.0"

# Deterministic laboratory seed. Changing this invalidates golden vectors.
LAB_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon about"
)
LAB_PASSPHRASE = ""
LAB_COIN_TYPE = 145  # BIP-44 Bitcoin Cash. NOT a PSBT version.
LAB_ACCOUNT = 0
LAB_NETWORK_PREFIX = "bitcoincash"
