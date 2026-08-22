# CONIITI

Plataforma integral para la gestión del Congreso Internacional de Innovación y Tecnología: agenda, sedes, contenido multimedia, usuarios, comités, grupos, asistencia, sorteos, pagos, analítica y observabilidad.

`CONIITI/` es el repositorio canónico y la única carpeta necesaria para ejecutar, probar, migrar y desplegar la solución. Todo el código, los contratos, las migraciones, los manifiestos y la documentación están incluidos aquí; no existen dependencias de ejecución hacia otro proyecto local.

## Estado de la integración

La integración funcional está terminada. El repositorio incluye:

- frontend React/Vite con diseño CONIITI, navegación pública y paneles administrativos;
- autenticación local y OAuth con Google y Microsoft mediante cookie `HttpOnly`;
- perfil progresivo para completar institución, carrera, género, documento y código institucional después del registro;
- administración de usuarios, comité, grupos, membresías y administradores limitados a cada grupo;
- CMS, identidad visual, país invitado, textos y visibilidad de módulos públicos;
- biblioteca de imágenes, videos, documentos, subtítulos WebVTT y transcripciones;
- agenda autoritativa con edición, fechas, zona horaria, sesiones, sedes, recursos multimedia y cupos;
- confirmación de asistencia mediante QR o registro manual auditado;
- sorteos reproducibles y auditables basados en asistencia confirmada;
- pagos, notificaciones y analítica integrados;
- PostgreSQL para metadatos transaccionales, MongoDB para analítica y RabbitMQ para eventos;
- Prometheus, Alertmanager y Grafana;
- Docker Compose, Kubernetes/Minikube y validación continua con GitHub Actions.

