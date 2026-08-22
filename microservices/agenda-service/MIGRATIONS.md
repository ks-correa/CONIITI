# Migraciones de agenda-service

Antes de operar sobre una base existente, haga un respaldo verificable. La revisión
`0001_existing` detecta las tablas legacy de `create_all`, no intenta recrearlas y
permite que una instalación sin `alembic_version` ejecute directamente:

```bash
alembic upgrade head
```

El mismo comando crea el baseline en una base vacía. El contenedor lo ejecuta antes
de iniciar Uvicorn. `stamp` queda reservado a recuperación operativa después de
comparar el esquema, nunca como paso normal. Para ensayar rollback use una copia:

```bash
alembic downgrade 0001_existing
alembic upgrade head
```

El downgrade de `0001_existing` es deliberadamente no-op: Alembic no puede saber si
creó esas tablas o si las heredó y por seguridad no destruye el dominio histórico.

La migración elimina únicamente preinscripciones huérfanas cuyo `session_id` no
existe, reconcilia `inscritos` contra la asociación y eleva un cupo positivo si era
menor al número real de inscritos. Después crea FK y checks para capacidades,
contadores y usos de tokens. Las asistencias y tokens usan `ON DELETE RESTRICT`;
una sesión con evidencia de asistencia no se elimina.
