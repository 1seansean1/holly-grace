---- MODULE KernelInvariants ----
(******************************************************************************)
(* TLA+ specification of the KernelContext state machine and K1-K8 invariant  *)
(* enforcement gates for the Holly Grace kernel.                              *)
(*                                                                            *)
(* Traces to:                                                                 *)
(*   Behavior Spec SS1.1  KernelContext state machine (states + transitions)  *)
(*   Behavior Spec SS1.2  K1 Schema Validation                                *)
(*   Behavior Spec SS1.3  K2 Permission Gates                                 *)
(*   Behavior Spec SS1.4  K3 Bounds Checking                                  *)
(*   Behavior Spec SS1.5  K4 Trace Injection                                  *)
(*   Behavior Spec SS1.6  K5 Idempotency Key Generation                       *)
(*   Behavior Spec SS1.7  K6 Durability / WAL                                 *)
(*   Behavior Spec SS1.8  K7 HITL Gates                                       *)
(*   Behavior Spec SS1.9  K8 Eval Gates                                       *)
(*   FMEA-K001-K109       docs/FMEA_Kernel_Invariants.md                      *)
(*   Task 14.1            docs/Task_Manifest.md                               *)
(*   SIL 3               docs/SIL_Classification_Matrix.md                   *)
(*                                                                            *)
(* State machine (Behavior Spec SS1.1):                                       *)
(*   IDLE     -> ENTERING : __aenter__() called; correlation_id assigned      *)
(*   ENTERING -> ACTIVE   : all K1-K8 gates pass                              *)
(*   ENTERING -> FAULTED  : any gate fails; exception raised to caller        *)
(*   ACTIVE   -> EXITING  : operation completes normally                      *)
(*   ACTIVE   -> FAULTED  : async cancellation or K8 eval gate failure        *)
(*   EXITING  -> IDLE     : __aexit__() completes; WAL entry written          *)
(*   EXITING  -> FAULTED  : exit gate failure (WAL write error)               *)
(*   FAULTED  -> IDLE     : exception consumed by caller                      *)
(*                                                                            *)
(* Modelling assumptions (explicit, per Behavior Spec SS1.1 acceptance):      *)
(*   A1. Single KernelContext instance (one async task, one boundary crossing)*)
(*       Re-entrancy prevention is enforced externally (not modelled here).   *)
(*   A2. Gates K1-K8 are nondeterministic: each may independently pass/fail.  *)
(*   A3. AllGatesPass assigns the complete gate set atomically. The spec does  *)
(*       not model per-gate intermediate states (K1 -> K2 -> ... -> K8);      *)
(*       per-gate sub-state machines are specified in Behavior Spec SS1.2-1.9.*)
(*   A4. WAL write in EXITING is nondeterministic (may succeed or fail).      *)
(*   A5. HALTED is treated as a FAULTED sub-state (K8 eval gate failure maps  *)
(*       to FAULTED; the distinction is captured in the FMEA).                *)
(*   A6. Exception propagation is modelled as exc_raised=TRUE persisting in   *)
(*       FAULTED until ExceptionConsumed fires.                               *)
(******************************************************************************)

EXTENDS Naturals, FiniteSets, TLC

CONSTANT GATES  \* Instantiated as {"K1","K2","K3","K4","K5","K6","K7","K8"}

(******************************************************************************)
(* State set (Behavior Spec SS1.1 Table 1)                                    *)
(******************************************************************************)
KernelStates == {"IDLE", "ENTERING", "ACTIVE", "EXITING", "FAULTED"}

(******************************************************************************)
(* Variables                                                                  *)
(******************************************************************************)
VARIABLES
    kstate,       \* Current KernelContext state in KernelStates
    gates_passed, \* Set of gates that ran and passed (subset of GATES)
    gates_failed, \* Set of gates that ran and failed (subset of GATES)
    wal_written,  \* TRUE iff WAL entry persisted for this boundary crossing
    corr_id,      \* TRUE iff correlation_id assigned for this crossing (K4)
    exc_raised    \* TRUE iff exception is pending to the caller

vars == <<kstate, gates_passed, gates_failed, wal_written, corr_id, exc_raised>>

(******************************************************************************)
(* Type invariant                                                             *)
(******************************************************************************)
TypeOK ==
    /\ kstate       \in KernelStates
    /\ gates_passed \in SUBSET GATES
    /\ gates_failed \in SUBSET GATES
    /\ gates_passed \cap gates_failed = {}   \* gate cannot both pass and fail
    /\ wal_written  \in BOOLEAN
    /\ corr_id      \in BOOLEAN
    /\ exc_raised   \in BOOLEAN

