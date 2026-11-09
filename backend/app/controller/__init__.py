"""The placement controller (owner: Rishabh). Run it with `python -m app.controller`.

Level-triggered: every pass compares the desired state (placement requests,
room state) with the actual state (Pods, Nodes) and fixes the difference. A
pass runs on every watch event and at least every RESYNC_SECONDS, and it is
safe to restart at any point, because Pod names are deterministic.

Later tasks add their work as reconcilers:

    from app.controller.loop import register

    @register("placement")
    def reconcile_placements(ctl): ...
"""
