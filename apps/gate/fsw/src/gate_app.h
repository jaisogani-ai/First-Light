/*
** NASA core Flight Software (cFS) Gate Application Header
** Proof-Carrying Commands (PCC) v1.1 Substrate
*/

#ifndef _gate_app_h_
#define _gate_app_h_

#include "cfe.h"

/* Message ID Definitions */
#define PCC_CMD_RAW_MID      0x1808
#define PCC_CMD_EXEC_MID     0x1809
#define PCC_GATE_APP_PERF_ID 32

/* Event IDs */
#define PCC_INIT_INF_EVID    1
#define PCC_VERIFY_INF_EVID  2
#define PCC_ERR_EVID         3

/* Verification Return Codes */
#define PCC_SUCCESS                    0
#define PCC_VERIFY_REPLAY_FAIL        -1
#define PCC_VERIFY_HASH_MISMATCH      -2
#define PCC_VERIFY_SIG_FAIL           -3
#define PCC_VERIFY_MODEL_FAIL         -4
#define PCC_VERIFY_FARKAS_INVALID     -5
#define PCC_VERIFY_FARKAS_NEGATIVE    -6

#define PCC_EXPECTED_MODEL_VERSION    1
#define PCC_MAX_MULTI_COUNT           8

/* PCC Farkas Certificate Structure */
typedef struct {
    char     command_id[32];
    uint8    command_hash[32];
    uint32   sequence_no;
    uint32   model_version;
    uint16   constraint_count;
    float    multipliers[PCC_MAX_MULTI_COUNT];
    float    constraint_values[PCC_MAX_MULTI_COUNT];
    float    contradiction_const;
    uint8    signature[32];
} PCC_Cert_t;

/* Global State Structure */
typedef struct {
    uint32   last_seq_no;
    uint32   verified_count;
    uint32   rejected_count;
} PCC_GlobalState_t;

extern PCC_GlobalState_t CFE_PCC_GlobalState;

/* Function Prototypes */
void  PCC_GateAppMain(void);
int32 PCC_VerifyCommand(PCC_Cert_t *pCert, const uint8 *pCmdBytes, uint16 CmdLen);

#endif /* _gate_app_h_ */
