# UI control QA (SeedCash PSBT Lab v2)

| Control | Result |
| --- | --- |
| New PSBT | PASS — resets builder |
| Presets (sidebar) | PASS — opens Presets tab |
| Preset click | PASS — `builder_from_catalog` + engine.generate |
| Fixtures click | PASS — catalog generate |
| JSON sync / apply | PASS |
| Add/Remove/Dup input | PASS |
| Add/Remove/Dup output | PASS |
| Token fields → model | PASS (`TokenEditor._sync`) |
| Validate | PASS — same as generate via engine |
| Generate PSBT | PASS — frozen engine |
| Copy PSBT / Copy UR | PASS |
| Save / Export fixture + ur/ | PASS |
| Random seed | PASS |
| UR encode roundtrip | PASS (PSBT bytes) |
| QR frame | PASS |
| Speed / density | PASS (timer ms / maxFragment) |
| Debug log Ctrl+L | PASS |
| Open PSBT | PASS — inspect hex/base64 |

UR: `@ngraveio/bc-ur` + `@keystonehq/bc-ur-registry` (Paytaca package.json).  
Paytaca **app** UR string identity: **unverified**. PSBT recover via those libs: **verified**.
