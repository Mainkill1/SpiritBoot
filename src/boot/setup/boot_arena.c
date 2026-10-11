/* SPDX-License-Identifier: GPL-2.0-or-later
 * Boot coordinator primitive. Link OUTSIDE the overlay being retired.
 * Executing stack and release callback must also remain outside that region.
 */
#include "boot_setup.h"

static bool overlaps(uintptr_t p, size_t n, uintptr_t first, uintptr_t end)
{
    if (n > UINTPTR_MAX-p) return true;
    return p < end && p+n > first;
}

bool sb_boot_arena_retire(SbBootArena *a, const SbArenaOps *ops)
{
    uintptr_t first, end;
    volatile unsigned char *p;
    if (!a) return false;
    if (a->state == SB_ARENA_RELEASED) return a->base == NULL && a->bytes == 0;
    if (!a->base || !a->bytes || (unsigned)a->state > SB_ARENA_SCRUBBED) return false;
    first=(uintptr_t)a->base;
    if ((first & (SB_PAGE_SIZE-1u)) || (a->bytes & (SB_PAGE_SIZE-1u)) ||
        a->bytes > UINTPTR_MAX-first) return false;
    end=first+a->bytes;
    if (!ops || overlaps((uintptr_t)a,sizeof(*a),first,end) ||
        overlaps((uintptr_t)ops,sizeof(*ops),first,end)) return false;
    if (ops->context && overlaps((uintptr_t)ops->context,1,first,end)) return false;
    if (!ops->release || (a->state == SB_ARENA_LIVE && !ops->quiesce)) return false;
    if (a->state == SB_ARENA_LIVE) {
        if (!ops->quiesce(ops->context,a->base,a->bytes)) return false;
        a->state=SB_ARENA_QUIESCED;
    }
    if (a->state == SB_ARENA_QUIESCED) {
        p=a->base;
        for (size_t i=0; i<a->bytes; ++i) p[i]=0;
        a->state=SB_ARENA_SCRUBBED;
    }
    /* If allocator release fails, do not re-enter already scrubbed menu code. */
    if (!ops->release(ops->context,a->base,a->bytes)) return false;
    a->base=NULL;
    a->bytes=0;
    a->state=SB_ARENA_RELEASED;
    return true;
}
