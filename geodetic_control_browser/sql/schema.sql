-- Geodetic Control Browser: demo PostGIS schema
-- Tested with PostgreSQL 14+ / PostGIS 3.x
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS gc;

CREATE TABLE IF NOT EXISTS gc.control_point (
    id             serial PRIMARY KEY,
    point_no       varchar(9)  NOT NULL UNIQUE CHECK (point_no ~ '^\d{4}-\d{4}$'),
    point_class    varchar(3)  NOT NULL CHECK (point_class IN ('I', 'II', 'III')),
    height         numeric(8,3),
    height_system  varchar(16) CHECK (height_system IN ('PL-EVRF2007-NH', 'PL-KRON86-NH', 'ellipsoidal')),
    status         varchar(10) NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'damaged', 'destroyed', 'not_found')),
    last_surveyed  date CHECK (last_surveyed <= current_date),
    description    text,
    geom           geometry(Point, 2180) NOT NULL,          -- PL-1992
    updated_at     timestamptz NOT NULL DEFAULT now(),
    updated_by     text NOT NULL DEFAULT current_user,
    CONSTRAINT height_needs_system CHECK (height IS NULL OR height_system IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS control_point_geom_gix ON gc.control_point USING gist (geom);
CREATE INDEX IF NOT EXISTS control_point_status_idx ON gc.control_point (status);

-- Full edit history: one row per insert/update/delete with the old and new record
CREATE TABLE IF NOT EXISTS gc.control_point_history (
    history_id   bigserial PRIMARY KEY,
    point_id     integer NOT NULL,
    operation    char(1) NOT NULL CHECK (operation IN ('I', 'U', 'D')),
    changed_at   timestamptz NOT NULL DEFAULT now(),
    changed_by   text NOT NULL DEFAULT current_user,
    old_row      jsonb,
    new_row      jsonb
);
CREATE INDEX IF NOT EXISTS control_point_history_point_idx ON gc.control_point_history (point_id, changed_at DESC);

CREATE OR REPLACE FUNCTION gc.log_control_point_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO gc.control_point_history (point_id, operation, new_row)
        VALUES (NEW.id, 'I', to_jsonb(NEW) - 'geom' || jsonb_build_object('wkt', ST_AsText(NEW.geom)));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        NEW.updated_at := now();
        NEW.updated_by := current_user;
        INSERT INTO gc.control_point_history (point_id, operation, old_row, new_row)
        VALUES (NEW.id, 'U',
                to_jsonb(OLD) - 'geom' || jsonb_build_object('wkt', ST_AsText(OLD.geom)),
                to_jsonb(NEW) - 'geom' || jsonb_build_object('wkt', ST_AsText(NEW.geom)));
        RETURN NEW;
    ELSE
        INSERT INTO gc.control_point_history (point_id, operation, old_row)
        VALUES (OLD.id, 'D', to_jsonb(OLD) - 'geom' || jsonb_build_object('wkt', ST_AsText(OLD.geom)));
        RETURN OLD;
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS control_point_audit ON gc.control_point;
CREATE TRIGGER control_point_audit
    BEFORE INSERT OR UPDATE OR DELETE ON gc.control_point
    FOR EACH ROW EXECUTE FUNCTION gc.log_control_point_change();
