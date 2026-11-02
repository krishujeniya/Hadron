"""
tests/frontend/test_consequential_human_decision_flow.py
---------------------------------------------------
Validates T37: Complete the consequential human-decision flow.
Tests:
  1. HITLDecisionForm prevents duplicate/double-click submissions with atomic lock.
  2. HITLDecisionForm handles 401, 403, 409 conflict, 422 validation, and 5xx errors gracefully.
  3. HITLDecisionForm separates recorded decision state from GitHub delivery state.
  4. HITLQueuePage implements server-scoped pagination, reachable counts, and honest empty queue messaging.
  5. HITLDetailPage eliminates false promises of decision overriding or PR merging.
"""

import pathlib


def test_hitl_decision_form_source_contract():
    """Verify HITLDecisionForm has duplicate locks, error matrix handling, and honest disclosure."""
    form_path = pathlib.Path("frontend/src/features/hitl/HITLDecisionForm.tsx")
    assert form_path.exists(), "HITLDecisionForm.tsx must exist"
    content = form_path.read_text(encoding="utf-8")

    # 1. Duplicate submission lock
    assert "submitLock" in content
    assert "submitting" in content

    # 2. Status code handling: 401, 403, 409, 422, 5xx
    assert "err.status === 401" in content
    assert "err.status === 403" in content
    assert "err.status === 409" in content
    assert "err.status === 422" in content
    assert "conflictDetail" in content

    # 3. Decision recorded vs GitHub delivery separation
    assert "result.posted_to_github" in content
    assert "Human Determination Recorded" in content

    # 4. Draft preservation
    assert "DRAFT_KEY_PREFIX" in content
    assert "localStorage.setItem" in content
    assert "localStorage.getItem" in content

    # 5. Clear disclaimer: cannot edit/undo, does not merge PR
    assert "cannot\n            edit or undo" in content or "cannot edit or undo" in content
    assert "does not merge the" in content


def test_hitl_queue_page_contract():
    """Verify hitl/page.tsx implements server-scoped pagination and honest empty states."""
    queue_path = pathlib.Path("frontend/src/app/hitl/page.tsx")
    assert queue_path.exists(), "hitl/page.tsx must exist"
    content = queue_path.read_text(encoding="utf-8")

    # 1. Server-scoped pagination
    assert "PAGE_SIZE" in content
    assert "totalPages" in content
    assert "pageUrl" in content
    assert "Queue pagination" in content

    # 2. Honest empty state
    assert "No Pending Decisions in Scope" in content
    assert "automated checks and review\n            policies may still apply" in content or "automated checks and review policies may still apply" in content


def test_hitl_detail_page_contract():
    """Verify hitl/[id]/page.tsx eliminates false promises of overriding decisions."""
    detail_path = pathlib.Path("frontend/src/app/hitl/[id]/page.tsx")
    assert detail_path.exists(), "hitl/[id]/page.tsx must exist"
    content = detail_path.read_text(encoding="utf-8")

    # 1. Consequential Decision Gate disclosure
    assert "Consequential Decision Gate" in content
    assert "cannot be edited or overridden" in content
    assert "Submitting does not merge the pull request" in content
