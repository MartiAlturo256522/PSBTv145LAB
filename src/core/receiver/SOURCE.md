# Local receiver source

`psbt_parser.py` is adapted from the user's local SeedCash PSBT parser and
transaction models. SeedCash copyright and original terms are preserved in
`LICENSE`; copying the source does not relicense it.

The adaptation replaces wallet-wide Bip44 imports with this project's CashAddr
encoder. It retains the receiver's v145 uint32 version and separator fixes.
QR text processing uses the project's licensed Python UR helpers. Hardware,
wallet storage, seed generation, camera capture, and device views are excluded.
No external SeedCash checkout, installation, or source path is required.
