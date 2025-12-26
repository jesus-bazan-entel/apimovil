-- Script SQL para crear un nuevo usuario para apimovil
-- Ejecutar como usuario postgres: psql -f setup_postgres_new_user.sql

-- IMPORTANTE: Cambia 'TU_PASSWORD_SEGURO' por un password real antes de ejecutar

\echo '================================================'
\echo 'Creando usuario apimovil_user y configurando db_apimovil'
\echo '================================================'

-- Crear usuario si no existe
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'apimovil_user') THEN
        CREATE USER apimovil_user WITH PASSWORD 'TU_PASSWORD_SEGURO';
        RAISE NOTICE 'Usuario apimovil_user creado';
    ELSE
        RAISE NOTICE 'Usuario apimovil_user ya existe';
    END IF;
END
$$;

-- Si la base de datos db_apimovil ya existe, cambiar owner
-- Si no existe, créala (descomenta la siguiente línea)
-- CREATE DATABASE db_apimovil OWNER apimovil_user;

-- Otorgar privilegios
GRANT ALL PRIVILEGES ON DATABASE db_apimovil TO apimovil_user;

-- Conectar a la base de datos
\c db_apimovil

-- Cambiar owner de la base de datos
ALTER DATABASE db_apimovil OWNER TO apimovil_user;

-- Otorgar permisos en el esquema público
GRANT ALL ON SCHEMA public TO apimovil_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO apimovil_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO apimovil_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO apimovil_user;

-- Para objetos futuros
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO apimovil_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO apimovil_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO apimovil_user;

\echo ''
\echo '================================================'
\echo 'Configuración completada'
\echo '================================================'
\echo 'Usuario: apimovil_user'
\echo 'Base de datos: db_apimovil'
\echo ''
\echo 'IMPORTANTE: Cambia el password en tu archivo .env'
\echo 'DB_USER=apimovil_user'
\echo 'DB_PASSWORD=TU_PASSWORD_SEGURO'
\echo ''

-- Mostrar información
\l db_apimovil
\du apimovil_user

\echo ''
\echo 'Probar conexión:'
\echo '  psql -U apimovil_user -d db_apimovil -h localhost'
\echo ''
\echo 'Salir con: \q'
\echo '================================================'
