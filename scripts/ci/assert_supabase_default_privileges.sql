-- Run only in the disposable GitHub Actions database after the migration.
-- Creating new objects proves that default grants for Data API roles stay off.
CREATE TABLE public.future_public_table (id BIGINT PRIMARY KEY);
CREATE SEQUENCE public.future_public_sequence;
CREATE VIEW public.future_public_view AS
    SELECT id FROM public.future_public_table;

DO $assert_defaults$
DECLARE
    role_name TEXT;
    privilege_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated']
    LOOP
        FOREACH privilege_name IN ARRAY ARRAY[
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER', 'MAINTAIN'
        ]
        LOOP
            IF has_table_privilege(role_name, 'public.future_public_table', privilege_name) THEN
                RAISE EXCEPTION '% receives future table privilege %', role_name, privilege_name;
            END IF;
        END LOOP;

        FOREACH privilege_name IN ARRAY ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE']
        LOOP
            IF has_table_privilege(role_name, 'public.future_public_view', privilege_name) THEN
                RAISE EXCEPTION '% receives future view privilege %', role_name, privilege_name;
            END IF;
        END LOOP;

        FOREACH privilege_name IN ARRAY ARRAY['USAGE', 'SELECT', 'UPDATE']
        LOOP
            IF has_sequence_privilege(role_name, 'public.future_public_sequence', privilege_name) THEN
                RAISE EXCEPTION '% receives future sequence privilege %', role_name, privilege_name;
            END IF;
        END LOOP;
    END LOOP;

    IF NOT has_table_privilege('service_role', 'public.future_public_table', 'SELECT') THEN
        RAISE EXCEPTION 'service_role lost intended future table access';
    END IF;
END
$assert_defaults$;
