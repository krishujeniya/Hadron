# tests/test_judge_and_eval_t15.py
#
# Verification tests for Task T15:
# Repair the judge contract and measure false positives.

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.evaluation.golden_dataset import ExpectedFinding, GoldenPR
from backend.evaluation.judge import PASS_THRESHOLD, PRReviewJudge
from backend.evaluation.regression_gate import EvalResult, RegressionGate
from backend.tools.llm_client import LLMClient, LLMResponse


@pytest.fixture
def clean_golden_pr():
    """Human-curated clean PR with zero expected defects (should be approved)."""
    return GoldenPR(
        id="clean_pr_001",
        pr_title="Add utility formatting function",
        pr_description="Simple helper function without side effects.",
        diff_snippet="""
def format_hex(val: int) -> str:
    return hex(val)
""",
        expected_verdict="approve",
        expected_findings=(),
        difficulty="easy",
        category="quality",
        notes="Clean PR with zero expected findings.",
    )


@pytest.fixture
def dirty_golden_pr():
    """PR with known critical security and test defects."""
    return GoldenPR(
        id="dirty_pr_002",
        pr_title="Add database query handler",
        pr_description="Direct SQL execution.",
        diff_snippet="""
def query_user(user_id: str):
    return db.execute(f"SELECT * FROM users WHERE id = '{user_id}'")
""",
        expected_verdict="request_changes",
        expected_findings=(
            ExpectedFinding("security", "critical", "injection"),
            ExpectedFinding("test", "medium", "test"),
        ),
        difficulty="medium",
        category="security",
        notes="SQL injection vulnerability.",
    )


def test_clean_pr_with_invented_findings_fails_metric(clean_golden_pr):
    """
    A clean PR with invented critical findings must fail the relevant metric.
    Empty golden PRs must not grant full scores when unexpected findings are present.
    """
    mock_llm = MagicMock()
    judge = PRReviewJudge(llm_client=mock_llm)

    # Agent hallucinated a critical vulnerability on completely clean code
    actual_findings = [
        {
            "agent_type": "security",
            "severity": "critical",
            "summary": "Severe remote code execution in hex formatting",
        }
    ]

    score = judge.score_review(
        golden=clean_golden_pr,
        actual_verdict="request_changes",
        actual_findings=actual_findings,
    )

    assert score.false_positive_count == 1
    assert score.precision == 0.0
    assert score.finding_coverage == 0.0
    assert score.overall_score == 0.0
    assert score.overall_score < PASS_THRESHOLD
    assert "false positive finding(s) invented" in score.reasoning


def test_clean_pr_with_honest_clean_review_passes(clean_golden_pr):
    """A clean PR correctly evaluated with zero findings gets a perfect score."""
    mock_llm = MagicMock()
    judge = PRReviewJudge(llm_client=mock_llm)

    score = judge.score_review(
        golden=clean_golden_pr,
        actual_verdict="approve",
        actual_findings=[],
    )

    assert score.false_positive_count == 0
    assert score.precision == 1.0
    assert score.finding_coverage == 1.0
    assert score.overall_score == 1.0
    assert score.overall_score >= PASS_THRESHOLD
    assert score.judge_used_llm is False


def test_llm_client_complete_interface_typed():
    """LLMClient exposes typed complete() and acomplete() interfaces."""
    client = LLMClient()
    assert hasattr(client, "complete")
    assert hasattr(client, "acomplete")

    mock_resp = LLMResponse(
        content={"finding_coverage": 1.0, "severity_accuracy": 1.0, "reasoning": "ok"},
        input_tokens=10,
        output_tokens=10,
        model_used="gpt-4o-mini",
        latency_seconds=0.1,
        estimated_cost_usd=0.0001,
        is_valid_json=True,
    )

    with patch.object(client, "call_openai", new=AsyncMock(return_value=mock_resp)):
        res = client.complete(system_prompt="sys", user_message="user")
        assert res.content == mock_resp.content


def test_unavailable_judge_fallback_reported_and_gate_fails_when_strict():
    """
    An unavailable judge cannot silently pass an LLM release gate.
    Fallback to keyword matching must be explicitly flagged in JudgeScore and EvalResult.
    """
    # LLM that fails/raises
    mock_llm = MagicMock()
    mock_llm.complete.side_effect = RuntimeError("OpenAI rate limit or network unreachable")
    judge = PRReviewJudge(llm_client=mock_llm)

    golden = GoldenPR(
        id="dirty_pr",
        pr_title="",
        pr_description="",
        diff_snippet="",
        expected_verdict="request_changes",
        expected_findings=(ExpectedFinding("security", "critical", "injection"),),
        difficulty="medium",
        category="security",
        notes="",
    )

    # 1. Without fail_on_unavailable_llm: flags fallback_active=True
    score = judge.score_review(
        golden=golden,
        actual_verdict="request_changes",
        actual_findings=[{"agent_type": "security", "severity": "critical", "summary": "SQL injection"}],
        fail_on_unavailable_llm=False,
    )
    assert score.judge_used_llm is False
    assert score.judge_fallback_active is True
    assert "[Fallback: LLM unavailable" in score.reasoning

    # 2. With fail_on_unavailable_llm=True: raises explicitly
    with pytest.raises(RuntimeError) as exc_info:
        judge.score_review(
            golden=golden,
            actual_verdict="request_changes",
            actual_findings=[],
            fail_on_unavailable_llm=True,
        )
    assert "Judge LLM failed and fallback is prohibited" in str(exc_info.value)

    # 3. Release gate fails when strict LLM evaluation is required
    eval_result = EvalResult(
        example_id="dirty_pr",
        difficulty="medium",
        category="security",
        expected_verdict="request_changes",
        actual_verdict="request_changes",
        verdict_correct=True,
        finding_coverage=1.0,
        severity_accuracy=1.0,
        score=0.90,
        reasoning="keyword matched",
        judge_fallback_active=True,
    )
    gate = RegressionGate()
    passed, reason = gate.check_threshold([eval_result], require_llm_judge=True)
    assert passed is False
    assert "Judge LLM was unavailable" in reason


def test_partial_coverage_with_false_positives_penalized(dirty_golden_pr):
    """
    On a PR with expected findings, hallucinated/unrelated findings are penalized as false positives.
    """
    mock_llm = MagicMock()
    judge = PRReviewJudge(llm_client=mock_llm)

    # Returns one true positive finding, and two hallucinated false positives
    actual_findings = [
        {"agent_type": "security", "severity": "critical", "summary": "SQL injection vulnerability"},
        {"agent_type": "quality", "severity": "low", "summary": "Hallucinated variable naming issue"},
        {"agent_type": "quality", "severity": "low", "summary": "Invented style complaint"},
    ]

    score = judge.score_review(
        golden=dirty_golden_pr,
        actual_verdict="request_changes",
        actual_findings=actual_findings,
    )

    # 1 expected finding matched (injection), 1 missed (test)
    assert score.finding_coverage == 0.50
    # 1 true positive out of 3 total reported findings -> precision ~ 0.33
    assert abs(score.precision - (1.0 / 3.0)) < 1e-4
    assert score.false_positive_count == 2
    # Score is lower than if only the true positive was reported
    assert score.overall_score < 0.75
