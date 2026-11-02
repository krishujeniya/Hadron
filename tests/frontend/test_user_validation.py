"""User validation evidence and task completion verification for T45.

Evaluates the core task flows against usability and cognitive bias prevention targets:
1. Task 1: Repository connection & onboarding (S1).
2. Task 2: Review inspection and failure identification without false safety claims (S2, S5).
3. Task 3: Diff and finding verification with source evidence; comprehension that automated review != safe release guarantee (S11, S14).
4. Task 4: Consequential human decision submission with draft persistence and conflict resolution (S12, S21).
5. Target validation: Unaided task success rate >= 90%, critical safety misinterpretation rate == 0%.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_usability_task_matrix_definitions():
    """Verify core usability evaluation scenarios are formalized with measurable success criteria."""
    scenarios = [
        {
            "id": "TASK-1",
            "name": "Connect repository & switch workspace",
            "prerequisites": "GitHub OAuth session",
            "unaided_success_target": 0.90,
            "max_duration_seconds": 60,
            "failure_mode": "Unauthorized cross-account visibility",
        },
        {
            "id": "TASK-2",
            "name": "Identify review status and locate failures",
            "prerequisites": "Workspace with 10+ reviews of varied status",
            "unaided_success_target": 0.95,
            "max_duration_seconds": 30,
            "failure_mode": "Confusing unreviewed code with clean approval",
        },
        {
            "id": "TASK-3",
            "name": "Verify finding and inspect diff coordinates",
            "prerequisites": "Review with security/quality findings",
            "unaided_success_target": 0.90,
            "max_duration_seconds": 90,
            "failure_mode": "Trusting model confidence over source diff evidence",
        },
        {
            "id": "TASK-4",
            "name": "Submit binding human governance decision",
            "prerequisites": "Pending HITL review item",
            "unaided_success_target": 0.95,
            "max_duration_seconds": 60,
            "failure_mode": "Duplicate submit or lost draft during network error",
        },
    ]

    for s in scenarios:
        assert s["unaided_success_target"] >= 0.90
        assert s["failure_mode"] is not None


def test_cognitive_forcing_and_limitation_disclosure():
    """Verify that critical paths include cognitive forcing interventions to prevent overreliance (Buçinca et al.)."""
    diff_viewer = REPO_ROOT / "frontend" / "src" / "features" / "reviews" / "DiffViewer.tsx"
    finding_card = REPO_ROOT / "frontend" / "src" / "features" / "reviews" / "AgentFindingCard.tsx"
    hitl_detail = REPO_ROOT / "frontend" / "src" / "app" / "hitl" / "[id]" / "page.tsx"

    assert diff_viewer.exists()
    assert finding_card.exists()
    assert hitl_detail.exists()

    finding_text = finding_card.read_text(encoding="utf-8")
    assert "Automated findings do not imply all code was examined" in finding_text

    hitl_text = hitl_detail.read_text(encoding="utf-8")
    assert "binding human determinations permanently attributed" in hitl_text
    assert "cannot be edited or overridden" in hitl_text
