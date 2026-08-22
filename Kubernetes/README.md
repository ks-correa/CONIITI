# Despliegue Kubernetes

Los manifiestos actuales asumen el namespace `default` (incluido el subject del `ClusterRoleBinding` de Traefik). Si se usa otro namespace, ajuste esa referencia y cree allí ConfigMaps, Secrets y PVC antes de aplicar los Deployments.

Los scripts retiran Deployments y Services heredados, pero conservan sus PVC para recuperación. Elimine esos volúmenes únicamente después de verificar backup y migración; `clean` sí elimina los PVC declarados por los manifiestos actuales porque es una acción destructiva explícita.

Los manifiestos no contienen secretos. Antes del despliegue deben existir, como mínimo:

- `shared-postgres-secret`: `POSTGRES_PASSWORD`.
- `rabbitmq-secret`: `RABBITMQ_PASS`.
- `auth-service-secret`: `DATABASE_URL`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_TOKEN`, `FRONTEND_URL`, `RABBITMQ_PASS` y credenciales SMTP/OAuth aplicables.
- `users-service-secret`: `DATABASE_URL`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_TOKEN`.
- `agenda-service-secret`: `DATABASE_URL`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_TOKEN`, `ATTENDANCE_SIGNING_KEY`, `RABBITMQ_PASS`.
- `files-service-secret`: `FILES_DATABASE_URL`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_TOKEN`.
- `notifications-service-secret`: `DATABASE_URL`, `INTERNAL_SERVICE_TOKEN`, `RABBITMQ_PASS`.
- `analytics-service-secret`: `MONGO_URI`, `INTERNAL_SERVICE_TOKEN`, `RABBITMQ_PASS`.
- `payments-service-secret`: `PAYMENTS_DATABASE_URL`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_TOKEN` y credenciales del proveedor.
- `raffles-service-secret`: `DATABASE_URL`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_TOKEN`, `RABBITMQ_PASS`.
- `grafana-admin-secret`: `admin-user`, `admin-password` aleatorios y rotados.

Los videos se alojan normalmente en Files. Si se habilita un proveedor externo, declare `AGENDA_MEDIA_ALLOWED_HOSTS` en `agenda-service-config` con una lista explícita de hosts; vacío significa que Agenda rechaza URLs multimedia externas.

Los scripts locales usan `http://127.0.0.1:8080` para frontend, pagos y callbacks OAuth. El port-forward utiliza exactamente el puerto de `FRONTEND_URL` y falla si está ocupado, evitando callbacks desalineados. Si el proveedor exige otra URL, defina en `.env.local` valores coincidentes para `FRONTEND_URL`, `PUBLIC_APP_URL`, `GOOGLE_REDIRECT_URI` y `MICROSOFT_REDIRECT_URI`, y registre exactamente esos callbacks con cada proveedor.

Files conserva los binarios en `files-uploads-pvc` y los metadatos en `filesdb`. Las revisiones de configuración y los claims de sus assets se retienen indefinidamente para garantizar rollback seguro. Antes de escalar Files a más de una réplica, mueva los binarios a object storage compartido; el PVC actual es `ReadWriteOnce`.

Las URL PostgreSQL dentro del clúster usan `shared-postgres-service:5432`. El ConfigMap de inicialización crea `authdb`, `usersdb`, `agenda_db`, `filesdb`, `notificationsdb`, `paymentsdb` y `rafflesdb` únicamente al inicializar un volumen nuevo. Los scripts locales comprueban y crean idempotentemente cualquier base faltante; en un clúster administrado existente, cree las bases faltantes con su procedimiento aprobado antes del rollout.

Auth, Users, Agenda, Files y Raffles ejecutan `alembic upgrade head` antes de Uvicorn. Para producción con más de una réplica, sustituya ese comando por un Job de migración único previo al Deployment.

Orden recomendado:

1. PostgreSQL, MongoDB y RabbitMQ persistente.
2. Notifications/Analytics con colas v2 y DLQ.
3. Auth, Users y Files con migraciones.
4. Agenda con migración; el ConfigMap inicia `ASISTENCIA_CONFIRMADA_ENABLED=false`.
5. Raffles, frontend e ingress; el ConfigMap inicia `PREMIO_ADJUDICADO_ENABLED=false`.
6. Alertmanager, Prometheus y Grafana. Se accede a Grafana mediante port-forward o una ruta administrativa con TLS; no se exponen Prometheus, Alertmanager ni el dashboard inseguro de Traefik. Antes de producción, conecte el receiver `coniiti-operations` al canal aprobado inyectando sus secretos fuera del repositorio.

Después de comprobar que `notifications-service` y `analytics-service` están Ready, que existen las colas `notifications_queue_v2` y `analytics_queue_v2` y que sus DLQ están declaradas, habilite los publishers de forma secuencial y reinicie cada Deployment para recargar el ConfigMap:

```sh
kubectl patch configmap agenda-service-config --type merge -p '{"data":{"ASISTENCIA_CONFIRMADA_ENABLED":"true"}}'
kubectl rollout restart deployment/agenda-service
kubectl rollout status deployment/agenda-service

kubectl patch configmap raffles-service-config --type merge -p '{"data":{"PREMIO_ADJUDICADO_ENABLED":"true"}}'
kubectl rollout restart deployment/raffles-service
kubectl rollout status deployment/raffles-service
```

Los flags suspenden únicamente el despacho. Agenda y Raffles conservan eventos pendientes en sus outbox PostgreSQL mientras están deshabilitados, por lo que no se pierde evidencia. No use estos flags para omitir migraciones, autorización o validaciones.

## Verificación posterior

- Confirme probes Ready de PostgreSQL, MongoDB, RabbitMQ, aplicación, Traefik y observabilidad.
- Confirme los ocho targets `*-service` en Prometheus.
- Ejecute una alerta sintética y verifique agrupación en Alertmanager y entrega en el receiver aprobado.
- Compruebe que `/api/*/metrics` devuelve una ruta inexistente desde el gateway, mientras el scrape interno permanece disponible.
- Revise capacidad y backups de los PVC; Prometheus retiene 15 días y Alertmanager 120 horas.