(******************************************************************************)
(* Initial state                                                              *)
(******************************************************************************)
Init ==
    /\ kstate       = "IDLE"
    /\ gates_passed = {}
    /\ gates_failed = {}
    /\ wal_written  = FALSE
    /\ corr_id      = FALSE
    /\ exc_raised   = FALSE

(******************************************************************************)
(* Actions                                                                    *)
(******************************************************************************)

\* ── IDLE → ENTERING ──────────────────────────────────────────────────────────
\* Caller invokes __aenter__(). K4 assigns correlation_id during ENTERING.
\* Resets per-crossing state from any prior successful exit.
Aenter ==
    /\ kstate = "IDLE"
    /\ kstate'       = "ENTERING"
    /\ gates_passed' = {}
    /\ gates_failed' = {}
    /\ wal_written'  = FALSE
    /\ corr_id'      = TRUE        \* K4: correlation_id assigned on entry
    /\ exc_raised'   = FALSE

\* ── ENTERING → ACTIVE ────────────────────────────────────────────────────────
\* All K1-K8 gates evaluate and pass (Behavior Spec SS1.1 INV-5).
\* The full GATES set is assigned atomically (modelling assumption A3).
AllGatesPass ==
    /\ kstate = "ENTERING"
    /\ kstate'       = "ACTIVE"
    /\ gates_passed' = GATES
    /\ gates_failed' = {}
    /\ wal_written'  = wal_written
    /\ corr_id'      = corr_id
    /\ exc_raised'   = FALSE

\* ── ENTERING → FAULTED ───────────────────────────────────────────────────────
\* A gate fails. Nondeterministically choose any gate not yet passed.
\* In practice gates_passed = {} at this point; the existential captures all
\* failure scenarios. Exception propagates to caller (FM-001-2 mitigation).
GateFails ==
    /\ kstate = "ENTERING"
    /\ \E g \in (GATES \ gates_passed) :
           /\ gates_failed' = gates_failed \cup {g}
           /\ gates_passed' = gates_passed
    /\ kstate'      = "FAULTED"
    /\ exc_raised'  = TRUE
    /\ wal_written' = wal_written
    /\ corr_id'     = corr_id

\* ── ACTIVE → EXITING ─────────────────────────────────────────────────────────
\* Boundary operation completes normally. WAL not yet finalized.
OperationComplete ==
    /\ kstate = "ACTIVE"
    /\ kstate'       = "EXITING"
    /\ gates_passed' = gates_passed
    /\ gates_failed' = gates_failed
    /\ wal_written'  = wal_written
    /\ corr_id'      = corr_id
    /\ exc_raised'   = exc_raised

\* ── ACTIVE → FAULTED ─────────────────────────────────────────────────────────
\* Async cancellation (CancelledError) or K8 eval gate failure (HALTED substate,
\* modelling assumption A5). Exception propagates to caller.
AsyncCancelOrK8Fail ==
    /\ kstate = "ACTIVE"
    /\ kstate'       = "FAULTED"
    /\ exc_raised'   = TRUE
    /\ gates_passed' = gates_passed
    /\ gates_failed' = gates_failed
    /\ wal_written'  = wal_written
    /\ corr_id'      = corr_id

\* ── EXITING → IDLE ───────────────────────────────────────────────────────────
\* __aexit__() completes. WAL entry persisted (K6). Crossing finalized.
\* Per-crossing state reset (gates, corr_id, exc_raised cleared).
ExitSuccess ==
    /\ kstate = "EXITING"
    /\ kstate'       = "IDLE"
    /\ wal_written'  = TRUE        \* K6: WAL entry written exactly once
    /\ gates_passed' = {}
    /\ gates_failed' = {}
    /\ corr_id'      = FALSE
    /\ exc_raised'   = FALSE

\* ── EXITING → FAULTED ────────────────────────────────────────────────────────
\* Exit gate fails (e.g. Postgres WAL write error, trace injection failure).
\* WAL NOT written. Exception propagates to caller.
ExitFails ==
    /\ kstate = "EXITING"
    /\ kstate'       = "FAULTED"
    /\ exc_raised'   = TRUE
    /\ wal_written'  = FALSE
    /\ gates_passed' = gates_passed
    /\ gates_failed' = gates_failed
    /\ corr_id'      = corr_id

\* ── FAULTED → IDLE ───────────────────────────────────────────────────────────
\* Exception consumed by caller. Context reset for next crossing.
\* wal_written preserved (reflects result of prior crossing, if any).
ExceptionConsumed ==
    /\ kstate = "FAULTED"
    /\ kstate'       = "IDLE"
    /\ exc_raised'   = FALSE
    /\ gates_passed' = {}
    /\ gates_failed' = {}
    /\ corr_id'      = FALSE
    /\ wal_written'  = wal_written  \* inherited from last successful exit

