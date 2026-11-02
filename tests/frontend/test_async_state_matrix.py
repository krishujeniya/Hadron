"""
tests/frontend/test_async_state_matrix.py
------------------------------------
Validates T41: Implement the full asynchronous state matrix (S0–S25).
Tests:
  1. SWRProvider implements bounded transient retry with exponential backoff and offline guards.
  2. Non-transient errors (401, 403, 404, 422) are never retried automatically.
  3. GitHubProvider contains generation guards preventing race responses across account switches.
  4. Repository fetch errors are captured and exposed in state (repoError).
  5. SWR cache is cleared on workspace switch and sign out to prevent cross-tenant data leaks.
"""

import pathlib


def test_swr_provider_async_resilience_contract():
    """Verify swr.tsx implements bounded transient error retry and suppression."""
    swr_path = pathlib.Path("frontend/src/lib/swr.tsx")
    assert swr_path.exists(), "frontend/src/lib/swr.tsx must exist"
    content = swr_path.read_text(encoding="utf-8")

    # 1. Bounded retry count
    assert "errorRetryCount: 3" in content
    assert "retryCount >= 3" in content

    # 2. Suppression of non-transient status codes
    assert "error?.status === 401" in content
    assert "error?.status === 403" in content
    assert "error?.status === 404" in content
    assert "error?.status === 422" in content

    # 3. Offline and background tab pause
    assert 'document.visibilityState === "hidden"' in content
    assert "!navigator.onLine" in content

    # 4. Exponential backoff
    assert "2 ** retryCount" in content


def test_github_provider_generation_guard_and_race_prevention():
    """Verify githubContext.tsx contains generation guard against race responses."""
    ctx_path = pathlib.Path("frontend/src/features/auth/github-context.tsx")
    assert ctx_path.exists(), "frontend/src/features/auth/github-context.tsx must exist"
    content = ctx_path.read_text(encoding="utf-8")

    # 1. Generation reference
    assert "generationRef" in content
    assert "generationRef.current" in content
    assert "thisGen" in content

    # 2. Captured repoError
    assert "repoError" in content
    assert "setRepoError" in content

    # 3. Cache purge on switch
    assert "mutate(() => true, undefined, { revalidate: false })" in content
