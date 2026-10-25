# Model Routing & Provider Architecture

This document describes model routing and provider configuration in Hadron.

## Overview

Hadron employs a multi-agent review architecture orchestrated via LangGraph. Each specialist agent analyzes distinct facets of incoming code diffs:

| Agent | Scope | Recommended Model | Provider |
|---|---|---|---|
| **Security Agent** | OWASP Top 10, credential leaks, SQL/Command injection | `openai/gpt-oss-20b` | NVIDIA NIM / OpenAI |
| **Quality Agent** | SOLID principles, code smells, complexity, maintainability | `openai/gpt-oss-20b` | NVIDIA NIM / OpenAI |
| **Test Agent** | Test coverage gaps, untested edge cases, mock contracts | `openai/gpt-oss-20b` | NVIDIA NIM / OpenAI |
| **Docs Agent** | Docstrings, type annotations, README/API doc drift | `openai/gpt-oss-20b` | NVIDIA NIM / OpenAI |

## NVIDIA NIM Integration

Hadron natively integrates with NVIDIA NIM endpoints (`https://integrate.api.nvidia.com/v1`).
When an API key prefix `nvapi-` is detected or `NVIDIA_API_KEY` is provided:

1. **Model Normalization**: Model requests are automatically mapped to catalog-compatible identifiers such as `openai/gpt-oss-20b`.
2. **Reasoning Headroom**: Generative reasoning models require token headroom for internal chain-of-thought before emitting structured JSON findings. Hadron allocates at least 4,096 tokens of response headroom.
3. **Concurrency Control**: Multi-agent fan-out executions are throttled via an `asyncio.Semaphore` (default 2 parallel agents) to maintain high throughput without triggering endpoint rate limits.
