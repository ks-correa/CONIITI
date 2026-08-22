param(
    [ValidateSet("start", "build", "secrets", "deploy", "status", "open", "stop-forward", "clean", "reset", "all")]
    [string]$Action = "all"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile = Join-Path $Root ".env.local"
$PortForwardStateFile = Join-Path $env:TEMP "coniiti-minikube-port-forward.state"
$PortForwardLogFile = Join-Path $env:TEMP "coniiti-minikube-port-forward.log"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-PlaceholderValue {
    param([string]$Value)
    return $Value -like "replace-with-*"
}

function Read-LocalEnv {
    if (Test-Path $EnvFile) {
        Get-Content $EnvFile | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
                return
            }

            $parts = $line.Split("=", 2)
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            if (-not (Test-PlaceholderValue $value)) {
                [Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
    }

    $defaults = @{
        POSTGRES_USER = "admin"
        POSTGRES_PASSWORD = "local-dev-postgres-password"
        MONGO_USER = "admin"
        MONGO_PASSWORD = "local-dev-mongo-password"
        MONGO_DB_NAME = "analytics_db"
        RABBITMQ_USER = "user"
        RABBITMQ_PASS = "local-dev-rabbitmq-password"
        RABBITMQ_EXCHANGE = "coniiti_events"
        JWT_SECRET_KEY = "local-dev-jwt-secret-change-me-32-chars"
        INTERNAL_SERVICE_TOKEN = "local-dev-internal-token"
        ATTENDANCE_SIGNING_KEY = "local-dev-attendance-signing-key-change-me"
        GRAFANA_ADMIN_USER = "coniiti-admin"
        GRAFANA_ADMIN_PASSWORD = "local-dev-grafana-password-change-me"
        FRONTEND_URL = "http://127.0.0.1:8080"
        SMTP_HOST = "smtp.example.local"
        SMTP_PORT = "587"
        SMTP_USER = ""
        SMTP_PASSWORD = ""
        EMAIL_FROM_NAME = "CONIITI"
        GOOGLE_CLIENT_ID = ""
        GOOGLE_CLIENT_SECRET = ""
        GOOGLE_REDIRECT_URI = "http://127.0.0.1:8080/api/auth/oauth/google/callback"
        MICROSOFT_TENANT_ID = "common"
        MICROSOFT_CLIENT_ID = ""
        MICROSOFT_CLIENT_SECRET = ""
        MICROSOFT_REDIRECT_URI = "http://127.0.0.1:8080/api/auth/oauth/microsoft/callback"
        PAYMENT_PROVIDER_MODE = "mock"
        PUBLIC_APP_URL = "http://127.0.0.1:8080"
        PAYPAL_CLIENT_ID = ""
        PAYPAL_CLIENT_SECRET = ""
        MP_ACCESS_TOKEN = ""
    }

    foreach ($key in $defaults.Keys) {
        $currentValue = [Environment]::GetEnvironmentVariable($key, "Process")
        if (-not $currentValue -or (Test-PlaceholderValue $currentValue)) {
            [Environment]::SetEnvironmentVariable($key, $defaults[$key], "Process")
        }
    }
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "No se encontro '$Name' en PATH."
    }
}

function Require-ClusterReady {
    Require-Command minikube
    Require-Command kubectl

    $status = minikube status --format "{{.Host}}|{{.Kubelet}}|{{.APIServer}}|{{.Kubeconfig}}" 2>$null
    if ($LASTEXITCODE -ne 0 -or $status -ne "Running|Running|Running|Configured") {
        throw "Minikube no esta listo. Ejecuta '.\scripts\minikube-local.ps1 start' antes de '$Action'."
    }
}

function Invoke-Kubectl {
    param([string[]]$KubectlArgs)
    kubectl --request-timeout=10s @KubectlArgs
}

function Test-LocalPortInUse {
    param([int]$Port)

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new(
            [System.Net.IPAddress]::Parse("127.0.0.1"),
            $Port
        )
        $listener.Start()
        return $false
    } catch {
        return $true
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

function Get-ActivePortForward {
    if (-not (Test-Path $PortForwardStateFile)) {
        return $null
    }

    $state = (Get-Content -Raw $PortForwardStateFile).Trim().Split("|")
    if ($state.Length -ne 2) {
        Remove-Item $PortForwardStateFile -Force -ErrorAction SilentlyContinue
        return $null
    }

    $processId = [int]$state[0]
    $port = [int]$state[1]
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item $PortForwardStateFile -Force -ErrorAction SilentlyContinue
        return $null
    }

    return @{ ProcessId = $processId; Port = $port }
}

function Stop-LocalPortForward {
    $state = Get-ActivePortForward
    if (-not $state) {
        Write-Host "No hay port-forward local activo para CONIITI."
        return
    }

    Stop-Process -Id $state.ProcessId -Force -ErrorAction SilentlyContinue
    Remove-Item $PortForwardStateFile -Force -ErrorAction SilentlyContinue
    Write-Host "Port-forward detenido."
}

function Start-LocalMinikube {
    Write-Step "Validando herramientas"
    Require-Command docker
    Require-Command minikube
    Require-Command kubectl

    Write-Step "Iniciando Minikube con Docker driver (2 CPU, 3072 MB RAM)"
    minikube start --driver=docker --cpus=2 --memory=3072 --disk-size=20g
}

function Use-MinikubeDocker {
    Write-Step "Conectando Docker al daemon de Minikube"
    minikube -p minikube docker-env --shell powershell | Invoke-Expression
}

function Build-LocalImages {
    Use-MinikubeDocker

    $images = @(
        @{ Tag = "auth-service:latest"; Path = "./microservices/auth-service" },
        @{ Tag = "users-service:latest"; Path = "./microservices/users-service" },
        @{ Tag = "agenda-service:latest"; Path = "./microservices/agenda-service" },
        @{ Tag = "notifications-service:latest"; Path = "./microservices/notifications-service" },
        @{ Tag = "payments-service:latest"; Path = "./microservices/payments-service" },
        @{ Tag = "analytics-service:latest"; Path = "./microservices/analytics-service" },
        @{ Tag = "files-service:latest"; Path = "./microservices/files-service" },
        @{ Tag = "raffles-service:latest"; Path = "./microservices/raffles-service" },
        @{ Tag = "frontend-app:latest"; Path = "./Front-end" }
    )

    foreach ($image in $images) {
        Write-Step "Construyendo $($image.Tag)"
        docker build -t $image.Tag (Join-Path $Root $image.Path)
    }
}

function Recreate-Secret {
    param(
        [string]$Name,
        [string[]]$Literals
    )

    Invoke-Kubectl @("delete", "secret", $Name, "--ignore-not-found", "--wait=false") | Out-Null
    $kubectlArgs = @("create", "secret", "generic", $Name)
    foreach ($literal in $Literals) {
        $kubectlArgs += "--from-literal=$literal"
    }
    Invoke-Kubectl $kubectlArgs | Out-Null
}

function New-KubernetesSecrets {
    Read-LocalEnv

    $postgresUser = $env:POSTGRES_USER
    $postgresPassword = $env:POSTGRES_PASSWORD
    $mongoUser = $env:MONGO_USER
    $mongoPassword = $env:MONGO_PASSWORD
    $mongoDb = $env:MONGO_DB_NAME
    $rabbitPass = $env:RABBITMQ_PASS

    Recreate-Secret "shared-postgres-secret" @(
        "POSTGRES_PASSWORD=$postgresPassword"
    )

    Recreate-Secret "analytics-mongo-secret" @(
        "MONGO_PASSWORD=$mongoPassword"
    )

    Recreate-Secret "rabbitmq-secret" @(
        "RABBITMQ_PASS=$rabbitPass"
    )

    Recreate-Secret "auth-service-secret" @(
        "DATABASE_URL=postgresql://$postgresUser`:$postgresPassword@shared-postgres-service:5432/authdb",
        "JWT_SECRET_KEY=$env:JWT_SECRET_KEY",
        "INTERNAL_SERVICE_TOKEN=$env:INTERNAL_SERVICE_TOKEN",
        "FRONTEND_URL=$env:FRONTEND_URL",
        "RABBITMQ_PASS=$rabbitPass",
        "SMTP_HOST=$env:SMTP_HOST",
        "SMTP_PORT=$env:SMTP_PORT",
        "SMTP_USER=$env:SMTP_USER",
        "SMTP_PASSWORD=$env:SMTP_PASSWORD",
        "EMAIL_FROM_NAME=$env:EMAIL_FROM_NAME",
        "GOOGLE_CLIENT_ID=$env:GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET=$env:GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI=$env:GOOGLE_REDIRECT_URI",
        "MICROSOFT_TENANT_ID=$env:MICROSOFT_TENANT_ID",
        "MICROSOFT_CLIENT_ID=$env:MICROSOFT_CLIENT_ID",
        "MICROSOFT_CLIENT_SECRET=$env:MICROSOFT_CLIENT_SECRET",
        "MICROSOFT_REDIRECT_URI=$env:MICROSOFT_REDIRECT_URI"
    )

    Recreate-Secret "users-service-secret" @(
        "DATABASE_URL=postgresql://$postgresUser`:$postgresPassword@shared-postgres-service:5432/usersdb",
        "JWT_SECRET_KEY=$env:JWT_SECRET_KEY",
        "INTERNAL_SERVICE_TOKEN=$env:INTERNAL_SERVICE_TOKEN"
    )

    Recreate-Secret "agenda-service-secret" @(
        "DATABASE_URL=postgresql://$postgresUser`:$postgresPassword@shared-postgres-service:5432/agenda_db",
        "JWT_SECRET_KEY=$env:JWT_SECRET_KEY",
        "INTERNAL_SERVICE_TOKEN=$env:INTERNAL_SERVICE_TOKEN",
        "ATTENDANCE_SIGNING_KEY=$env:ATTENDANCE_SIGNING_KEY",
        "RABBITMQ_PASS=$rabbitPass"
    )

    Recreate-Secret "notifications-service-secret" @(
        "DATABASE_URL=postgresql://$postgresUser`:$postgresPassword@shared-postgres-service:5432/notificationsdb",
        "INTERNAL_SERVICE_TOKEN=$env:INTERNAL_SERVICE_TOKEN",
        "RABBITMQ_PASS=$rabbitPass"
    )

    Recreate-Secret "payments-service-secret" @(
        "PAYMENTS_DATABASE_URL=postgresql://$postgresUser`:$postgresPassword@shared-postgres-service:5432/paymentsdb",
        "JWT_SECRET_KEY=$env:JWT_SECRET_KEY",
        "INTERNAL_SERVICE_TOKEN=$env:INTERNAL_SERVICE_TOKEN",
        "PAYMENT_PROVIDER_MODE=$env:PAYMENT_PROVIDER_MODE",
        "PUBLIC_APP_URL=$env:PUBLIC_APP_URL",
        "PAYPAL_CLIENT_ID=$env:PAYPAL_CLIENT_ID",
        "PAYPAL_CLIENT_SECRET=$env:PAYPAL_CLIENT_SECRET",
        "MP_ACCESS_TOKEN=$env:MP_ACCESS_TOKEN"
    )

    Recreate-Secret "files-service-secret" @(
        "FILES_DATABASE_URL=postgresql://$postgresUser`:$postgresPassword@shared-postgres-service:5432/filesdb",
        "JWT_SECRET_KEY=$env:JWT_SECRET_KEY",
        "INTERNAL_SERVICE_TOKEN=$env:INTERNAL_SERVICE_TOKEN"
    )

    Recreate-Secret "analytics-service-secret" @(
        "MONGO_URI=mongodb://$mongoUser`:$mongoPassword@analytics-mongo-service:27017/$mongoDb`?authSource=admin",
        "INTERNAL_SERVICE_TOKEN=$env:INTERNAL_SERVICE_TOKEN",
        "RABBITMQ_PASS=$rabbitPass"
    )

    Recreate-Secret "raffles-service-secret" @(
        "DATABASE_URL=postgresql://$postgresUser`:$postgresPassword@shared-postgres-service:5432/rafflesdb",
        "JWT_SECRET_KEY=$env:JWT_SECRET_KEY",
        "INTERNAL_SERVICE_TOKEN=$env:INTERNAL_SERVICE_TOKEN",
        "RABBITMQ_PASS=$rabbitPass"
    )

    Recreate-Secret "grafana-admin-secret" @(
        "admin-user=$env:GRAFANA_ADMIN_USER",
        "admin-password=$env:GRAFANA_ADMIN_PASSWORD"
    )
}

function Ensure-PostgresDatabases {
    $postgresUser = $env:POSTGRES_USER
    $databaseNames = @(
        "usersdb", "authdb", "agenda_db", "notificationsdb",
        "paymentsdb", "filesdb", "rafflesdb"
    )

    foreach ($databaseName in $databaseNames) {
        $query = "SELECT 1 FROM pg_database WHERE datname='$databaseName'"
        $exists = Invoke-Kubectl @(
            "exec", "deployment/shared-postgres", "--",
            "psql", "-U", $postgresUser, "-d", "default_db", "-tAc", $query
        )
        $existsValue = ($exists | Out-String).Trim()
        if ($existsValue -ne "1") {
            Write-Step "Creando base PostgreSQL faltante: $databaseName"
            Invoke-Kubectl @(
                "exec", "deployment/shared-postgres", "--",
                "createdb", "-U", $postgresUser, $databaseName
            )
        }
    }
}

function Deploy-LocalCluster {
    Require-ClusterReady
    Remove-LegacyResources

    Write-Step "Instalando CRDs de Traefik"
    Invoke-Kubectl @("apply", "-f", "https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-crd-definition-v1.yml")

    Write-Step "Creando Secrets locales"
    New-KubernetesSecrets

    Write-Step "Aplicando bases de datos y mensajeria"
    Invoke-Kubectl @("apply", "-f", (Join-Path $Root "Kubernetes/base-datos/"))
    Invoke-Kubectl @("apply", "-f", (Join-Path $Root "Kubernetes/mensajeria/"))

    Write-Step "Esperando infraestructura"
    Invoke-Kubectl @("rollout", "status", "deployment/shared-postgres", "--timeout=180s")
    Ensure-PostgresDatabases
    Invoke-Kubectl @("rollout", "status", "deployment/analytics-mongo", "--timeout=180s")
    Invoke-Kubectl @("rollout", "status", "deployment/rabbitmq", "--timeout=180s")

    Write-Step "Aplicando microservicios, observabilidad e ingress"
    Invoke-Kubectl @("apply", "-f", (Join-Path $Root "Kubernetes/microservicios/"))
    Invoke-Kubectl @("apply", "-f", (Join-Path $Root "Kubernetes/observabilidad/"))
    Invoke-Kubectl @("apply", "-f", (Join-Path $Root "Kubernetes/ingress/"))
}

function Show-LocalStatus {
    Require-ClusterReady

    Write-Step "Pods"
    Invoke-Kubectl @("get", "pods")

    Write-Step "Servicios"
    Invoke-Kubectl @("get", "svc")

    $deployments = @(
        "shared-postgres",
        "analytics-mongo",
        "rabbitmq",
        "auth-service",
        "users-service",
        "agenda-service",
        "notifications-service",
        "payments-service",
        "analytics-service",
        "files-service",
        "raffles-service",
        "frontend-app",
        "traefik",
        "alertmanager",
        "prometheus",
        "grafana"
    )

    foreach ($deployment in $deployments) {
        Invoke-Kubectl @("rollout", "status", "deployment/$deployment", "--timeout=90s")
    }
}

function Open-LocalApp {
    Require-ClusterReady
    Read-LocalEnv

    Write-Step "Exponiendo Traefik en localhost"

    try {
        $frontendUri = [Uri]$env:FRONTEND_URL
    } catch {
        throw "FRONTEND_URL debe ser una URL local valida para el port-forward de Minikube."
    }

    if (
        $frontendUri.Scheme -ne "http" -or
        $frontendUri.Host -notin @("127.0.0.1", "localhost") -or
        $frontendUri.Port -lt 1 -or
        $frontendUri.Port -gt 65535
    ) {
        throw "FRONTEND_URL debe usar http://127.0.0.1:<puerto> o http://localhost:<puerto> en Minikube local."
    }

    $port = $frontendUri.Port

    $state = Get-ActivePortForward
    if ($state) {
        if ($state.Port -ne $port) {
            throw "Hay un port-forward en $($state.Port), pero FRONTEND_URL usa $port. Ejecuta stop-forward y vuelve a abrir."
        }
        Write-Host "Port-forward activo en PID $($state.ProcessId)."
        Write-Host "Frontend: http://127.0.0.1:$($state.Port)"
        Write-Host "Estado:   http://127.0.0.1:$($state.Port)/estado"
        return
    }

    if (Test-LocalPortInUse $port) {
        throw "El puerto $port definido por FRONTEND_URL esta ocupado. Liberalo o configura el mismo puerto en FRONTEND_URL, PUBLIC_APP_URL y los callbacks OAuth."
    }

    $command = "kubectl --request-timeout=10s port-forward --address 127.0.0.1 svc/traefik-service ${port}:80 *> `"$PortForwardLogFile`""
    $process = Start-Process powershell `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command) `
        -WindowStyle Hidden `
        -PassThru

    Start-Sleep -Seconds 2
    if ($process.HasExited) {
        $details = if (Test-Path $PortForwardLogFile) { Get-Content -Raw $PortForwardLogFile } else { "" }
        throw "No se pudo iniciar port-forward a Traefik. $details"
    }

    "$($process.Id)|$port" | Set-Content -Encoding ASCII $PortForwardStateFile
    Write-Host "Port-forward activo en PID $($process.Id)."
    Write-Host "Frontend: http://127.0.0.1:$port"
    Write-Host "Estado:   http://127.0.0.1:$port/estado"
    Write-Host "Para cerrarlo: .\scripts\minikube-local.ps1 stop-forward"
}

