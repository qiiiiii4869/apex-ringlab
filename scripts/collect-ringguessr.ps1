param(
    [ValidateRange(1, 10000)][int]$Target = 100,
    [ValidateRange(1, 100)][int]$MaxGames = 35,
    [ValidateRange(0.5, 60)][double]$DelaySeconds = 1.5,
    [ValidateSet('ALGS', 'PUBLIC', 'BOTH')][string]$Mode = 'BOTH',
    [Alias('MaxServerRecoveries')][ValidateRange(0, 20)][int]$MaxRecoveries = 5,
    [ValidateRange(5, 900)][int]$RecoveryDelaySeconds = 30,
    [ValidateRange(5, 900)][int]$MaxRecoveryDelaySeconds = 300
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$rawDirectory = Join-Path $projectRoot 'data\raw'
$datasetPath = Join-Path $projectRoot 'data\rings.json'
$pairsPath = Join-Path $rawDirectory 'ringguessr-pairs.jsonl'
$progressPath = Join-Path $projectRoot 'data\collection-progress.json'
$encoding = [System.Text.UTF8Encoding]::new($false)
$batchId = [guid]::NewGuid().ToString('N')
$site = 'https://apexlegendsstatus.com'
$api = $site + '/algs/ringguesser/api/'
[string[]]$modes = if ($Mode -eq 'BOTH') { @('PUBLIC', 'ALGS') } else { @($Mode) }
$statistics = [ordered]@{ batch_id=$batchId; target=$Target; source_mode=$Mode; status='running'; started_at=[DateTime]::UtcNow.ToString('o');
    games=0; rounds=0; worlds_edge_pairs=0; other_maps=0; unique_total=0; stop_reason=$null;
    server_recoveries=0; recoveries=0; consecutive_recoveries=0; max_recoveries=$MaxRecoveries;
    recovery_delay_seconds=$RecoveryDelaySeconds; max_recovery_delay_seconds=$MaxRecoveryDelaySeconds;
    recovery_events=@(); request_stage=$null; next_retry_at=$null; last_error=$null }

function Save-Progress {
    $statistics['updated_at'] = [DateTime]::UtcNow.ToString('o')
    $temporary = $progressPath + '.tmp'
    [System.IO.File]::WriteAllText($temporary, ($statistics | ConvertTo-Json -Depth 5), $encoding)
    Move-Item -LiteralPath $temporary -Destination $progressPath -Force
}

function Read-ApiJson($response) {
    if ($response.StatusCode -ne 200) {
        throw ('HTTP ' + $response.StatusCode + '; API request failed')
    }
    try { $result = $response.Content | ConvertFrom-Json } catch {
        if ($response.Content -match '(?i)captcha|turnstile|cloudflare|verify.{0,30}human|access denied|rate.?limit') {
            throw 'Verification or access restriction; collection stopped'
        }
        throw 'Non-JSON response; restart the guest session'
    }
    # Inspect only in memory; never log arbitrary response fields or credentials.
    $diagnostic = @($result.code, $result.error, $result.message) | ConvertTo-Json -Compress -Depth 5
    if ($diagnostic -match '(?i)captcha|verif|turnstile|cloudflare|challenge|rate.?limit|too many|access.?denied|forbidden|unauthori[sz]ed|blocked|banned|cooldown|throttl|human') {
        throw 'Verification or access restriction; collection stopped'
    }
    if ($result.error) {
        throw 'API error; restart the guest session'
    }
    if (-not $result.success) { throw 'API response did not confirm success' }
    return $result
}

function Sync-Dataset {
    if (-not (Test-Path -LiteralPath $pairsPath)) { return }
    Push-Location -LiteralPath $projectRoot
    try {
        $output = & $pythonPath -m ringlab.ingest $pairsPath --allow-quarantine
        if ($LASTEXITCODE -ne 0) { throw 'Sample validation failed; inspect collection-report.json' }
        $report = $output | ConvertFrom-Json
        $statistics.unique_total = $report.total
        Write-Output ('DATA total=' + $report.total + ' public=' + $report.source_modes.PUBLIC + ' algs=' + $report.source_modes.ALGS + ' quarantined=' + $report.invalid)
    } finally { Pop-Location }
}

if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Missing .venv Python environment' }
New-Item -ItemType Directory -Path $rawDirectory -Force | Out-Null
if (Test-Path -LiteralPath $datasetPath) {
    $statistics.unique_total = @((Get-Content -LiteralPath $datasetPath -Raw -Encoding utf8 | ConvertFrom-Json)).Count
}
$collectionMutex = [System.Threading.Mutex]::new($false, 'Local\ApexRingGuessrCollector')
try { $ownsCollectionMutex = $collectionMutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $ownsCollectionMutex = $true }
if (-not $ownsCollectionMutex) { $collectionMutex.Dispose(); throw 'A collector is already active; no second collector started' }

try {
    Save-Progress
    if ($statistics.unique_total -ge $Target) {
        $statistics.status = 'target_reached'
    } else {
        for ($game = 0; $game -lt $MaxGames; $game++) {
          try {
            $statistics.status = 'running'
            $statistics.next_retry_at = $null
            $sourceMode = $modes[$game % $modes.Count]
            if ($sourceMode -notin @('PUBLIC', 'ALGS')) { throw 'Invalid source mode; no request sent' }
            # Only normal guest game requests. Keep the session in memory.
            $statistics.request_stage = 'gamePage'
            $entry = Invoke-WebRequest -Uri ($site + '/algs/ring-guessr') -SessionVariable gameSession -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 25
            if ($entry.StatusCode -ne 200) { throw ('HTTP ' + $entry.StatusCode + '; API request failed') }
            if ($entry.Content -notmatch 'ringGuesser_play') { throw 'Game page unavailable or requires verification' }
            Start-Sleep -Milliseconds ([int]($DelaySeconds * 1000))
            $statistics.request_stage = 'startGame'
            $startResponse = Invoke-WebRequest -Uri ($api + 'startGame?mode=' + $sourceMode) -WebSession $gameSession -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 25
            $start = Read-ApiJson $startResponse
            if (-not $start.token) { throw 'Game did not provide a session token' }
            $statistics.games++

            for ($round = 1; $round -le 10; $round++) {
                Start-Sleep -Milliseconds ([int]($DelaySeconds * 1000))
                $roundClock = [System.Diagnostics.Stopwatch]::StartNew()
                $statistics.request_stage = 'getRandomRing'
                $knownResponse = Invoke-WebRequest -Uri ($api + 'getRandomRing?mode=' + $sourceMode + '&token=' + [uri]::EscapeDataString($start.token)) -WebSession $gameSession -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 25
                $known = Read-ApiJson $knownResponse
                if (-not $known.rings -or -not $known.map) { throw 'Missing known ring positions' }
                # The fixed map-center guess is not an attempt to optimize a score.
                Start-Sleep -Milliseconds ([int]($DelaySeconds * 1000))
                if ($roundClock.Elapsed.TotalSeconds -ge 11.5) { throw 'Round exceeded its timer; stop without mismatching labels' }
                $guessBody = @{ token=$start.token; round=$round; guessX=8192; guessY=8192;
                    time=$roundClock.Elapsed.TotalSeconds; mode=$sourceMode } | ConvertTo-Json -Compress
                $statistics.request_stage = 'submitGuess'
                $revealResponse = Invoke-WebRequest -Uri ($api + 'submitGuess') -Method Post -WebSession $gameSession -ContentType 'application/json' -Body $guessBody -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 25
                $reveal = Read-ApiJson $revealResponse
                if (-not $reveal.finalRing) { throw 'Missing revealed final ring; no sample saved' }
                $statistics.rounds++
                $statistics.consecutive_recoveries = 0
                if ($known.map -like 'mp_rr_desertlands*') {
                    $pair = @{ known=$known; reveal=$reveal; source_mode=$sourceMode; round=$round;
                        batch_id=$batchId; collected_at=[DateTime]::UtcNow.ToString('o') }
                    [System.IO.File]::AppendAllText($pairsPath, (($pair | ConvertTo-Json -Compress -Depth 12) + "`n"), $encoding)
                    $statistics.worlds_edge_pairs++
                    Sync-Dataset
                } else { $statistics.other_maps++ }
                Save-Progress
                Write-Output ('ROUND game=' + $statistics.games + ' round=' + $round + ' mode=' + $sourceMode + ' map=' + $known.map + ' unique=' + $statistics.unique_total)
                # Finish all ten rounds before endGame, matching the website flow.
                # The current game may add a few samples beyond the target.
            }
            # End guest session normally; no account is signed in and scores are not saved to a user leaderboard.
            Start-Sleep -Milliseconds ([int]($DelaySeconds * 1000))
            $endBody = @{ token=$start.token; mode=$sourceMode } | ConvertTo-Json -Compress
            $statistics.request_stage = 'endGame'
            $endResponse = Invoke-WebRequest -Uri ($api + 'endGame') -Method Post -WebSession $gameSession -ContentType 'application/json' -Body $endBody -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 25
            $null = Read-ApiJson $endResponse
            if ($statistics.unique_total -ge $Target) {
                $statistics.status = 'target_reached'
                break
            }
          } catch {
            $failure = $_.Exception.Message
            if ($_.Exception -is [System.Net.Http.HttpRequestException] -or $_.Exception -is [System.Threading.Tasks.TaskCanceledException] -or $_.Exception -is [System.TimeoutException] -or $_.Exception -is [System.Net.WebException]) {
                # Exception messages may contain a request URL with a session token.
                $failure = 'Network request failed or timed out; restart the guest session'
                if ($_.Exception -is [System.Net.Http.HttpRequestException] -and $null -ne $_.Exception.StatusCode) {
                    $failure = 'HTTP ' + [int]$_.Exception.StatusCode + '; API request failed'
                }
            }
            $recoverable = $failure -match '^(HTTP (408|5\d\d);|API error;|API response did not confirm success|Non-JSON response;|Network request failed|Round exceeded its timer|Missing known ring positions|Missing revealed final ring|Game did not provide a session token)'
            $statistics.last_error = $failure
            if ($recoverable -and $statistics.unique_total -ge $Target) {
                $statistics.status = 'target_reached'
                break
            }
            if ($recoverable -and $statistics.consecutive_recoveries -lt $MaxRecoveries) {
                $statistics.recoveries++
                $statistics.consecutive_recoveries++
                if ($failure -match '^HTTP 5\d\d;') { $statistics.server_recoveries++ }
                $retryDelay = [int][Math]::Min($MaxRecoveryDelaySeconds, $RecoveryDelaySeconds * [Math]::Pow(2, [Math]::Min($statistics.consecutive_recoveries - 1, 8)))
                $statistics.status = 'recovering'
                $statistics.next_retry_at = [DateTime]::UtcNow.AddSeconds($retryDelay).ToString('o')
                $statistics.recovery_events += @{ stage=$statistics.request_stage; reason=$failure; delay_seconds=$retryDelay; at=[DateTime]::UtcNow.ToString('o') }
                Save-Progress
                Write-Output ('RECOVER stage=' + $statistics.request_stage + ' attempt=' + $statistics.consecutive_recoveries + '/' + $MaxRecoveries + '; wait ' + $retryDelay + ' seconds, start a fresh guest game')
                # Never replay a possibly partially executed POST in the same game.
                $start = $null
                $gameSession = $null
                $guessBody = $null
                Start-Sleep -Seconds $retryDelay
                continue
            }
            if ($recoverable) { $failure = 'Consecutive recovery limit reached; last error: ' + $failure }
            throw $failure
          }
        }
        if ($statistics.status -in @('running', 'recovering')) { $statistics.status = 'budget_reached' }
    }
} catch {
    $statistics.status = 'stopped'
    $statistics.stop_reason = $_.Exception.Message
    Write-Output ('STOP ' + $statistics.stop_reason)
} finally {
    $start = $null
    $gameSession = $null
    $guessBody = $null
    $statistics['ended_at'] = [DateTime]::UtcNow.ToString('o')
    $statistics.next_retry_at = $null
    Save-Progress
    $collectionMutex.ReleaseMutex()
    $collectionMutex.Dispose()
}
if ($statistics.status -eq 'stopped') { exit 1 }
