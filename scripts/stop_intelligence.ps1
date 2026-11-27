$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$processFile = Join-Path $projectRoot '.artifacts\local-services.json'
if (!(Test-Path -LiteralPath $processFile)) { Write-Host 'No managed service record.'; exit 0 }
$processRecords = Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
foreach ($entry in $processRecords) {
    if ($entry.root -ne $projectRoot) { throw 'Process record belongs to another project.' }
    $processInfo = Get-Process -Id ([int]$entry.id) -ErrorAction SilentlyContinue
    if (!$processInfo) { continue }
    $correctEntry = $entry.marker -in @('backend.app', 'vue-cli-service.js')
    $expectedStart = ([datetime]$entry.started).ToUniversalTime()
    # PID 可能被系统复用，路径和创建时间都匹配才终止其进程树。
    if ($correctEntry -and $processInfo.Path -eq $entry.executable -and $processInfo.StartTime.ToUniversalTime().Ticks -eq $expectedStart.Ticks) {
        & taskkill.exe /PID ([int]$entry.id) /T /F
        if ($LASTEXITCODE -ne 0) { throw "Could not stop service $($entry.id)." }
        Write-Host "Stopped project service $($entry.id)."
    } else { throw "Process $($entry.id) no longer matches this project; left running." }
}
Remove-Item -LiteralPath $processFile
