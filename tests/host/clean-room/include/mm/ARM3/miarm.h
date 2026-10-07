#pragma once
static inline KIRQL MiAcquirePfnLock(void) { return 0; }
static inline void MiReleasePfnLock(KIRQL irql) { (void)irql; }
void NxkPageSupplyReturn(PFN_NUMBER Page);
