# Reviewed input changes

## 2026-09-20: checkout normalization only

No reviewed content was changed or re-pinned. No supplemental sample file was needed: this task changes ordering, not enrichment. Existing deterministic SAMPLE rows and the fixed sample clock are unchanged.

| File | Old reviewed SHA-256 | New reviewed SHA-256 | Exactly what changed and why |
| --- | --- | --- | --- |
| `docs/research/enriched_commercial_sample.json` | `b9ff27965e2716abab313f840de903191617c4da24d8fd8df7bf999c868bcd2e` | Same | `.gitattributes` enforces LF. Restored the clean checkout from CRLF to its original Git blob bytes so `load_release_sample` can validate it. |
| `docs/research/btx_original_workbook_references.json` | `d0e4a1ca28d5f6ec38edd457b81fe98177d5b9d5396ac582b6bf34e9901e55d7` | Same | `.gitattributes` enforces LF. Restored the clean checkout from CRLF to its original Git blob bytes so `load_private_reference_fields` can validate it. |
| `backend/tests/fixtures/g17-ip-sa-20260908.txt` | `e8f510e4ade5b3d0d2c43a1339185494c0996f4b2678ca810579caf9869791c3` | Same | `.gitattributes` enforces LF for the existing checksummed historical public test excerpt used by `backend/tests/prepare_e2e.py`. No market observations changed. |

Verification uses SHA-256 of `git show HEAD:<path>` bytes, compared with working-tree bytes and the existing loader constants. All three match after normalization. Original CRLF checkout hashes were respectively `a30c8966f964dd3cdd334e52d54c9496110508bfb0e81165fbdad1dadf457c1a`, `508ebafd032c652b4ef3c3b34006ca94d9dede0f9292dd1d9753aba11a1fa61a`, and `58b9c250933b8a752ad6c0f655d2d79994662ac34bfbaa33c5a96228ce27af9b`.

The earlier baseline recorded system `core.autocrlf=true`. On this continuation, the repository configuration reports `core.autocrlf=input`; the previously checked-out files remained CRLF. No Git configuration was changed by this task. Explicit attributes make these inputs independent of that setting.

No re-pin process was necessary. The repository's existing local setup process, `backend/tests/prepare_e2e.py`, is used for browser fixtures. Every backend test, including consumers of these inputs, is rerun; final outcomes are in `TODAY_PRIORITY_FINAL_2026-09-20.md`.
