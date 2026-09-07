CREATE ROLE flash_trips_migration
  LOGIN
  PASSWORD 'local-migration-only'
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE;

CREATE ROLE flash_trips_runtime
  LOGIN
  PASSWORD 'local-runtime-only'
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE;

GRANT CONNECT ON DATABASE flash_trips
  TO flash_trips_migration, flash_trips_runtime;
GRANT ALL ON SCHEMA public TO flash_trips_migration;
GRANT USAGE ON SCHEMA public TO flash_trips_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE flash_trips_migration IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flash_trips_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE flash_trips_migration IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO flash_trips_runtime;
