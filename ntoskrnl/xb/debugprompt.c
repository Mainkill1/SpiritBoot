/* SPDX-License-Identifier: GPL-2.0-or-later
 * Public nxdk DbgPrompt character count; existing RTL/KD debug transport.
 */
#include <ntoskrnl.h>
ULONG NTAPI XeDbgPrompt(PCCH Prompt, PCH Response, ULONG MaximumResponseLength)
{
    ULONG length;
    STRING output, input;
    extern ULONG NTAPI DebugPrompt(PSTRING, PSTRING);
    if (MaximumResponseLength == 0 || Response == NULL) return 0;
    Response[0] = '\0';
#if DBG
    extern BOOLEAN NTAPI NxkDebuggerPromptAvailable(VOID);
    if (!NxkDebuggerPromptAvailable()) return 0;
#else
    return 0; /* release omits all debugger input transport */
#endif
    if (!KdDebuggerEnabled || KdDebuggerNotPresent || Prompt == NULL) return 0;
    /* The transport STRING length is a USHORT; never let it wrap. The
     * existing prompt transport caps its packet buffer as well. */
    if (MaximumResponseLength > 0xFFFF) MaximumResponseLength = 0xFFFF;
    for (length = 0; length < 0xFFFF && Prompt[length]; ++length) ;
    output.Buffer = (PCHAR)Prompt; output.Length = (USHORT)length;
    output.MaximumLength = (USHORT)length;
    input.Buffer = Response; input.Length = 0;
    input.MaximumLength = (USHORT)MaximumResponseLength;
    length = DebugPrompt(&output, &input);
    return length <= MaximumResponseLength ? length : MaximumResponseLength;
}
