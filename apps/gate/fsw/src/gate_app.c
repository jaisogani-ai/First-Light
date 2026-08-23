/*
** NASA core Flight Software (cFS) Gate Application
** Main App Entry Point & Software Bus Interface
*/

#include "gate_app.h"

void PCC_GateAppMain(void)
{
    int32 status;
    PCC_Cert_t cert;
    uint8 dummy_cmd[16] = { 'R', 'C', 'S', '_', '0', '0', '4', '2' };

    CFE_EVS_SendEvent(PCC_INIT_INF_EVID, CFE_EVS_EventType_INFORMATION, "PCC Gate App Initialized. Subscribed to MID 0x%04X", PCC_CMD_RAW_MID);

    /* Sample execution tick */
    memset(&cert, 0, sizeof(cert));
    strncpy(cert.command_id, "RCS_PULSE_0043", 32);
    cert.sequence_no = 1043;
    cert.model_version = 1;
    cert.constraint_count = 3;
    cert.multipliers[0] = 0.62f; cert.multipliers[1] = 0.0f; cert.multipliers[2] = 1.0f;
    cert.constraint_values[0] = 0.01f; cert.constraint_values[1] = 0.01f; cert.constraint_values[2] = 0.00f;
    cert.contradiction_const = -0.014f;

    /* Compute mock matching hash */
    for (int i = 0; i < 8; i++) cert.command_hash[i] = dummy_cmd[i];

    status = PCC_VerifyCommand(&cert, dummy_cmd, 8);

    if (status == PCC_SUCCESS) {
        CFE_EVS_SendEvent(PCC_VERIFY_INF_EVID, CFE_EVS_EventType_INFORMATION, "PCC: Command %s VERIFIED. Republishing to MID 0x%04X", cert.command_id, PCC_CMD_EXEC_MID);
    } else {
        CFE_EVS_SendEvent(PCC_ERR_EVID, CFE_EVS_EventType_ERROR, "PCC: Command %s REJECTED with code %d", cert.command_id, status);
    }
}