(******************************************************************************)
(* Next-state relation                                                        *)
(******************************************************************************)
Next ==
    \/ Aenter
    \/ AllGatesPass
    \/ GateFails
    \/ OperationComplete
    \/ AsyncCancelOrK8Fail
    \/ ExitSuccess
    \/ ExitFails
    \/ ExceptionConsumed

(******************************************************************************)
(* Fairness                                                                   *)
(* Weak fairness on every action: if an action is continuously enabled it     *)
(* must eventually fire. This supports all four liveness properties.         *)
(******************************************************************************)
Fairness ==
    /\ WF_vars(Aenter)
    /\ WF_vars(AllGatesPass)
    /\ WF_vars(GateFails)
    /\ WF_vars(OperationComplete)
    /\ WF_vars(AsyncCancelOrK8Fail)
    /\ WF_vars(ExitSuccess)
    /\ WF_vars(ExitFails)
    /\ WF_vars(ExceptionConsumed)

(******************************************************************************)
(* Specification                                                              *)
(******************************************************************************)
Spec == Init /\ [][Next]_vars /\ Fairness

(******************************************************************************)
(* Safety Invariants (Behavior Spec SS1.1 Invariants 1-7)                    *)
(******************************************************************************)

\* INV-1: State is always in the defined set (captured by TypeOK.kstate)
StateInvariant ==
    kstate \in KernelStates

\* INV-2 (SS1.1 INV-5): In ACTIVE, all K1-K8 gates have passed and none failed
\* "No context can be ACTIVE unless all eight gates evaluated successfully."
ActiveRequiresAllGates ==
    kstate = "ACTIVE" => (gates_passed = GATES /\ gates_failed = {})

\* INV-3: No gate can simultaneously appear in both passed and failed sets
GatesDisjoint ==
    gates_passed \cap gates_failed = {}

\* INV-4: WAL entry NOT written during ENTERING phase
\* (WAL is only produced by ExitSuccess: EXITING -> IDLE transition)
NoWALInEntering ==
    kstate = "ENTERING" => ~wal_written

\* INV-5: Correlation ID assigned throughout active phases
\* (K4 assigns corr_id in Aenter; cleared in ExitSuccess / ExceptionConsumed)
CorrIdDuringActive ==
    kstate \in {"ENTERING", "ACTIVE", "EXITING"} => corr_id = TRUE

\* INV-6: Exception is raised if and only if state is FAULTED
\* Bidirectional: no exception outside FAULTED, no FAULTED without exception.
\* This enforces FM-001-2 mitigation (no silent FAULTED->IDLE transition).
ExcFaultedBijection ==
    exc_raised <=> kstate = "FAULTED"

\* INV-7: Gates that passed and gates that failed are disjoint subsets of GATES
GatesSubsetBound ==
    /\ gates_passed \in SUBSET GATES
    /\ gates_failed \in SUBSET GATES

\* ── Combined safety invariant (checked by TLC as INVARIANT) ─────────────────
SafetyInvariant ==
    /\ TypeOK
    /\ StateInvariant
    /\ ActiveRequiresAllGates
    /\ GatesDisjoint
    /\ NoWALInEntering
    /\ CorrIdDuringActive
    /\ ExcFaultedBijection
    /\ GatesSubsetBound

(******************************************************************************)
(* Liveness Properties (Behavior Spec SS1.1 progress guarantees)             *)
(******************************************************************************)

\* LP-1: Every ENTERING eventually reaches ACTIVE or FAULTED
\* (gates either all pass or one fails; no deadlock in gate evaluation)
EnteringTerminates ==
    [](kstate = "ENTERING" => <>(kstate = "ACTIVE" \/ kstate = "FAULTED"))

\* LP-2: Every ACTIVE eventually reaches EXITING or FAULTED
\* (operation completes or is cancelled; no indefinite blocking inside boundary)
ActiveTerminates ==
    [](kstate = "ACTIVE" => <>(kstate = "EXITING" \/ kstate = "FAULTED"))

\* LP-3: Every EXITING eventually reaches IDLE or FAULTED
\* (cleanup completes or WAL write fails; never stuck in exit cleanup)
ExitingTerminates ==
    [](kstate = "EXITING" => <>(kstate = "IDLE" \/ kstate = "FAULTED"))

\* LP-4: Every FAULTED eventually reaches IDLE
\* (exception is always consumed by caller; no permanent fault state)
FaultedTerminates ==
    [](kstate = "FAULTED" => <>(kstate = "IDLE"))

\* LP-5: IDLE is visited infinitely often (the system always makes progress)
EventuallyIdle ==
    []<>(kstate = "IDLE")

====
