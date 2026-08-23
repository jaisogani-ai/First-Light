/*
** NASA core Flight Software (cFS) Gate Application
** Pure C Deterministic 5-Step PCC Verifier Engine
*/

#include "gate_app.h"
#include <string.h>

PCC_GlobalState_t CFE_PCC_GlobalState = { .last_seq_no = 1042, .verified_count = 0, .rejected_count = 0 };

/* Mock SHA256 for standalone / cFS environment */
static void Mock_SHA256(const uint8 *pData, uint16 Len, uint8 *pOutHash)
{
    memset(pOutHash, 0, 32);
    for (uint16 i = 0; i < Len; i++) {
        pOutHash[i % 32] ^= pData[i];
    }
}

/* Mock Signature Check */
static int32 Mock_VerifySig(const PCC_Cert_t *pCert)
{
    /* In actual cFS: Ed25519 or HMAC-SHA256 signature verification */
    if (pCert->signature[0] == 0xFF && pCert->signature[1] == 0xFF) {
        return -1; // Forged signature marker
    }
    return 0; // Valid
}

int32 PCC_VerifyCommand(PCC_Cert_t *pCert, const uint8 *pCmdBytes, uint16 CmdLen)
{
    /* Step 1: Sequence Number & Freshness Check */
    if (pCert->sequence_no <= CFE_PCC_GlobalState.last_seq_no) {
        CFE_PCC_GlobalState.rejected_count++;
        return PCC_VERIFY_REPLAY_FAIL;
    }

    /* Step 2: Command Hash Verification */
    uint8 computed_hash[32];
    Mock_SHA256(pCmdBytes, CmdLen, computed_hash);
    if (memcmp(computed_hash, pCert->command_hash, 32) != 0) {
        CFE_PCC_GlobalState.rejected_count++;
        return PCC_VERIFY_HASH_MISMATCH;
    }

    /* Step 3: Signature Verification */
    if (Mock_VerifySig(pCert) != 0) {
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
