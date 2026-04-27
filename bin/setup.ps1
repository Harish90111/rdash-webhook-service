<#
.SYNOPSIS
Project setup and run helper for rdash-webhook-service.

.DESCRIPTION
This script documents the prerequisites for the project and provides
step-by-step commands for bootstrapping and running the server locally.

.PREREQUISITES
- Python 3.9+
- pip
- PostgreSQL 12+ and Redis 6+ for the full local stack
- OR SQLite for lightweight local development
- Docker Desktop and Docker Compose for container-based setup (optional)

.EXAMPLES
powershell -ExecutionPolicy Bypass -File .\bin\setup.ps1 -Action Help
powershell -ExecutionPolicy Bypass -File .\bin\setup.ps1 -Action Bootstrap -UseSqlite
powershell -ExecutionPolicy Bypass -File .\bin\setup.ps1 -Action RunServer
powershell -ExecutionPolicy Bypass -File .\bin\setup.ps1 -Action RunWorker
powershell -ExecutionPolicy Bypass -File .\bin\setup.ps1 -Action RunBeat
powershell -ExecutionPolicy Bypass -File .\bin\setup.ps1 -Action Docker
#>

[CmdletBinding()]
param(
    [ValidateSet("Help", "Bootstrap", "RunServer", "RunWorker", "RunBeat", "Docker")]
    [string]$Action = "Help",
    [switch]$UseSqlite
)

$ErrorActionPreference = "Stop"

$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = Resolve-Path (Join-Path $ScriptDirectory "..")
$VenvDirectory = Join-Path $RepositoryRoot ".venv"
$VenvPython = Join-Path $VenvDirectory "Scripts\python.exe"
$VenvCelery = Join-Path $VenvDirectory "Scripts\celery.exe"
$EnvExamplePath = Join-Path $RepositoryRoot ".env.example"
$EnvPath = Join-Path $RepositoryRoot ".env"
$RequirementsPath = Join-Path $RepositoryRoot "requirements.txt"
$ManagePyPath = Join-Path $RepositoryRoot "manage.py"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host $Title
    Write-Host ("=" * 78)
}

function Assert-CommandAvailable {
    param(
        [string]$CommandName,
        [string]$InstallHint
    )

    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "{0} is required. {1}" -f $CommandName, $InstallHint
    }
}

function Assert-FileExists {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path $Path)) {
        throw $Message
    }
}

function Ensure-VirtualEnvironment {
    Assert-CommandAvailable -CommandName "python" -InstallHint "Install Python 3.9 or newer and make sure it is on PATH."

    if (-not (Test-Path $VenvPython)) {
        Write-Host "Creating virtual environment at $VenvDirectory"
        Push-Location $RepositoryRoot
        try {
            & python -m venv .venv
        }
        finally {
            Pop-Location
        }
    }
}

function Ensure-EnvironmentFile {
    Assert-FileExists -Path $EnvExamplePath -Message ".env.example is missing from the repository root."

    if (-not (Test-Path $EnvPath)) {
        Copy-Item $EnvExamplePath $EnvPath
        Write-Host "Created $EnvPath from .env.example"
    }
}

function Enable-SqliteMode {
    Ensure-EnvironmentFile

    $envLines = @()
    if (Test-Path $EnvPath) {
        $envLines = Get-Content $EnvPath
    }

    $updated = $false
    for ($index = 0; $index -lt $envLines.Count; $index++) {
        if ($envLines[$index] -match '^USE_SQLITE=') {
            $envLines[$index] = "USE_SQLITE=True"
            $updated = $true
            break
        }
    }

    if (-not $updated) {
        $envLines += ""
        $envLines += "# Local lightweight development mode"
        $envLines += "USE_SQLITE=True"
    }

    Set-Content -Path $EnvPath -Value $envLines
    Write-Host "Enabled USE_SQLITE=True in $EnvPath"
}

function Show-Prerequisites {
    Write-Section "Prerequisites"
    Write-Host "1. Python 3.9+"
    Write-Host "2. pip"
    Write-Host "3. PostgreSQL 12+ and Redis 6+ for the full local stack"
    Write-Host "4. OR SQLite for lightweight local development"
    Write-Host "5. Docker Desktop and Docker Compose for the container path"
}

