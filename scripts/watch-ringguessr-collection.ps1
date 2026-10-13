param(
    [Parameter(Mandatory)][int]$CollectorProcessId,
    [ValidateRange(1, 10000)][int]$Target = 1000,
    [ValidateRange(1, 100)][int]$MaxGames = 100,
    [ValidateRange(1, 10)][int]$MaxAdditionalBatches = 9
)

# Follow the existing collector, then continue only after a normal batch budget.
# Transient errors restart sessions inside the collector. Exhausted retries,
# access restrictions, verification requirements, and unexpected exits stop work.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$progressPath = Join-Path $projectRoot 'data\collection-progress.json'
$watchPath = Join-Path $projectRoot 'data\collection-watch.json'
$collectorPath = Join-Path $PSScriptRoot 'collect-ringguessr.ps1'
$shellPath = (Get-Process -Id $PID).Path
$encoding = [System.Text.UTF8Encoding]::new($false)
$mutex = [System.Threading.Mutex]::new($false, 'Local\ApexRingGuessrCollectionWatch')
if (-not $mutex.WaitOne(0)) { throw 'A collection watcher is already active' }
$watch = [ordered]@{
    status='running'; process_id=$PID; collector_process_id=$CollectorProcessId;
    target=$Target; additional_batches=0; started_at=[DateTime]::UtcNow.ToString('o');
    unique_total=0; stop_reason=$null
}

function Save-Watch {
    $watch['updated_at'] = [DateTime]::UtcNow.ToString('o')
    $temporary = $watchPath + '.tmp'
    [System.IO.File]::WriteAllText($temporary, ($watch | ConvertTo-Json -Depth 5), $encoding)
    Move-Item -LiteralPath $temporary -Destination $watchPath -Force
}

function Refresh-Report {
    Push-Location -LiteralPath $projectRoot
    try {
        for ($attempt = 0; $attempt -lt 3; $attempt++) {
            $null = & $pythonPath -m ringlab.report
            if ($LASTEXITCODE -eq 0) { return }
            Start-Sleep -Milliseconds 200
        }
        throw 'Dataset report generation failed'
    } finally { Pop-Location }
}

function Read-Progress {
    for ($attempt = 0; $attempt -lt 5; $attempt++) {
        try {
            $snapshot = Get-Content -LiteralPath $progressPath -Raw -Encoding utf8 | ConvertFrom-Json
            if (-not $snapshot.batch_id -or -not $snapshot.status) { throw 'Incomplete progress snapshot' }
            return $snapshot
        } catch {
            if ($attempt -eq 4) { throw }
            Start-Sleep -Milliseconds 100
        }
    }
}

try {
    $progress = Read-Progress
    $batchStartTotal = $progress.unique_total
    Save-Watch
    while ($true) {
        while (Get-Process -Id $watch.collector_process_id -ErrorAction SilentlyContinue) {
            $progress = Read-Progress
            $watch.unique_total = $progress.unique_total
            Save-Watch
            Refresh-Report
            Start-Sleep -Seconds 30
        }
        $progress = Read-Progress
        $watch.unique_total = $progress.unique_total
        Refresh-Report
        # Never restart a stopped/failed batch, including 403/429/CAPTCHA.
        if ($progress.status -ne 'budget_reached') {
            $watch.status = if ($progress.status -eq 'running') { 'interrupted' } else { $progress.status }
            $watch.stop_reason = if ($progress.status -eq 'running') { 'Collector exited unexpectedly; no automatic restart' } else { $progress.stop_reason }
            break
        }
        if ($progress.unique_total -ge $Target) { $watch.status='target_reached'; break }
        if ($progress.unique_total -le $batchStartTotal) {
            $watch.status='stopped'; $watch.stop_reason='Completed batch produced no new samples'; break
        }
        if ($watch.additional_batches -ge $MaxAdditionalBatches) { $watch.status='budget_reached'; break }
        $batchStartTotal = $progress.unique_total
        $watch.additional_batches++
        $logPrefix = Join-Path $projectRoot ('data\raw\collection-background-' + [guid]::NewGuid().ToString('N'))
        $arguments = @('-NoProfile', '-File', ('"' + $collectorPath + '"'), '-Target', $Target,
            '-MaxGames', $MaxGames, '-DelaySeconds', '2', '-Mode', 'PUBLIC')
        $collector = Start-Process -FilePath $shellPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput ($logPrefix + '.log') -RedirectStandardError ($logPrefix + '.error.log')
        $watch.collector_process_id = $collector.Id
        Save-Watch
    }
} catch {
    $watch.status='stopped'
    $watch.stop_reason=$_.Exception.Message
} finally {
    $watch['ended_at'] = [DateTime]::UtcNow.ToString('o')
    Save-Watch
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
