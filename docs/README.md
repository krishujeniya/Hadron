# Hadron documentation

Start with the [execution tracker](tracker.md) for current verification, release blockers and handoff. Historical completion records do not certify a deployed version.

- [Repository layout and inspected GitHub sources](architecture/repository-layout.md)
- [Architecture decisions](adr/)
- [Model routing](architecture/model-routing.md)
- [Threat model](security/threat-model.md) and [data inventory](security/data-inventory.md)
- [Rollout and rollback](operations/rollout-rollback.md)
- [Disaster recovery](operations/disaster-recovery.md)
- [SLOs and capacity](operations/slo-and-capacity.md)
- [Incident response and support](operations/incident-and-support.md), with [operational runbooks](runbooks/)
- [Design principles](design/principles.md) and [design system](design/system/hadron/MASTER.md)
- [Product roadmap](product/roadmap.md)
- [UX research](research/ux-human-factors.md) and [historical frontend assessment](reviews/frontend-audit.md)
- [Dated verification evidence](verification/)

Application setup and runtime commands belong in the [root README](../README.md). Add an architecture decision when a dependency boundary or deployment responsibility changes; use the tracker for task status rather than creating another completion checklist.
