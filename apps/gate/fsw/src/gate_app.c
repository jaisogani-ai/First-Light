/*
** NASA core Flight Software (cFS) Gate Application
** Main App Entry Point & Software Bus Interface
*/

#include "gate_app.h"
#include "pcc_crypto.h"
#include <string.h>
#include <stddef.h>

/* Same demo key used in gate_verify.c's PCC_VerifySignature. */
extern int32 PCC_VerifyCommand(PCC_Cert_t *pCert, const uint8 *pCmdBytes, uint16 CmdLen);
static const uint8 PCC_DEMO_HMAC_KEY_LOCAL[] = "NASA_cFS_PCC_DEMO_KEY_DO_NOT_USE_IN_FLIGHT";

void PCC_GateAppMain(void)
{
    int32 status;
    PCC_Cert_t cert;
    uint8 dummy_cmd[16] = { 'R', 'C', 'S', '_', '0', '0', '4', '2' };

    CFE_EVS_SendEvent(PCC_INIT_INF_EVID, CFE_EVS_EventType_INFORMATION, "PCC Gate App Initialized. Subscribed to MID 0x%04X", PCC_CMD_RAW_MID);

    /* Sample execution tick — the certificate below is deliberately valid so this call
       demonstrates a real ACCEPT; multipliers/constraints mirror the box-constraint binding
       construction in producer/rules.py rather than being independently made up. */
    memset(&cert, 0, sizeof(cert));
    strncpy(cert.command_id, "RCS_PULSE_0043", 32);
    cert.sequence_no = 1043;
    cert.model_version = 1;
    cert.constraint_count = 1;
    cert.multipliers[0] = 1.0f;
    cert.constraint_values[0] = -0.039f;
    cert.contradiction_const = 0.0f;

    /* Real SHA-256 over the actual command bytes, then real HMAC-SHA256 over the fixed-layout
       certificate fields (everything before `signature`) — matches gate_verify.c's check. */
    PCC_SHA256(dummy_cmd, 8, cert.command_hash);
    PCC_HMAC_SHA256(PCC_DEMO_HMAC_KEY_LOCAL, sizeof(PCC_DEMO_HMAC_KEY_LOCAL) - 1,
                     (const uint8 *)&cert, offsetof(PCC_Cert_t, signature), cert.signature);

    status = PCC_VerifyCommand(&cert, dummy_cmd, 8);

    if (status == PCC_SUCCESS) {
        CFE_EVS_SendEvent(PCC_VERIFY_INF_EVID, CFE_EVS_EventType_INFORMATION, "PCC: Command %s VERIFIED. Republishing to MID 0x%04X", cert.command_id, PCC_CMD_EXEC_MID);
    } else {
        CFE_EVS_SendEvent(PCC_ERR_EVID, CFE_EVS_EventType_ERROR, "PCC: Command %s REJECTED with code %d", cert.command_id, status);
    }
}
