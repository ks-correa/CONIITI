# Contratos integrados de CONIITI

Este documento fija los contratos implementados durante la integración. Todas las rutas públicas se consumen mediante `/api`; los prefijos se retiran en Traefik/nginx antes de llegar al servicio.

## Decisiones de dominio

- **Grupo** es una agrupación real de participantes. `users-service` conserva grupo, membresía, administrador acotado al grupo y auditoría. `group_admin` no es un rol global ni se añade al JWT.
- **Files** es dueño de binarios y de sus metadatos PostgreSQL: assets, referencias, documentos, cards CMS, configuración visual y revisiones.
- **Agenda** es la única dueña de edición, fechas, zona horaria, calendario, sedes, recursos de sede, cupos, preinscripciones y asistencia confirmada. Files no publica otra edición o fecha.
- **Raffles** es dueño del snapshot inmutable, selección, evidencia aleatoria, auditoría y publicación de sorteos. El navegador nunca calcula un ganador.
- **Auth** es dueño de credenciales y vigencia de sesión; **Users** sigue siendo dueño del rol y el perfil.

Los binarios de Files permanecen en el volumen `/app/uploads`; todo el catálogo y los metadatos viven en `filesdb`. El importador idempotente conserva los JSON heredados como evidencia y solo crea filas faltantes. Las revisiones de configuración y sus claims de assets tienen retención indefinida: no existe GC automático, de modo que un rollback histórico nunca apunta a un archivo borrado.

## Sesiones y revocación

Los JWT nuevos incluyen `sv` (`session_version`). Un cambio administrativo de rol/estado llama:

- `POST /internal/users/{user_id}/revoke-sessions` en Auth.
- `POST /internal/introspect`, body `{ "token": "..." }`, en Auth.

Ambas rutas requieren `X-Internal-Service-Token`. La introspección devuelve HTTP 200 con `{ "active": false }` para token inválido, expirado, usuario inactivo o versión revocada. Los servicios protegidos fallan cerrados con 503 si Auth no está disponible.

## Perfiles y grupos

- `GET|PATCH /api/users/me`: perfil propio. Nombre, apellido, institución, carrera, género, documento y código institucional son completables después del alta local, Google o Microsoft.
- `GET /api/users/admin/profiles` y `PATCH /api/users/admin/profiles/{id}`: solo superusuario, con filtros/paginación y revocación de sesión al cambiar rol o estado.
- `/api/users/groups`: CRUD global solo para superusuario.
- `/api/users/groups/{id}/members` y `/audit`: superusuario o administrador de esa membresía, según operación.
- `GET /api/users/me/groups`: grupos del usuario autenticado.
- `POST /internal/profile-summaries`: lote máximo de 200 IDs; solo devuelve `id` y `full_name` para Raffles.

Nunca se puede desactivar/eliminar el último superusuario activo ni autoescalar una cuenta.

Google y Microsoft crean/restauran únicamente la identidad base disponible (correo y nombre); el usuario completa después los campos opcionales desde su perfil. `superuser` conserva capacidad global sobre cuentas, grupos, configuración, contenido, agenda, asistencia y sorteos. `group_admin` solo tiene autoridad derivada de una membresía activa en su grupo.

## Files, personalización y módulos

- `POST /api/files/upload`: carga multipart de imagen, video o documento con límites separados, inspección MIME, checksum y nombre seguro.
- `GET /api/files/assets`, `GET /api/files/download/{filename}`: registro y descarga/streaming; video admite `Range`.
- `GET /api/files/site-config`: DTO público.
- `PUT /api/files/site-config`: solo superusuario, exige `If-Match`; conflicto concurrente = 412.
- `GET /api/files/site-config/revisions` y `POST /api/files/site-config/rollback/{revision}`: historial y rollback.
- `GET /internal/assets/{asset_id}` y `PUT|DELETE /internal/assets/{asset_id}/references/{owner_service}/{owner_type}/{owner_id}`: lookup/claim/release autenticados entre servicios.

Módulos ocultables: `agenda`, `speakers`, `committee`, `authors`, `gallery`, `memories`, `about`, `contact` y la sección `payments` de inicio. Inicio, autenticación, perfil, estado, seguridad, APIs internas y observabilidad no son ocultables.

Las imágenes, videos y documentos se suben por Files. Agenda referencia esos assets mediante claims internos; por defecto rechaza multimedia externa. `AGENDA_MEDIA_ALLOWED_HOSTS` solo habilita proveedores explícitos y una lista vacía mantiene la política Files-only. Un video puede asociar, además del asset principal, un `captions_asset_id` WebVTT (`text/vtt`) y un `transcript_asset_id` de texto. Cada slot tiene claim y URL resuelta independientes; el recurso continúa fuera del DTO público hasta que todos los assets requeridos estén activos y validados.

