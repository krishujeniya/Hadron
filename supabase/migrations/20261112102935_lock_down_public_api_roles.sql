-- Keep the public Data API closed by default. Hadron accesses Postgres through
-- its server-side database connection; the browser uses the FastAPI API.
-- Preserve owner/service_role access, but require any future client exposure
-- to be an explicit, reviewed grant plus an RLS policy.

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, anon, authenticated;

DO $migration$
DECLARE
    relation_record RECORD;
    column_record RECORD;
BEGIN
    -- RLS without a policy denies Data API row access. The app's database
    -- owner connection and Supabase service_role retain their existing rights.
    FOR relation_record IN
        SELECT c.oid, n.nspname, c.relname
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',
            relation_record.nspname,
            relation_record.relname
        );

        -- REVOKE TABLE privileges does not remove separately granted column
        -- privileges, so remove those too if any have been configured.
        FOR column_record IN
            SELECT attname
            FROM pg_attribute
            WHERE attrelid = relation_record.oid
              AND attnum > 0
              AND NOT attisdropped
              AND attacl IS NOT NULL
        LOOP
            EXECUTE format(
                'REVOKE ALL PRIVILEGES (%I) ON TABLE %I.%I FROM PUBLIC, anon, authenticated',
                column_record.attname,
                relation_record.nspname,
                relation_record.relname
            );
        END LOOP;
    END LOOP;
END
$migration$;
