/*
** Self-contained SHA-256 / HMAC-SHA256 for the PCC Gate reference verifier.
**
** This is a REFERENCE implementation: it demonstrates the same cryptographic checks as
** backend/verifier.py (Python) using real SHA-256/HMAC arithmetic, not the mock XOR/marker
** checks the previous version of this file used. It has NOT been built or run under NASA
** cFE/OSAL in this repository (see the cFS integration note in README.md) — it compiles as
** standalone C with no cFS dependency so it can be unit-tested on its own.
*/

#ifndef _pcc_crypto_h_
#define _pcc_crypto_h_

#include <stdint.h>
#include <stddef.h>

void PCC_SHA256(const uint8_t *data, size_t len, uint8_t out[32]);
void PCC_HMAC_SHA256(const uint8_t *key, size_t key_len, const uint8_t *data, size_t data_len, uint8_t out[32]);

#endif /* _pcc_crypto_h_ */
