/* Original owned data declaration candidate, pending root admission.
 * Requires the independently owned cache_property.h type declarations.
 * No retained private overlay, helper body or function implementation.
 * Actual candidate size/alignment, publication and rundown must be proved.
 */
#pragma once

typedef struct nx_cache_worker_handoff_proposal {
    nx_lcq_result completed_result;
    uint32_t readiness;
} nx_cache_worker_handoff_proposal;