## Agenda, sedes y asistencia

- `GET|PUT /api/agenda/config`: calendario y zona horaria autoritativos; escritura con ETag para superusuario.
- `/api/agenda/venues`: sedes normalizadas, aforo y recursos ordenados. Los recursos Files —incluidos subtítulos y transcripción— permanecen pendientes hasta completar todos sus claims y no se publican antes.
- `POST /api/agenda/{session_id}/attendance-token`: token QR corto, firmado y con JTI; staff/superusuario.
- `POST /api/agenda/{session_id}/attendance/check-in`: check-in autenticado e idempotente.
- `POST /api/agenda/{session_id}/attendance/manual`: alternativa manual auditada para staff/superusuario.
- `GET /api/agenda/{session_id}/attendance`, `PATCH .../revoke` y `GET /api/agenda/me/attendance`.
- `POST /internal/attendance/eligibility-snapshot`: body `{session_ids?, confirmed_from?, confirmed_to?, require_registration}`; devuelve evidencia confirmada sin deduplicar usuarios.

La preinscripción nunca equivale a asistencia. Los cupos se validan dentro de una transacción con bloqueo.

## Sorteos

- `POST|GET /api/raffles`: crear/listar, solo superusuario.
- `POST /api/raffles/{id}/snapshot`: canonicaliza y fija asistencia elegible; es idempotente después del lock.
- `GET /api/raffles/{id}/eligibility`: paginado, solo superusuario.
- `POST /api/raffles/{id}/draw`: exige `Idempotency-Key`; usa entropía criptográfica y rechazo para evitar sesgo modular.
- `POST /api/raffles/{id}/publish`: transición explícita cuando se sortearon todos los ganadores.
- `GET /api/raffles/{id}/result`: el superusuario ve evidencia completa; el público solo después de publicar y recibe una referencia opaca, no PII.

Cada ganador conserva algoritmo, hash de snapshot, evidencia aleatoria y hash de auditoría. El evento se escribe en outbox en la misma transacción que el ganador.

## Eventos RabbitMQ

Envelope mínimo: `event_id`, `event` y timestamp/campos de dominio. No se incluye correo, documento, género ni nombre salvo que el consumidor los necesite explícitamente para una notificación privada.

| Routing key | Productor | Campos principales sin PII |
| --- | --- | --- |
| `usuario.registrado` | Auth | `event_id`, `event`; los datos de entrega quedan restringidos a Notifications |
| `ponencia.creada` | Agenda | `event_id`, `event`, título/ponente |
| `agenda.sesion_actualizada` | Agenda | `event_id`, `event`, cambios, afectados |
| `asistencia.confirmada` | Agenda | `event_id`, `event`, `session_id`, `user_id`, `confirmed_at` |
| `premio.adjudicado` | Raffles | `event_id`, `event`, `raffle_id`, `winner_user_id`, `draw_number`, `drawn_at`, `audit_hash` |

Notifications y Analytics usan colas v2 con DLX/DLQ. El orden de despliegue es: consumidores y DLQ, migraciones/productores, activación de `ASISTENCIA_CONFIRMADA_ENABLED` y, solo cuando ambos consumidores v2 estén listos, `PREMIO_ADJUDICADO_ENABLED=true`. Mientras este último flag está deshabilitado, Raffles conserva el evento durable en su outbox para publicarlo después sin perderlo.

Agenda aplica la misma regla: `ASISTENCIA_CONFIRMADA_ENABLED=false` suspende el despacho, pero la confirmación y su evento quedan persistidos en la outbox. `AGENDA_EVENT_OUTBOX_ENABLED` controla el worker, no la creación de evidencia durable. Los flags no descartan eventos ni deshabilitan autorización o validación de negocio.

Las bases Auth, Users, Agenda, Files y Raffles se administran con Alembic. En una instalación existente se realiza backup, upgrade y verificación antes del rollout; Kubernetes mantiene una réplica por manifiesto y debe reemplazar la migración al arranque por un Job único antes de escalar horizontalmente.

## Observabilidad

Prometheus scrapea `/metrics` directamente por la red interna. Gateway y nginx niegan `/api/*/metrics`. Prometheus no publica puerto al host en Compose; Grafana solo enlaza loopback y exige contraseña externa. En Kubernetes Prometheus, Alertmanager y Grafana son `ClusterIP`, y Grafana obtiene credenciales de `grafana-admin-secret`.

Las reglas alertan por servicio caído, tasa 5xx y latencia p95. Alertmanager conserva agrupaciones, silencios y estado durante 120 horas; el receiver `coniiti-operations` no contiene secretos ni un destino externo en el repositorio. Cada entorno debe inyectar el canal aprobado antes de considerar habilitada la entrega de notificaciones operativas.
