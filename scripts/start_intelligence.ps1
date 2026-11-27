param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.artifacts'
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$vuePath = Join-Path $projectRoot 'demo\node_modules\@vue\cli-service\bin\vue-cli-service.js'
$processFile = Join-Path $runtimeRoot 'local-services.json'
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $vuePath)) {
    throw 'Project dependencies are missing. See docs/INTELLIGENCE.md.'
}
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$processRecords = @()
if (Test-Path -LiteralPath $processFile) {
    $savedRecords = Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
    $processRecords = @($savedRecords)
}
function Test-Endpoint($url) {
    try { return (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 }
    catch { return $false }
}
function Assert-PortFree($port) {
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    try { $probe.Start() }
    catch { throw "Port $port is occupied by another service. No process was stopped." }
    finally { $probe.Stop() }
}
# 仅登记本脚本创建的进程，不接管已运行的服务。
if (!(Test-Endpoint 'http://127.0.0.1:5000/api/intelligence/options')) {
    Assert-PortFree 5000
    $env:OMP_NUM_THREADS = '4'
    $env:PYTHONUTF8 = '1'
    $backend = Start-Process -FilePath $pythonPath -ArgumentList @('-B', '-m', 'flask', '--app', 'backend.app', 'run', '--host', '127.0.0.1', '--port', '5000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'backend.stdout.log') -RedirectStandardError (Join-Path $runtimeRoot 'backend.stderr.log')
    $processRecords += @{ id = $backend.Id; marker = 'backend.app'; root = $projectRoot; executable = $pythonPath; started = $backend.StartTime.ToUniversalTime().ToString('o') }
}
if (!(Test-Endpoint 'http://127.0.0.1:8080/')) {
    Assert-PortFree 8080
    $frontend = Start-Process -FilePath $nodePath -ArgumentList @('--openssl-legacy-provider', ('"' + $vuePath + '"'), 'serve', '--host', '127.0.0.1', '--port', '8080') -WorkingDirectory (Join-Path $projectRoot 'demo') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'frontend.stdout.log') -RedirectStandardError (Join-Path $runtimeRoot 'frontend.stderr.log')
    $processRecords += @{ id = $frontend.Id; marker = 'vue-cli-service.js'; root = $projectRoot; executable = $nodePath; started = $frontend.StartTime.ToUniversalTime().ToString('o') }
}
ConvertTo-Json -InputObject @($processRecords) | Set-Content -LiteralPath $processFile -Encoding UTF8
for ($attempt = 0; $attempt -lt 90; $attempt++) {
    if ((Test-Endpoint 'http://127.0.0.1:5000/api/intelligence/options') -and (Test-Endpoint 'http://127.0.0.1:8080/')) {
        Write-Host 'Ready: http://127.0.0.1:8080/#/intelligence'
        if (!$NoBrowser) { Start-Process 'http://127.0.0.1:8080/#/intelligence' }
        return
    }
    Start-Sleep -Seconds 1
}
throw 'Startup timed out. Check .artifacts/*.stderr.log.'
