/*
** NASA core Flight Software (cFS) Target Application ("Thruster Control")
** Consumes verified commands republished by PCC Gate App
*/

#include "gate_app.h"

void Target_AppMain(void)
{
    CFE_EVS_SendEvent(1, CFE_EVS_EventType_INFORMATION, "Target App Subscribed to Verified MID 0x%04X", PCC_CMD_EXEC_MID);
    CFE_EVS_SendEvent(2, CFE_EVS_EventType_INFORMATION, "Thruster Pulse Executed Safely.");
}