function Clean-LocalCluster {
    Require-ClusterReady

    Write-Step "Eliminando recursos CONIITI del cluster local"
    Invoke-Kubectl @("delete", "-f", (Join-Path $Root "Kubernetes/ingress/"), "--ignore-not-found", "--wait=false")
    Invoke-Kubectl @("delete", "-f", (Join-Path $Root "Kubernetes/observabilidad/"), "--ignore-not-found", "--wait=false")
    Invoke-Kubectl @("delete", "-f", (Join-Path $Root "Kubernetes/microservicios/"), "--ignore-not-found", "--wait=false")
    Invoke-Kubectl @("delete", "-f", (Join-Path $Root "Kubernetes/mensajeria/"), "--ignore-not-found", "--wait=false")
    Invoke-Kubectl @("delete", "-f", (Join-Path $Root "Kubernetes/base-datos/"), "--ignore-not-found", "--wait=false")
}

function Remove-LegacyResources {
    Require-ClusterReady

    Write-Step "Retirando workloads heredados; los PVC legacy se conservan para recuperación"

    $legacyDeployments = @(
        "agenda-db-deployment",
        "auth-db-deployment",
        "users-db-deployment",
        "notifications-db-deployment",
        "payments-db-deployment",
        "analytics-mongo-deployment",
        "rabbitmq-deployment"
    )

    foreach ($deployment in $legacyDeployments) {
        Invoke-Kubectl @("delete", "deployment", $deployment, "--ignore-not-found", "--wait=false") | Out-Null
    }

    $legacyServices = @(
        "agenda-db-service",
        "auth-db-service",
        "users-db-service",
        "notifications-db-service",
        "payments-db-service"
    )

    foreach ($service in $legacyServices) {
        Invoke-Kubectl @("delete", "service", $service, "--ignore-not-found", "--wait=false") | Out-Null
    }

}

function Reset-LocalCluster {
    Stop-LocalPortForward
    Remove-LegacyResources
    Clean-LocalCluster
}

switch ($Action) {
    "start" { Start-LocalMinikube }
    "build" { Build-LocalImages }
    "secrets" { New-KubernetesSecrets }
    "deploy" { Deploy-LocalCluster }
    "status" { Show-LocalStatus }
    "open" { Open-LocalApp }
    "stop-forward" { Stop-LocalPortForward }
    "clean" { Clean-LocalCluster }
    "reset" { Reset-LocalCluster }
    "all" {
        Start-LocalMinikube
        Build-LocalImages
        Deploy-LocalCluster
        Show-LocalStatus
        Open-LocalApp
    }
}
