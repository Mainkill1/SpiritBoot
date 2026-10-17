/* SPDX-License-Identifier: GPL-2.0-or-later
 * GPL ReactOS production excerpts, retaining the source's COPYING terms.
 * PROGRAMMER: Alex Ionescu (ReactOS kernel); sem.c also Thomas Weidenmueller.
 * Original paths / pinned Git blobs:
 * ntoskrnl/ex/sem.c d44eccd3aa2bba941477cd0404e76e1c0edebfe8
 * ntoskrnl/ke/semphobj.c 516ea5054fe68c73fbc974fa393b0a24f80d5b6f
 * ntoskrnl/ex/harderr.c 8ac2b106f2b3252a454c88a0bd0a57eefc6e369b
 * Unchanged function excerpts are a portable test input, never a second algorithm.
 */

/*
 * @implemented
 */
NTSTATUS
NTAPI
NtReleaseSemaphore(IN HANDLE SemaphoreHandle,
                   IN LONG ReleaseCount,
                   OUT PLONG PreviousCount OPTIONAL)
{
    KPROCESSOR_MODE PreviousMode = ExGetPreviousMode();
    PKSEMAPHORE Semaphore;
    NTSTATUS Status;
    PAGED_CODE();

    /* Check if we were called from user-mode */
    if ((PreviousCount) && (PreviousMode != KernelMode))
    {
        /* Entry SEH Block */
        _SEH2_TRY
        {
            /* Make sure the state pointer is valid */
            ProbeForWriteLong(PreviousCount);
         }
        _SEH2_EXCEPT(EXCEPTION_EXECUTE_HANDLER)
        {
            /* Return the exception code */
            _SEH2_YIELD(return _SEH2_GetExceptionCode());
        }
        _SEH2_END;
    }

    /* Make sure count makes sense */
    if (ReleaseCount <= 0)
    {
        DPRINT("Invalid Release Count\n");
        return STATUS_INVALID_PARAMETER;
    }

    /* Get the Object */
    Status = ObReferenceObjectByHandle(SemaphoreHandle,
                                       SEMAPHORE_MODIFY_STATE,
                                       ExSemaphoreObjectType,
                                       PreviousMode,
                                       (PVOID*)&Semaphore,
                                       NULL);

    /* Check for success */
    if (NT_SUCCESS(Status))
    {
        /* Enter SEH Block */
        _SEH2_TRY
        {
            /* Release the semaphore */
            LONG PrevCount = KeReleaseSemaphore(Semaphore,
                                                IO_NO_INCREMENT,
                                                ReleaseCount,
                                                FALSE);

            /* Return the old count if requested */
            if (PreviousCount) *PreviousCount = PrevCount;
        }
        _SEH2_EXCEPT(ExSystemExceptionFilter())
        {
            /* Get the exception code */
            Status = _SEH2_GetExceptionCode();
        }
        _SEH2_END;

        /* Dereference the Semaphore */
        ObDereferenceObject(Semaphore);
    }

    /* Return Status */
    return Status;
}

/*
 * @implemented
 */
LONG
NTAPI
KeReleaseSemaphore(IN PKSEMAPHORE Semaphore,
                   IN KPRIORITY Increment,
                   IN LONG Adjustment,
                   IN BOOLEAN Wait)
{
    LONG InitialState, State;
    KIRQL OldIrql;
    PKTHREAD CurrentThread;
    ASSERT_SEMAPHORE(Semaphore);
    ASSERT_IRQL_LESS_OR_EQUAL(DISPATCH_LEVEL);

    /* Lock the Dispatcher Database */
    OldIrql = KiAcquireDispatcherLock();

    /* Save the Old State and get new one */
    InitialState = Semaphore->Header.SignalState;
    State = InitialState + Adjustment;

    /* Check if the Limit was exceeded */
    if ((Semaphore->Limit < State) || (InitialState > State))
    {
        /* Raise an error if it was exceeded */
        KiReleaseDispatcherLock(OldIrql);
        ExRaiseStatus(STATUS_SEMAPHORE_LIMIT_EXCEEDED);
    }

    /* Now set the new state */
    Semaphore->Header.SignalState = State;

    /* Check if we should wake it */
    if (!(InitialState) && !(IsListEmpty(&Semaphore->Header.WaitListHead)))
    {
        /* Wake the Semaphore */
        KiWaitTest(&Semaphore->Header, Increment);
    }

    /* Check if the caller wants to wait after this release */
    if (Wait == FALSE)
    {
        /* Release the Lock */
        KiReleaseDispatcherLock(OldIrql);
    }
    else
    {
        /* Set a wait */
        CurrentThread = KeGetCurrentThread();
        CurrentThread->WaitNext = TRUE;
        CurrentThread->WaitIrql = OldIrql;
    }

    /* Return the previous state */
    return InitialState;
}

/*++
 * @name ExSystemExceptionFilter
 * @implemented
 *
 * TODO: Add description
 *
 * @return FILLME
 *
 * @remarks None
 *
 *--*/
LONG
NTAPI
ExSystemExceptionFilter(VOID)
{
    return KeGetPreviousMode() != KernelMode ?
           EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH;
}
