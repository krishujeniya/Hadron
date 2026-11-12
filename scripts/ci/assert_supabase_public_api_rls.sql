-- Read-only assertions for both the disposable CI database and the linked
-- Supabase project. Checks effective role privileges, including PUBLIC.
DO $assert_current$
DECLARE
    relation_record RECORD;
    sequence_record RECORD;
    role_name TEXT;
    privilege_name TEXT;
    table_privileges TEXT[];
    qualified_name TEXT;
BEGIN
    FOR relation_record IN
        SELECT c.oid, n.nspname, c.relname, c.relkind, c.relrowsecurity
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
    LOOP
        qualified_name := format('%I.%I', relation_record.nspname, relation_record.relname);

        IF relation_record.relkind IN ('r', 'p') AND NOT relation_record.relrowsecurity THEN
            RAISE EXCEPTION 'RLS is disabled on %', qualified_name;
        END IF;

        IF relation_record.relkind IN ('r', 'p') THEN
            IF NOT has_table_privilege('postgres', relation_record.oid, 'SELECT') THEN
                RAISE EXCEPTION 'postgres lost SELECT on %', qualified_name;
            END IF;
            IF NOT has_table_privilege('service_role', relation_record.oid, 'SELECT') THEN
                RAISE EXCEPTION 'service_role lost SELECT on %', qualified_name;
            END IF;
        END IF;

        table_privileges := CASE
            WHEN relation_record.relkind IN ('r', 'p') THEN ARRAY[
                'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER', 'MAINTAIN'
            ]
            ELSE ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE']
        END;

        FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated']
        LOOP
            FOREACH privilege_name IN ARRAY table_privileges
            LOOP
                IF has_table_privilege(role_name, relation_record.oid, privilege_name) THEN
                    RAISE EXCEPTION '% retains % on %', role_name, privilege_name, qualified_name;
                END IF;
                IF relation_record.relkind IN ('r', 'p', 'v', 'f')
                   AND privilege_name IN ('SELECT', 'INSERT', 'UPDATE')
                   AND has_any_column_privilege(role_name, relation_record.oid, privilege_name) THEN
                    RAISE EXCEPTION '% retains column % on %', role_name, privilege_name, qualified_name;
                END IF;
            END LOOP;
        END LOOP;
    END LOOP;

    FOR sequence_record IN
        SELECT c.oid, n.nspname, c.relname
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'S'
    LOOP
        FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated']
        LOOP
            FOREACH privilege_name IN ARRAY ARRAY['USAGE', 'SELECT', 'UPDATE']
            LOOP
                IF has_sequence_privilege(role_name, sequence_record.oid, privilege_name) THEN
                    RAISE EXCEPTION '% retains % on sequence public.%',
                        role_name, privilege_name, sequence_record.relname;
                END IF;
            END LOOP;
        END LOOP;
    END LOOP;
END
$assert_current$;
