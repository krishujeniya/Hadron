# Supabase public schema security

Project: `hadron-production` (`zwpfaqmwfjbeautfplzz`).

## Verified exposure

The read-only Supabase Security Advisor and catalog queries on 2026-11-12 found 20 tables in the exposed `public` schema with RLS disabled, no policies, and full table privileges granted to `anon` and `authenticated`. Five public sequences also granted those roles usage, select, and update. The public schema includes personal and credential data, including application/bank details, password hashes, OTPs, OAuth private keys, and refresh tokens. The existing `postgres` role owns these tables.

The Hadron frontend calls its FastAPI backend and the backend connects directly to Postgres; the repository does not use a browser Supabase client. The fix therefore closes direct Supabase Data API access for `anon` and `authenticated`, while retaining the existing database owner and server-side `service_role` privileges. No rows or table definitions are changed.

## What the migration does

`supabase/migrations/20261112102935_lock_down_public_api_roles.sql`:

- enables RLS on every existing table in `public`;
- revokes table, view, column, and sequence privileges from `PUBLIC`, `anon`, and `authenticated`;
- removes those default grants for future tables and sequences created by `postgres`;
- leaves `postgres` and `service_role` privileges intact and creates no client access policies.

With RLS enabled and no policies or grants for the API roles, their table requests are denied. A future feature that intentionally exposes data must add a reviewed policy and the smallest required grants in the same migration.

## GitHub Actions release path

Pull requests run `.github/workflows/supabase-security.yml` against a disposable PostgreSQL 17.11 service. It seeds Supabase-style default grants, applies the tracked migrations, checks current and future table/sequence permissions, and checks migration idempotency. The job uses no Supabase credentials and does not touch production.

After the pull request passes and is merged to `main`:

1. Configure the GitHub environment `supabase-production` with a required reviewer.
2. Add environment secrets `SUPABASE_ACCESS_TOKEN` and `SUPABASE_DB_PASSWORD`. Scope the access token to this project and the read permissions needed for `supabase link` plus migration deployment. Do not put either value in the repository or workflow source. See [Supabase personal access token scopes](https://supabase.com/docs/guides/platform/personal-access-tokens).
3. In GitHub Actions, dispatch **Supabase database security** from `main` and set `deploy_production` to `true`.
4. Review and approve the protected environment job. The workflow previews pending migrations, applies them with `supabase db push --remote`, then runs read-only privilege assertions and the Security Advisor.

The workflow is manual by design. A push or pull request cannot write to the production database. Production acceptance is not established until the Actions deployment and its post-migration checks pass.

## Recovery

This migration changes privileges and RLS metadata only. If a server-side database connection unexpectedly loses access, restore access through a reviewed forward migration for that server role. Do not roll back by granting the public API roles broad table access.
