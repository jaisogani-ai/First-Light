/*
** NASA core Flight Software (cFS) Gate Application
** Pure C Deterministic 5-Step PCC Verifier Engine — reference implementation.
**
** Mirrors backend/verifier.py's checks using real SHA-256/HMAC-SHA256 (see pcc_crypto.c),
** not the XOR/marker mocks the earlier version of this file used. It has not been built or
** exercised under a live NASA cFE/Software Bus instance in this repository — see the cFS
** integration note in README.md for exactly what was and wasn't achieved and why.
*/

#include "gate_app.h"
#include "pcc_crypto.h"
#include <string.h>
#include <stddef.h>

/* Genesis sequence number — arbitrary but documented (matches backend/constants.py's
   INITIAL_SEQUENCE_NO=1000; the sample cert below uses 1001). */
PCC_GlobalState_t CFE_PCC_GlobalState = { .last_seq_no = 1000, .verified_count = 0, .rejected_count = 0 };

/* Demo-only shared key. A flight build would source this from a provisioned key store, not
   a compiled-in constant — this mirrors backend/config.py's HMAC_SECRET_KEY for the demo. */
static const uint8 PCC_DEMO_HMAC_KEY[] = "NASA_cFS_PCC_DEMO_KEY_DO_NOT_USE_IN_FLIGHT";

static int32 PCC_VerifySignature(const PCC_Cert_t *pCert)
{
    uint8 expected[32];
    /* Signs the fixed-layout certificate fields as raw bytes (a flight build would sign the
       canonical serialized payload, matching the Python producer's JSON-based signing). */
    PCC_HMAC_SHA256(PCC_DEMO_HMAC_KEY, sizeof(PCC_DEMO_HMAC_KEY) - 1,
                     (const uint8 *)pCert, offsetof(PCC_Cert_t, signature), expected);
    return memcmp(expected, pCert->signature, 32) == 0 ? 0 : -1;
}

int32 PCC_VerifyCommand(PCC_Cert_t *pCert, const uint8 *pCmdBytes, uint16 CmdLen)
{
    /* Step 1: Sequence Number & Freshness Check */
    if (pCert->sequence_no <= CFE_PCC_GlobalState.last_seq_no) {
        CFE_PCC_GlobalState.rejected_count++;
        return PCC_VERIFY_REPLAY_FAIL;
    }

    /* Step 2: Command Hash Verification (real SHA-256) */
    uint8 computed_hash[32];
    PCC_SHA256(pCmdBytes, CmdLen, computed_hash);
    if (memcmp(computed_hash, pCert->command_hash, 32) != 0) {
        CFE_PCC_GlobalState.rejected_count++;
        return PCC_VERIFY_HASH_MISMATCH;
    }

    /* Step 3: Signature Verification (real HMAC-SHA256) */
    if (PCC_VerifySignature(pCert) != 0) {
        CFE_PCC_GlobalState.rejected_count++;
        return PCC_VERIFY_SIG_FAIL;
    }

    /* Step 4: Model Version Provenance Check */
    if (pCert->model_version != PCC_EXPECTED_MODEL_VERSION) {
        CFE_PCC_GlobalState.rejected_count++;
        return PCC_VERIFY_MODEL_FAIL;
    }

    /* Step 5: Farkas Linear Combination Arithmetic Check */
    float sum = 0.0f;
    for (int i = 0; i < pCert->constraint_count; i++) {
        if (pCert->multipliers[i] < 0.0f) {
            CFE_PCC_GlobalState.rejected_count++;
            return PCC_VERIFY_FARKAS_NEGATIVE;
        }
        sum += pCert->multipliers[i] * pCert->constraint_values[i];
    }

    /* Contradiction requires sum + constant < 0 */
    if ((sum + pCert->contradiction_const) >= 0.0f) {
        CFE_PCC_GlobalState.rejected_count++;
        return PCC_VERIFY_FARKAS_INVALID;
    }

    /* PASS: Update sequence number and state */
    CFE_PCC_GlobalState.last_seq_no = pCert->sequence_no;
    CFE_PCC_GlobalState.verified_count++;
    return PCC_SUCCESS;
}
