# Phase 9 — Task Workflow

Status: **Complete**

## Implemented workflow

1. A Business Lead sends an unassigned task to the Operations inbox.
2. An Operations Manager sets priority and assigns the task.
3. Only the assigned employee can start work.
4. The employee can pause, resume, and add manual time while paused.
5. The employee submits the task for review.
6. Operations completes the task or returns it with a correction reason.
7. Returned work must be started again before it can be resubmitted.
8. Escalated reviews are decided by a Director.

## Timing guarantees

- Opening Nexus or viewing a task does not start task time.
- The server starts time only on an explicit `start` or `resume` action.
- `pause` and `submit-review` settle the active interval into actual hours.
- Manual time can be added only while the task is paused.
- A running task cannot be reassigned.
- Completed task duration contains the accumulated work sessions and manual entries.

## Desktop alignment

- The free-form status dropdown was replaced by a read-only state badge.
- Employees see only actions valid for the current state.
- Employees never receive a Complete control.
- Paused tasks show Resume, Log time, and Submit review.
- Operations receives priority and assignment controls.
- Operations receives Complete, Return, and Director escalation controls only for submitted work.
- Directors receive Complete and Return controls only for escalated work.
- Business Leads and Branch Managers receive oversight-only controls on existing tasks.
- Non-Operations task creation is presented as sending work to the Operations inbox.
- Task details show accumulated work time and whether the timer is running.

## Validation

- FastAPI suite: **23 passed**
- Desktop suite: **63 passed**
- Python compilation checks passed for all changed task modules.

The test coverage includes the complete correction loop, strict start/resume states, idle viewing with zero time, timer settlement, paused manual time, active-timer reassignment rejection, and independent review of Operations-owned work.
