-- Script de inicialización para CONIITI
-- Crea todas las bases de datos en una sola instancia de Postgres

CREATE DATABASE usersdb;
CREATE DATABASE authdb;
CREATE DATABASE agenda_db;
CREATE DATABASE notificationsdb;
CREATE DATABASE paymentsdb;
CREATE DATABASE filesdb;
CREATE DATABASE rafflesdb;

-- Opcional: Crear usuarios específicos si fuera necesario, 
-- pero para ahorro máximo usaremos el usuario 'admin' para todos.
