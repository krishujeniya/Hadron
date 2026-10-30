# tests/test_deployment_topology_t22.py
#
# Contract tests for Gate B - Task T22:
# Make deployment topology and images reproducible.
#
# Invariants verified:
#   1. .dockerignore strictly blocks all credentials, agent workspaces, git, and local cache.
#   2. Dockerfile uses multi-stage builds, non-root user, and allowlisted source copying.
#   3. No unsupported marketing claims ("<200MB", "CIS hardened") in container files.
#   4. scripts/entrypoint.sh decouples API and Worker into independent execution modes.
#   5. docker-compose.yml defines persistent Redis volumes, prevents duplicate workers,
#      and declares the full production topology (frontend, api, worker, redis).

import pathlib
import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_dockerignore_rules_protect_credentials_and_agent_context():
    """
    .dockerignore must strictly exclude sensitive credentials (.aws, .ssh, .pem, .key),
    local AI agent workspaces (.agents, .codex, .gemini, .claude), and git/caches.
    """
    dockerignore_path = REPO_ROOT / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore missing"

    content = dockerignore_path.read_text()
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    required_exclusions = [
        ".aws/",
        ".ssh/",
        ".gnupg/",
        "*.pem",
        "*.key",
        ".agents/",
        ".codex/",
        ".gemini/",
        ".claude/",
        ".git/",
        ".venv/",
        ".pytest_cache/",
        ".system_generated/",
    ]

    for req in required_exclusions:
        assert any(req in line for line in lines), f"Required exclusion '{req}' missing from .dockerignore"


def test_dockerfile_multi_stage_structure_and_no_unsubstantiated_claims():
    """
    Dockerfile must use a clean multi-stage pattern, unprivileged non-root user,
    allowlisted source copying, and must not make unsubstantiated claims.
    """
    dockerfile_path = REPO_ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile missing"

    content = dockerfile_path.read_text()

    # Multi-stage check
    assert "FROM python:3.11-slim AS builder" in content
    assert "FROM python:3.11-slim AS runtime" in content

    # Non-root unprivileged execution check
    assert "USER hadron" in content

    # Allowlisted source copy (not blind 'COPY . .')
    assert "COPY --chown=hadron:hadron backend/ ./backend/" in content
    assert "COPY --chown=hadron:hadron scripts/ ./scripts/" in content

    # Entrypoint and command decoupling check
    assert 'ENTRYPOINT ["/app/scripts/entrypoint.sh"]' in content
    assert 'CMD ["api"]' in content

    # Ensure no unsubstantiated claims
    assert "<200MB" not in content
    assert "CIS Benchmark hardened" not in content


def test_entrypoint_script_decouples_api_and_worker():
    """
    scripts/entrypoint.sh must provide distinct subcommands for 'api' and 'worker'
    to prevent accidental duplicate worker processes in container clusters.
    """
    entrypoint_path = REPO_ROOT / "scripts" / "entrypoint.sh"
    assert entrypoint_path.exists(), "scripts/entrypoint.sh missing"

    content = entrypoint_path.read_text()

    # Must support individual process execution
    assert "api)" in content
    assert "worker)" in content
    assert "exec uvicorn backend.main:app" in content
    assert "exec python3 -m arq backend.job_queue.arq_worker.WorkerSettings" in content


def test_docker_compose_production_topology_has_durable_volumes_and_isolated_services():
    """
    docker-compose.yml must declare persistent Redis storage, independent
    process commands without duplicate workers, and the complete application topology.
    """
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml missing"

    with open(compose_path, "r") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})
    assert "api" in services, "api service missing from compose"
    assert "worker" in services, "worker service missing from compose"
    assert "redis" in services, "redis service missing from compose"
    assert "frontend" in services, "frontend service missing from compose"

    # Redis persistence check
    redis_service = services["redis"]
    redis_volumes = redis_service.get("volumes", [])
    assert any("redis_data" in v for v in redis_volumes), "Redis must have a durable named volume"
    redis_cmd = " ".join(redis_service.get("command", []))
    assert "--appendonly yes" in redis_cmd, "Redis must have AOF persistence enabled"

    # API vs Worker command isolation check (No duplicate workers!)
    api_cmd = services["api"].get("command", [])
    assert api_cmd == ["api"], "API service must specify command ['api'] to avoid duplicate workers"

    worker_cmd = services["worker"].get("command", [])
    assert worker_cmd == ["worker"], "Worker service must specify command ['worker']"

    # Restart policies
    for name in ["api", "worker", "redis", "frontend"]:
        assert services[name].get("restart") in ("unless-stopped", "always"), (
            f"Service {name} missing production restart policy"
        )

    # Volumes section check
    volumes = config.get("volumes", {})
    assert "redis_data" in volumes, "redis_data volume must be declared"


def test_frontend_dockerfile_multi_stage_standalone():
    """
    frontend/Dockerfile must build Next.js in standalone mode with unprivileged user.
    """
    frontend_dockerfile = REPO_ROOT / "frontend" / "Dockerfile"
    assert frontend_dockerfile.exists(), "frontend/Dockerfile missing"

    content = frontend_dockerfile.read_text()
    assert "FROM node:20-alpine AS deps" in content
    assert "FROM node:20-alpine AS builder" in content
    assert "FROM node:20-alpine AS runner" in content
    assert "USER nextjs" in content
    assert 'CMD ["node", "server.js"]' in content