El despliegue de producción requiere credenciales reales, contenido aprobado y la configuración operativa indicada en la sección [Preparación para producción](#preparación-para-producción).

## Arquitectura

| Componente | Responsabilidad | Persistencia |
| --- | --- | --- |
| `Front-end` | Aplicación pública y paneles de gestión | Navegador |
| `auth-service` | Credenciales, OAuth, OTP, JWT, sesiones y revocación | `authdb` |
| `users-service` | Perfiles, roles, comité, grupos y membresías | `usersdb` |
| `agenda-service` | Configuración del evento, sesiones, sedes, cupos y asistencia | `agenda_db` |
| `files-service` | Binarios, catálogo, galería, CMS y configuración visual | `filesdb` + volumen de uploads |
| `payments-service` | Operaciones de pago | `paymentsdb` |
| `raffles-service` | Elegibilidad, sorteos, ganadores y auditoría | `rafflesdb` |
| `analytics-service` | Métricas de negocio | MongoDB |
| `notifications-service` | Notificaciones y trazabilidad de entrega | `notificationsdb` |
| Traefik | Gateway y enrutamiento `/api/*` | Configuración |
| RabbitMQ | Eventos de dominio, colas v2 y DLQ | Volumen persistente |
| Prometheus / Alertmanager / Grafana | Métricas, alertas y tableros | Volúmenes persistentes |

Los dominios no comparten tablas ni claves foráneas entre bases. La coordinación usa APIs internas autenticadas y eventos con outbox durable.

## Estructura del repositorio

```text
CONIITI/
├── Front-end/                 # React y Vite
├── microservices/             # Ocho servicios FastAPI
├── postgres-init/             # Creación de bases PostgreSQL
├── traefik/                   # Gateway para Docker Compose
├── prometheus/                # Scrape y reglas de alerta
├── alertmanager/              # Enrutamiento de alertas
├── grafana/                   # Datasource y dashboard provisionados
├── Kubernetes/                # Bases, mensajería, servicios, ingress y observabilidad
├── scripts/                   # Automatización local de Minikube
├── docs/                      # Plan final, contratos y documentación operativa
├── docker-compose.yml
└── .env.example
```

## Inicio rápido con Docker Compose

### Requisitos

- Docker Desktop o Docker Engine con Compose v2.
- Git.
- Al menos 4 GB de memoria disponibles para los contenedores.

Node.js 24 y Python 3.11 solo son necesarios si se ejecutan las pruebas fuera de Docker.

### 1. Configurar variables

Desde la raíz de `CONIITI`:

```powershell
Copy-Item .env.example .env
```

En Linux o macOS:

```bash
cp .env.example .env
```

Reemplaza todos los valores `replace-with-*`. El archivo `.env` está ignorado por Git y no debe versionarse.

Para desarrollo sin proveedores externos se puede conservar `PAYMENT_PROVIDER_MODE=mock`. Google, Microsoft y SMTP necesitan credenciales reales para probar sus respectivos flujos.

### 2. Construir y levantar

```powershell
docker compose up --build
```

La primera ejecución crea las siete bases PostgreSQL, aplica las migraciones Alembic, prepara MongoDB/RabbitMQ y arranca los ocho microservicios, el frontend y la observabilidad.

### 3. Abrir la aplicación

| Recurso | URL local |
| --- | --- |
| Frontend | `http://localhost` |
| Estado de servicios | `http://localhost/estado` |
| Auth | `http://localhost/api/auth` |
| Usuarios | `http://localhost/api/users` |
| Comité | `http://localhost/api/committees/members` |
| Agenda | `http://localhost/api/agenda` |
| Files | `http://localhost/api/files` |
| Pagos | `http://localhost/api/payments` |
| Notificaciones | `http://localhost/api/notifications` |
| Analítica | `http://localhost/api/analytics` |
| Sorteos | `http://localhost/api/raffles` |
| Grafana | `http://127.0.0.1:3000` o `GRAFANA_PORT` |

### Operación cotidiana

```powershell
docker compose ps
docker compose logs -f
docker compose config --quiet
docker compose down
```

`docker compose down` conserva los volúmenes. El siguiente comando también elimina bases, uploads y datos de observabilidad locales:

```powershell
docker compose down -v
```

## Minikube local

Minikube ofrece un entorno local más cercano a Kubernetes. Requiere Docker, Minikube y kubectl.

Configura sus secretos en `.env.local`:

```powershell
Copy-Item .env.example .env.local
```

Despliegue completo en Windows:

```powershell
.\scripts\minikube-local.ps1 all
```

En Linux o macOS:

```bash
chmod +x scripts/minikube-local.sh
./scripts/minikube-local.sh all
```

La acción `all` inicia Minikube, construye imágenes, crea Secrets, comprueba las bases PostgreSQL, aplica infraestructura/microservicios/observabilidad, valida rollouts y abre el port-forward. No borra PVC existentes.

Acciones disponibles:

```text
start | build | secrets | deploy | status | open | stop-forward | clean | reset | all
```

`open` usa exactamente el puerto de `FRONTEND_URL` —8080 por defecto— para mantener alineados el frontend, pagos y callbacks OAuth. `clean` y `reset` son acciones destructivas para los recursos locales actuales; los PVC heredados se preservan para recuperación.

La lista completa de Secrets y el orden de rollout están en [Kubernetes/README.md](Kubernetes/README.md).

## Autenticación y perfiles

- El registro local solicita únicamente la identidad mínima.
- Google y Microsoft crean o enlazan la cuenta usando correo verificado por el proveedor.
- El usuario completa posteriormente los campos académicos e institucionales desde su perfil.
- Los JWT incluyen versión de sesión y se entregan mediante cookie `HttpOnly`.
- Los microservicios protegidos consultan Auth y fallan cerrados si no pueden validar estado, rol o revocación.
- Las URLs OAuth se toman de configuración canónica; no se construyen desde cabeceras `Host` u `Origin`.

Para Docker Compose registra estos callbacks en los proveedores:

```text
http://localhost/api/auth/oauth/google/callback
http://localhost/api/auth/oauth/microsoft/callback
```

Para Minikube local, los valores predeterminados usan `http://127.0.0.1:8080`.

## Archivos, multimedia y personalización

Files almacena los metadatos en PostgreSQL `filesdb` y los binarios en su volumen persistente. Valida tamaño, firma y MIME, genera nombres internos, calcula checksum y soporta `Range` para streaming de video.

El catálogo se reutiliza para:

- videos, posters, subtítulos WebVTT y transcripciones de sedes;
- galería de imágenes y videos;
- documentos y memorias;
- logotipos y assets de marca;
- tarjetas y textos del CMS.

Agenda registra claims/releases idempotentes sobre los assets. Un recurso no se publica hasta que todos sus archivos estén resueltos y Files impide eliminar contenido todavía referenciado.

El superusuario puede ocultar agenda, conferencistas, comité, autores, galería, memorias, acerca de, contacto y la sección de pagos. Inicio base, autenticación, perfil, estado y componentes internos no pueden ocultarse.

## Usuarios, grupos y permisos

| Rol o permiso | Alcance |
| --- | --- |
| `superuser` | Administración total de todos los dominios integrados |
| `staff` | Operación autorizada de agenda, asistencia, contenido y pagos |
| `group_admin` | Membresías del grupo específico donde fue asignado; no es un rol global |
| `university_community` / `external` | Perfil propio, consulta, registro, asistencia y operaciones propias |

El backend evita autoescalada, protege al último superusuario activo y al último administrador de cada grupo, y registra auditoría de cambios administrativos.

## Migraciones de base de datos

Auth, Users, Agenda, Files y Raffles usan Alembic. Docker Compose y los manifiestos actuales ejecutan `alembic upgrade head` antes de iniciar cada servicio.

Ejemplo manual:

```powershell
cd microservices/auth-service
alembic upgrade head
alembic check
```

En producción:

1. crea un backup y verifica restauración sobre una copia;
2. configura la URL de base correspondiente;
3. ejecuta `alembic upgrade head` una sola vez por servicio;
4. realiza smoke tests;
5. despliega las aplicaciones;
6. mueve la migración a un Job previo antes de escalar a varias réplicas.

Files ya no usa JSON como fuente de verdad. Su importación heredada es idempotente y los metadatos posteriores residen en `filesdb`.

## Pruebas y calidad

Resultado de cierre de la integración:

- backend: 123 pruebas aprobadas;
- frontend: 14 pruebas aprobadas;
- total: 137 pruebas aprobadas;
- ESLint y Ruff sin hallazgos;
- build estricto de Vite correcto;
- `npm audit`: 0 vulnerabilidades;
- ciclos Alembic sin drift;
- YAML, Kubernetes, Prometheus, Alertmanager y Grafana validados.

Frontend:

```powershell
cd Front-end
npm ci
npm run lint
npm test
npm run build:strict
npm audit --audit-level=high
```

Backend, desde cada microservicio:

```powershell
python -m pip install -r requirements.txt pytest
$env:PYTHONPATH='.'
python -m pytest -q
```

Lint backend desde la raíz:

```powershell
ruff check microservices
```

El workflow [.github/workflows/ci.yml](.github/workflows/ci.yml) automatiza pruebas, lint, auditoría, builds Docker, migraciones contra PostgreSQL 16 y validación de infraestructura.

## Observabilidad

- `/estado` muestra disponibilidad y latencia de los ocho microservicios.
- Cada servicio FastAPI publica métricas solo dentro de la red interna.
- Prometheus evalúa disponibilidad, tasa de errores 5xx y latencia p95.
- Alertmanager agrupa alertas; el receiver externo se configura fuera del repositorio.
- Grafana incluye paneles generales y métricas de CMS, Files, usuarios, grupos, agenda, sedes, asistencia y sorteos.
- El gateway bloquea la exposición pública de `/metrics`.

## Seguridad

- No se versionan secretos reales.
- Contraseñas y OTP usan funciones criptográficas apropiadas.
- Cookies de autenticación son `HttpOnly` y las sesiones pueden revocarse.
- Los endpoints administrativos validan rol y ámbito en backend.
- Files inspecciona firma/MIME y restringe tamaños por tipo de archivo.
- Agenda rechaza hosts multimedia externos salvo allowlist explícita.
- Sorteos usan entropía segura, snapshots inmutables, idempotencia y auditoría.
- Los eventos evitan incluir documento, género, correo u otra PII innecesaria.
- Prometheus, Alertmanager y el dashboard de Traefik no se exponen públicamente.

## Preparación para producción

Antes de abrir tráfico real:

1. reemplaza y rota todos los Secrets;
2. configura Google, Microsoft, SMTP y el proveedor de pagos;
3. registra exactamente los callbacks OAuth del dominio final;
4. sube a Files los videos, posters, subtítulos, transcripciones e imágenes aprobados;
5. conecta el receiver `coniiti-operations` de Alertmanager;
6. ejecuta backup, migraciones y smoke tests sobre una copia de los datos;
7. verifica targets de Prometheus, alertas sintéticas, colas y DLQ;
8. usa object storage compartido antes de escalar Files a varias réplicas, o conserva una sola réplica con su PVC actual.

## Documentación

- [Plan e informe final de integración](docs/PLAN_INTEGRACION_PROPUESTAS.md)
- [Contratos y eventos](docs/contracts_and_events.md)
- [Despliegue Kubernetes](Kubernetes/README.md)
- [Arquitectura de microservicios](docs/arquitectura_microservicios.md)
- [Observabilidad](docs/observabilidad.md)
- [Matriz de cumplimiento](docs/matriz_cumplimiento.md)

No se realizó un despliegue remoto desde esta máquina. El repositorio queda preparado para validación local y CI; el paso a producción depende únicamente de infraestructura, secretos, contenido y procedimientos operativos del entorno de destino.
