#!/usr/bin/env bash

# ==============================================================================
# minikube-local.sh — Linux Bash script for local staging in Minikube
# ==============================================================================

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env.local"
PORT_FORWARD_STATE_FILE="/tmp/coniiti-minikube-port-forward.state"
PORT_FORWARD_LOG_FILE="/tmp/coniiti-minikube-port-forward.log"

write_step() {
    echo -e "\n\e[36m==> $1\e[0m"
}

is_port_in_use() {
    # Returns 0 (true) if in use, 1 (false) if free
    if python3 -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', $1))" 2>/dev/null; then
        return 1 # Free
    else
        return 0 # In use
    fi
}

read_local_env() {
    if [ -f "$ENV_FILE" ]; then
        while IFS= read -r line || [ -n "$line" ]; do
            # Trim leading/trailing whitespace
            line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            if [[ -z "$line" || "$line" == \#* || "$line" != *"="* ]]; then
                continue
            fi
            key=$(echo "$line" | cut -d= -f1 | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            value=$(echo "$line" | cut -d= -f2- | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            # If value doesn't start with replace-with-
            if [[ ! "$value" =~ ^replace-with- ]]; then
                export "$key"="$value"
            fi
        done < "$ENV_FILE"
    fi

    # Set defaults if not set or set to replace-with-*
    declare -A defaults=(
        [POSTGRES_USER]="admin"
        [POSTGRES_PASSWORD]="local-dev-postgres-password"
        [MONGO_USER]="admin"
        [MONGO_PASSWORD]="local-dev-mongo-password"
        [MONGO_DB_NAME]="analytics_db"
        [RABBITMQ_USER]="user"
        [RABBITMQ_PASS]="local-dev-rabbitmq-password"
        [RABBITMQ_EXCHANGE]="coniiti_events"
        [JWT_SECRET_KEY]="local-dev-jwt-secret-change-me-32-chars"
        [INTERNAL_SERVICE_TOKEN]="local-dev-internal-token"
        [ATTENDANCE_SIGNING_KEY]="local-dev-attendance-signing-key-change-me"
        [GRAFANA_ADMIN_USER]="coniiti-admin"
        [GRAFANA_ADMIN_PASSWORD]="local-dev-grafana-password-change-me"
        [FRONTEND_URL]="http://127.0.0.1:8080"
        [SMTP_HOST]="smtp.example.local"
        [SMTP_PORT]="587"
        [SMTP_USER]=""
        [SMTP_PASSWORD]=""
        [EMAIL_FROM_NAME]="CONIITI"
        [GOOGLE_CLIENT_ID]=""
        [GOOGLE_CLIENT_SECRET]=""
        [GOOGLE_REDIRECT_URI]="http://127.0.0.1:8080/api/auth/oauth/google/callback"
        [MICROSOFT_TENANT_ID]="common"
        [MICROSOFT_CLIENT_ID]=""
        [MICROSOFT_CLIENT_SECRET]=""
        [MICROSOFT_REDIRECT_URI]="http://127.0.0.1:8080/api/auth/oauth/microsoft/callback"
        [PAYMENT_PROVIDER_MODE]="mock"
        [PUBLIC_APP_URL]="http://127.0.0.1:8080"
        [PAYPAL_CLIENT_ID]=""
        [PAYPAL_CLIENT_SECRET]=""
        [MP_ACCESS_TOKEN]=""
    )

    for key in "${!defaults[@]}"; do
        val="${!key}"
        if [[ -z "$val" || "$val" =~ ^replace-with- ]]; then
            export "$key"="${defaults[$key]}"
        fi
    done
}

require_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "\e[31mError: No se encontró '$1' en el PATH.\e[0m" >&2
        exit 1
    fi
}

require_cluster_ready() {
    require_command minikube
    require_command kubectl

    status=$(minikube status --format "{{.Host}}|{{.Kubelet}}|{{.APIServer}}|{{.Kubeconfig}}" 2>/dev/null || true)
    if [ "$status" != "Running|Running|Running|Configured" ]; then
        echo -e "\e[31mError: Minikube no está listo. Ejecuta './scripts/minikube-local.sh start' antes de '$ACTION'.\e[0m" >&2
        exit 1
    fi
}

get_active_port_forward() {
    if [ ! -f "$PORT_FORWARD_STATE_FILE" ]; then
        echo ""
        return
    fi
    state=$(cat "$PORT_FORWARD_STATE_FILE" | tr -d '\r\n')
    pid=$(echo "$state" | cut -d'|' -f1)
    p_port=$(echo "$state" | cut -d'|' -f2)
    if [ -z "$pid" ] || [ -z "$p_port" ]; then
        rm -f "$PORT_FORWARD_STATE_FILE"
        echo ""
        return
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PORT_FORWARD_STATE_FILE"
        echo ""
        return
    fi
    echo "$pid|$p_port"
}

stop_local_port_forward() {
    state=$(get_active_port_forward)
    if [ -z "$state" ]; then
        echo "No hay port-forward local activo para CONIITI."
        return
    fi
    pid=$(echo "$state" | cut -d'|' -f1)
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PORT_FORWARD_STATE_FILE"
    echo "Port-forward detenido."
}

start_local_minikube() {
    write_step "Validando herramientas"
    require_command docker
    require_command minikube
    require_command kubectl

    write_step "Iniciando Minikube con Docker driver (2 CPU, 3072 MB RAM)"
    minikube start --driver=docker --cpus=2 --memory=3072 --disk-size=20g
}

use_minikube_docker() {
    write_step "Conectando Docker al daemon de Minikube"
    eval $(minikube -p minikube docker-env)
}

build_local_images() {
    use_minikube_docker

    images=(
        "auth-service:latest|./microservices/auth-service"
        "users-service:latest|./microservices/users-service"
        "agenda-service:latest|./microservices/agenda-service"
        "notifications-service:latest|./microservices/notifications-service"
        "payments-service:latest|./microservices/payments-service"
        "analytics-service:latest|./microservices/analytics-service"
        "files-service:latest|./microservices/files-service"
        "raffles-service:latest|./microservices/raffles-service"
        "frontend-app:latest|./Front-end"
    )

    for img in "${images[@]}"; do
        tag=$(echo "$img" | cut -d'|' -f1)
        path=$(echo "$img" | cut -d'|' -f2)
        write_step "Construyendo $tag"
        docker build -t "$tag" "$ROOT/$path"
    done
}

recreate_secret() {
    local name=$1
    shift
    kubectl delete secret "$name" --ignore-not-found --wait=false &>/dev/null || true

    local args=(create secret generic "$name")
    for literal in "$@"; do
        args+=("--from-literal=$literal")
    done
    kubectl "${args[@]}" &>/dev/null
}

new_kubernetes_secrets() {
    read_local_env

    postgresUser="$POSTGRES_USER"
    postgresPassword="$POSTGRES_PASSWORD"
    mongoUser="$MONGO_USER"
    mongoPassword="$MONGO_PASSWORD"
    mongoDb="$MONGO_DB_NAME"
    rabbitPass="$RABBITMQ_PASS"

    recreate_secret "shared-postgres-secret" \
        "POSTGRES_PASSWORD=$postgresPassword"

    recreate_secret "analytics-mongo-secret" \
        "MONGO_PASSWORD=$mongoPassword"

    recreate_secret "rabbitmq-secret" \
        "RABBITMQ_PASS=$rabbitPass"

    recreate_secret "auth-service-secret" \
        "DATABASE_URL=postgresql://$postgresUser:$postgresPassword@shared-postgres-service:5432/authdb" \
        "JWT_SECRET_KEY=$JWT_SECRET_KEY" \
        "INTERNAL_SERVICE_TOKEN=$INTERNAL_SERVICE_TOKEN" \
        "FRONTEND_URL=$FRONTEND_URL" \
        "RABBITMQ_PASS=$rabbitPass" \
        "SMTP_HOST=$SMTP_HOST" \
        "SMTP_PORT=$SMTP_PORT" \
        "SMTP_USER=$SMTP_USER" \
        "SMTP_PASSWORD=$SMTP_PASSWORD" \
        "EMAIL_FROM_NAME=$EMAIL_FROM_NAME" \
        "GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID" \
        "GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET" \
        "GOOGLE_REDIRECT_URI=$GOOGLE_REDIRECT_URI" \
        "MICROSOFT_TENANT_ID=$MICROSOFT_TENANT_ID" \
        "MICROSOFT_CLIENT_ID=$MICROSOFT_CLIENT_ID" \
        "MICROSOFT_CLIENT_SECRET=$MICROSOFT_CLIENT_SECRET" \
        "MICROSOFT_REDIRECT_URI=$MICROSOFT_REDIRECT_URI"

    recreate_secret "users-service-secret" \
        "DATABASE_URL=postgresql://$postgresUser:$postgresPassword@shared-postgres-service:5432/usersdb" \
        "JWT_SECRET_KEY=$JWT_SECRET_KEY" \
        "INTERNAL_SERVICE_TOKEN=$INTERNAL_SERVICE_TOKEN"

    recreate_secret "agenda-service-secret" \
        "DATABASE_URL=postgresql://$postgresUser:$postgresPassword@shared-postgres-service:5432/agenda_db" \
        "JWT_SECRET_KEY=$JWT_SECRET_KEY" \
        "INTERNAL_SERVICE_TOKEN=$INTERNAL_SERVICE_TOKEN" \
        "ATTENDANCE_SIGNING_KEY=$ATTENDANCE_SIGNING_KEY" \
        "RABBITMQ_PASS=$rabbitPass"

    recreate_secret "notifications-service-secret" \
        "DATABASE_URL=postgresql://$postgresUser:$postgresPassword@shared-postgres-service:5432/notificationsdb" \
        "INTERNAL_SERVICE_TOKEN=$INTERNAL_SERVICE_TOKEN" \
        "RABBITMQ_PASS=$rabbitPass"

    recreate_secret "payments-service-secret" \
        "PAYMENTS_DATABASE_URL=postgresql://$postgresUser:$postgresPassword@shared-postgres-service:5432/paymentsdb" \
        "JWT_SECRET_KEY=$JWT_SECRET_KEY" \
        "INTERNAL_SERVICE_TOKEN=$INTERNAL_SERVICE_TOKEN" \
        "PAYMENT_PROVIDER_MODE=$PAYMENT_PROVIDER_MODE" \
        "PUBLIC_APP_URL=$PUBLIC_APP_URL" \
        "PAYPAL_CLIENT_ID=$PAYPAL_CLIENT_ID" \
        "PAYPAL_CLIENT_SECRET=$PAYPAL_CLIENT_SECRET" \
        "MP_ACCESS_TOKEN=$MP_ACCESS_TOKEN"

    recreate_secret "files-service-secret" \
        "FILES_DATABASE_URL=postgresql://$postgresUser:$postgresPassword@shared-postgres-service:5432/filesdb" \
        "JWT_SECRET_KEY=$JWT_SECRET_KEY" \
        "INTERNAL_SERVICE_TOKEN=$INTERNAL_SERVICE_TOKEN"

    recreate_secret "analytics-service-secret" \
        "MONGO_URI=mongodb://$mongoUser:$mongoPassword@analytics-mongo-service:27017/$mongoDb?authSource=admin" \
        "INTERNAL_SERVICE_TOKEN=$INTERNAL_SERVICE_TOKEN" \
        "RABBITMQ_PASS=$rabbitPass"

    recreate_secret "raffles-service-secret" \
        "DATABASE_URL=postgresql://$postgresUser:$postgresPassword@shared-postgres-service:5432/rafflesdb" \
        "JWT_SECRET_KEY=$JWT_SECRET_KEY" \
        "INTERNAL_SERVICE_TOKEN=$INTERNAL_SERVICE_TOKEN" \
        "RABBITMQ_PASS=$rabbitPass"

    recreate_secret "grafana-admin-secret" \
        "admin-user=$GRAFANA_ADMIN_USER" \
        "admin-password=$GRAFANA_ADMIN_PASSWORD"
}

ensure_postgres_databases() {
    local database_name
    local database_names=(
        usersdb authdb agenda_db notificationsdb paymentsdb filesdb rafflesdb
    )

    for database_name in "${database_names[@]}"; do
        if ! kubectl exec deployment/shared-postgres -- \
            psql -U "$POSTGRES_USER" -d default_db -tAc \
            "SELECT 1 FROM pg_database WHERE datname='$database_name'" \
            | grep -qx '1'; then
            write_step "Creando base PostgreSQL faltante: $database_name"
            kubectl exec deployment/shared-postgres -- \
                createdb -U "$POSTGRES_USER" "$database_name"
        fi
    done
}

remove_legacy_resources() {
    require_cluster_ready

    write_step "Retirando workloads heredados; los PVC legacy se conservan para recuperación"

    legacyDeployments=(
        "agenda-db-deployment"
        "auth-db-deployment"
        "users-db-deployment"
        "notifications-db-deployment"
        "payments-db-deployment"
        "analytics-mongo-deployment"
        "rabbitmq-deployment"
    )

    for dep in "${legacyDeployments[@]}"; do
        kubectl delete deployment "$dep" --ignore-not-found --wait=false &>/dev/null || true
    done

    legacyServices=(
        "agenda-db-service"
        "auth-db-service"
        "users-db-service"
        "notifications-db-service"
        "payments-db-service"
    )

    for svc in "${legacyServices[@]}"; do
        kubectl delete service "$svc" --ignore-not-found --wait=false &>/dev/null || true
    done

}

deploy_local_cluster() {
    require_cluster_ready
    remove_legacy_resources

    write_step "Instalando CRDs de Traefik"
    kubectl apply -f "https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-crd-definition-v1.yml"

    write_step "Creando Secrets locales"
    new_kubernetes_secrets

    write_step "Aplicando bases de datos y mensajeria"
    kubectl apply -f "$ROOT/Kubernetes/base-datos/"
    kubectl apply -f "$ROOT/Kubernetes/mensajeria/"

    write_step "Esperando infraestructura"
    kubectl rollout status deployment/shared-postgres --timeout=180s
    ensure_postgres_databases
    kubectl rollout status deployment/analytics-mongo --timeout=180s
    kubectl rollout status deployment/rabbitmq --timeout=180s

    write_step "Aplicando microservicios, observabilidad e ingress"
    kubectl apply -f "$ROOT/Kubernetes/microservicios/"
    kubectl apply -f "$ROOT/Kubernetes/observabilidad/"
    kubectl apply -f "$ROOT/Kubernetes/ingress/"
}

show_local_status() {
    require_cluster_ready

    write_step "Pods"
    kubectl get pods

    write_step "Servicios"
    kubectl get svc

    deployments=(
        "shared-postgres"
        "analytics-mongo"
        "rabbitmq"
        "auth-service"
        "users-service"
        "agenda-service"
        "notifications-service"
        "payments-service"
        "analytics-service"
        "files-service"
        "raffles-service"
        "frontend-app"
        "traefik"
        "alertmanager"
        "prometheus"
        "grafana"
    )

    for dep in "${deployments[@]}"; do
        kubectl rollout status deployment/$dep --timeout=90s || true
    done
}

open_local_app() {
    require_cluster_ready
    read_local_env

    write_step "Exponiendo Traefik en localhost"

    local frontend_url="${FRONTEND_URL:-http://127.0.0.1:8080}"
    if [[ ! "$frontend_url" =~ ^http://(127\.0\.0\.1|localhost)(:([0-9]{1,5}))?(/.*)?$ ]]; then
        echo -e "\e[31mError: FRONTEND_URL debe usar http://127.0.0.1:<puerto> o http://localhost:<puerto> en Minikube local.\e[0m" >&2
        exit 1
    fi

    local port="${BASH_REMATCH[3]:-80}"
    if (( port < 1 || port > 65535 )); then
        echo -e "\e[31mError: FRONTEND_URL contiene un puerto fuera de rango.\e[0m" >&2
        exit 1
    fi

    state=$(get_active_port_forward)
    if [ -n "$state" ]; then
        pid=$(echo "$state" | cut -d'|' -f1)
        p_port=$(echo "$state" | cut -d'|' -f2)
        if [ "$p_port" != "$port" ]; then
            echo -e "\e[31mError: Hay un port-forward en $p_port, pero FRONTEND_URL usa $port. Ejecuta stop-forward y vuelve a abrir.\e[0m" >&2
            exit 1
        fi
        write_step "Port-forward activo en PID $pid."
        echo "Frontend: http://127.0.0.1:$p_port"
        echo "Estado:   http://127.0.0.1:$p_port/estado"
        return
    fi

    if is_port_in_use "$port"; then
        echo -e "\e[31mError: El puerto $port definido por FRONTEND_URL esta ocupado. Liberalo o configura el mismo puerto en FRONTEND_URL, PUBLIC_APP_URL y los callbacks OAuth.\e[0m" >&2
        exit 1
    fi

    kubectl --request-timeout=10s port-forward --address 127.0.0.1 svc/traefik-service "${port}:80" > "$PORT_FORWARD_LOG_FILE" 2>&1 &
    pf_pid=$!

    sleep 2

    if ! kill -0 "$pf_pid" 2>/dev/null; then
        details=""
        if [ -f "$PORT_FORWARD_LOG_FILE" ]; then
            details=$(cat "$PORT_FORWARD_LOG_FILE")
        fi
        echo -e "\e[31mError: No se pudo iniciar port-forward a Traefik. $details\e[0m" >&2
        exit 1
    fi

    echo "$pf_pid|$port" > "$PORT_FORWARD_STATE_FILE"
    echo "Port-forward activo en PID $pf_pid."
    echo "Frontend: http://127.0.0.1:$port"
    echo "Estado:   http://127.0.0.1:$port/estado"
    echo "Para cerrarlo: ./scripts/minikube-local.sh stop-forward"
}

clean_local_cluster() {
    require_cluster_ready

    write_step "Eliminando recursos CONIITI del clúster local"
    kubectl delete -f "$ROOT/Kubernetes/ingress/" --ignore-not-found --wait=false &>/dev/null || true
    kubectl delete -f "$ROOT/Kubernetes/observabilidad/" --ignore-not-found --wait=false &>/dev/null || true
    kubectl delete -f "$ROOT/Kubernetes/microservicios/" --ignore-not-found --wait=false &>/dev/null || true
    kubectl delete -f "$ROOT/Kubernetes/mensajeria/" --ignore-not-found --wait=false &>/dev/null || true
    kubectl delete -f "$ROOT/Kubernetes/base-datos/" --ignore-not-found --wait=false &>/dev/null || true
}

reset_local_cluster() {
    stop_local_port_forward
    remove_legacy_resources
    clean_local_cluster
}

ACTION=${1:-all}

case "$ACTION" in
    start) start_local_minikube ;;
    build) build_local_images ;;
    secrets) new_kubernetes_secrets ;;
    deploy) deploy_local_cluster ;;
    status) show_local_status ;;
    open) open_local_app ;;
    stop-forward) stop_local_port_forward ;;
    clean) clean_local_cluster ;;
    reset) reset_local_cluster ;;
    all)
        start_local_minikube
        build_local_images
        deploy_local_cluster
        show_local_status
        open_local_app
        ;;
    *)
        echo "Uso: $0 {start|build|secrets|deploy|status|open|stop-forward|clean|reset|all}"
        exit 1
        ;;
esac
