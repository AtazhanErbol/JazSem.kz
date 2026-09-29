param(
    [string]$DatabasePath = (Join-Path $PSScriptRoot '../../e2e-release.sqlite3'),
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$RuntimeName = '.runtime',
    [switch]$Seed
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = [IO.Path]::GetFullPath((Join-Path $projectRoot '../venv/Scripts/python.exe'))
$runtimePath = Join-Path $projectRoot $RuntimeName
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install the Python virtual environment at ../venv first.' }
$nodePath = (Get-Command node).Source
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend/node_modules/vite/bin/vite.js'))) { throw 'Install frontend dependencies first.' }
$manifestPath = Join-Path $runtimePath 'processes.json'
if (Test-Path -LiteralPath $manifestPath) {
    $previous = Get-Content -LiteralPath $manifestPath | ConvertFrom-Json
    foreach ($entry in $previous.PSObject.Properties) {
        if (Get-Process -Id $entry.Value -ErrorAction SilentlyContinue) {
            throw "A previously recorded process is still running: $($entry.Name), PID $($entry.Value). Check and stop previous JazSem services before restarting."
        }
    }
}
New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
$env:DJANGO_SETTINGS_MODULE = 'config.settings.local'
$env:DATABASE_URL = 'sqlite:///' + [IO.Path]::GetFullPath($DatabasePath).Replace('\', '/')
$env:JAZSEM_RUNTIME_DIR = $runtimePath
$env:FRONTEND_URL = "http://127.0.0.1:$FrontendPort"
$env:CSRF_TRUSTED_ORIGINS = $env:FRONTEND_URL
$env:API_PROXY = "http://127.0.0.1:$BackendPort"
foreach ($port in @($BackendPort, $FrontendPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop the previous JazSem process before restarting."
    }
}
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $pythonPath manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
    if ($Seed) {
        & $pythonPath manage.py seed_dev
        if ($LASTEXITCODE -ne 0) { throw 'Seed failed: set DEV_SEED_PASSWORD first' }
    }
} finally { Pop-Location }
$processes = @{}
foreach ($service in @(
    @{Name='backend'; Args=@('-u','manage.py','runserver',"127.0.0.1:$BackendPort",'--noreload')},
    @{Name='worker'; Args=@('-m','celery','-A','config','worker','--pool=solo','--concurrency=1','--loglevel=info')},
    @{Name='beat'; Args=@('-m','celery','-A','config','beat','--loglevel=info')}
)) {
    $p = Start-Process -FilePath $pythonPath -ArgumentList $service.Args -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath ($service.Name+'.out.log')) -RedirectStandardError (Join-Path $runtimePath ($service.Name+'.err.log'))
    $processes[$service.Name] = $p.Id
}
$p = Start-Process -FilePath $nodePath -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',"$FrontendPort",'--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'frontend.out.log') -RedirectStandardError (Join-Path $runtimePath 'frontend.err.log')
$processes['frontend'] = $p.Id
$processes | ConvertTo-Json | Set-Content (Join-Path $runtimePath 'processes.json')
Write-Output "JazSem started: $env:FRONTEND_URL. Logs: $runtimePath"
