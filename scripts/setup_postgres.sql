-- Script SQL para configurar PostgreSQL para apimovil
-- Ejecutar como usuario postgres: psql -f setup_postgres.sql
-- O desde psql: \i setup_postgres.sql

-- Opción 1: Usar usuario 'admin' existente con db_apimovil existente
-- Ejecuta esto si ya tienes el usuario 'admin' y la base 'db_apimovil'

\echo '================================================'
\echo 'Configurando permisos para usuario admin en db_apimovil'
\echo '================================================'

-- Otorgar todos los privilegios sobre la base de datos
GRANT ALL PRIVILEGES ON DATABASE db_apimovil TO admin;

-- Conectar a la base de datos
\c db_apimovil

-- Otorgar permisos en el esquema público
GRANT ALL ON SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO admin;

-- Para objetos futuros (muy importante para Django)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO admin;

-- Si postgres es el owner de la BD, transferir ownership
ALTER DATABASE db_apimovil OWNER TO admin;

\echo ''
\echo 'Configuración completada para usuario: admin'
\echo 'Base de datos: db_apimovil'
\echo ''
\echo 'Verificar permisos:'
\echo '  \c db_apimovil'
\echo '  \l'
\echo '  \dn+'
\echo ''

-- Mostrar información de la base de datos
\l db_apimovil

-- Mostrar usuarios
\du

\echo ''
\echo '================================================'
\echo 'Puedes salir con: \q'
\echo '================================================'
