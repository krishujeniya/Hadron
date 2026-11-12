-- Recreate the Supabase default API grants and the production relation names
-- in an isolated Postgres service. This file is used only by GitHub Actions.
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON TABLES TO PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON SEQUENCES TO PUBLIC, anon, authenticated, service_role;

DO $fixture$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'agent_events', 'applications', 'audit_log', 'code_chunks',
        'data_exports', 'finding_records', 'hitl_feedback', 'hitl_reviews',
        'legal_holds', 'llm_call_log', 'oauth_clients', 'oauth_codes',
        'oauth_keys', 'oauth_program_tokens', 'oauth_refresh_tokens',
        'oauth_requests', 'otps', 'portal_users', 'pr_review_records',
        'repo_file_index'
    ]
    LOOP
        EXECUTE format('CREATE TABLE public.%I (id BIGINT PRIMARY KEY)', table_name);
    END LOOP;
END
$fixture$;

CREATE SEQUENCE public.applications_id_seq;
CREATE SEQUENCE public.audit_log_id_seq;
CREATE SEQUENCE public.oauth_clients_id_seq;
CREATE SEQUENCE public.oauth_program_tokens_id_seq;
CREATE SEQUENCE public.otps_id_seq;

CREATE VIEW public.sensitive_view AS
    SELECT id FROM public.portal_users;

-- Exercise removal of column-only grants separately from table ACLs.
GRANT SELECT (id) ON public.portal_users TO anon, PUBLIC;
GRANT UPDATE (id) ON public.portal_users TO authenticated;