function Show-StepByStepCommands {
    Write-Section "Step By Step Commands"
    $commands = @"
Repository root:
    cd "$RepositoryRoot"

Bootstrap the project:
    python -m venv .venv
    .\.venv\Scripts\python -m pip install --upgrade pip
    .\.venv\Scripts\python -m pip install -r requirements.txt
    Copy-Item .env.example .env

Lightweight local mode with SQLite:
    Add this line to .env:
        USE_SQLITE=True

Full local mode with PostgreSQL and Redis:
    Keep USE_SQLITE=False (or omit it)
    Configure POSTGRES_* and CELERY_* values in .env

Prepare the app:
    .\.venv\Scripts\python manage.py migrate
    .\.venv\Scripts\python manage.py ensure_admin_user
    .\.venv\Scripts\python manage.py check

Run the web server:
    .\.venv\Scripts\python manage.py runserver

Run the Celery worker:
    .\.venv\Scripts\celery -A config worker -l info

Run Celery Beat:
    .\.venv\Scripts\celery -A config beat -l info

Run the full stack with Docker:
    docker-compose up --build
"@

    Write-Host $commands
}

function Ensure-AdminUser {
    Assert-FileExists -Path $VenvPython -Message ".venv is missing. Run the Bootstrap action first."
    Push-Location $RepositoryRoot
    try {
        & $VenvPython $ManagePyPath ensure_admin_user
    }
    finally {
        Pop-Location
    }
}

function Bootstrap-Project {
    Write-Section "Bootstrap"

    Ensure-VirtualEnvironment
    Ensure-EnvironmentFile

    Push-Location $RepositoryRoot
    try {
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r $RequirementsPath

        if ($UseSqlite) {
            Enable-SqliteMode
        }

        & $VenvPython $ManagePyPath migrate
        & $VenvPython $ManagePyPath ensure_admin_user
        & $VenvPython $ManagePyPath check
    }
    finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "Bootstrap completed."
    Write-Host "Dev admin bootstrap runs automatically."
    Write-Host "  Username : configured by DJANGO_SUPERUSER_USERNAME in .env (default: admin)"
    Write-Host "  Password : configured by DJANGO_SUPERUSER_PASSWORD in .env (default: admin)"
    Write-Host "Next:"
    Write-Host "  Run server : powershell -ExecutionPolicy Bypass -File .\bin\setup.ps1 -Action RunServer"
    Write-Host "  Run worker : powershell -ExecutionPolicy Bypass -File .\bin\setup.ps1 -Action RunWorker"
    Write-Host "  Run beat   : powershell -ExecutionPolicy Bypass -File .\bin\setup.ps1 -Action RunBeat"
}

function Run-Server {
    Assert-FileExists -Path $VenvPython -Message ".venv is missing. Run the Bootstrap action first."
    Push-Location $RepositoryRoot
    try {
        & $VenvPython $ManagePyPath migrate
        & $VenvPython $ManagePyPath ensure_admin_user
        & $VenvPython $ManagePyPath runserver
    }
    finally {
        Pop-Location
    }
}

function Run-Worker {
    Assert-FileExists -Path $VenvCelery -Message "Celery is not available in .venv. Run the Bootstrap action first."
    Push-Location $RepositoryRoot
    try {
        & $VenvCelery -A config worker -l info
    }
    finally {
        Pop-Location
    }
}

function Run-Beat {
    Assert-FileExists -Path $VenvCelery -Message "Celery is not available in .venv. Run the Bootstrap action first."
    Push-Location $RepositoryRoot
    try {
        & $VenvCelery -A config beat -l info
    }
    finally {
        Pop-Location
    }
}

function Run-DockerStack {
    Assert-CommandAvailable -CommandName "docker" -InstallHint "Install Docker Desktop."
    Push-Location $RepositoryRoot
    try {
        & docker-compose up --build
    }
    finally {
        Pop-Location
    }
}

switch ($Action) {
    "Help" {
        Show-Prerequisites
        Show-StepByStepCommands
    }
    "Bootstrap" {
        Show-Prerequisites
        Bootstrap-Project
    }
    "RunServer" {
        Run-Server
    }
    "RunWorker" {
        Run-Worker
    }
    "RunBeat" {
        Run-Beat
    }
    "Docker" {
        Show-Prerequisites
        Run-DockerStack
    }
}
