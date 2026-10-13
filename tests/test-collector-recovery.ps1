$ErrorActionPreference = 'Stop'
$sourcePath = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\collect-ringguessr.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('ringlab-recovery-tests-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path (Join-Path $tempRoot 'scripts'),(Join-Path $tempRoot '.venv\Scripts'),(Join-Path $tempRoot 'data') -Force
$testCollector = Join-Path $tempRoot 'scripts\collect-ringguessr.ps1'
Copy-Item -LiteralPath $sourcePath -Destination $testCollector
$null = New-Item -ItemType File -Path (Join-Path $tempRoot '.venv\Scripts\python.exe')
Set-Content -LiteralPath (Join-Path $tempRoot 'data\rings.json') -Value '[]' -Encoding utf8

# All network and waits are replaced; no requests or executable fixtures are run.
function Invoke-WebRequest {
    param($Uri,$SessionVariable,$WebSession,$Method,$ContentType,$Body,[switch]$UseBasicParsing,[switch]$SkipHttpErrorCheck,$TimeoutSec)
    if ($Uri -match '/ring-guessr$') { return [pscustomobject]@{StatusCode=200;Content='ringGuesser_play'} }
    if ($Uri -match '/startGame\?mode=PUBLIC$') {
        $global:ringlabTestStartCalls++
        switch ($global:ringlabTestCase) {
            'api_error' { return [pscustomobject]@{StatusCode=200;Content='{"success":false,"error":"Session expired"}'} }
            'captcha' { return [pscustomobject]@{StatusCode=200;Content='{"success":false,"code":"CAPTCHA_REQUIRED"}'} }
            'rate_limit' { return [pscustomobject]@{StatusCode=200;Content='{"success":false,"code":"RATE_LIMITED"}'} }
            'non_json' { return [pscustomobject]@{StatusCode=200;Content='upstream service unavailable'} }
            'challenge_html' { return [pscustomobject]@{StatusCode=200;Content='<html>Cloudflare verification</html>'} }
            'network' { throw [System.Net.Http.HttpRequestException]::new('Request failed for token=fixture-secret') }
            'http_exception_403' { throw [System.Net.Http.HttpRequestException]::new('Forbidden', $null, [System.Net.HttpStatusCode]::Forbidden) }
            'reset_counter' {
                if ($global:ringlabTestStartCalls -eq 1) { return [pscustomobject]@{StatusCode=500;Content='{}'} }
            }
            'submit_failure' { }
            default { return [pscustomobject]@{StatusCode=$global:ringlabTestStatusCode;Content='{}'} }
        }
        return [pscustomobject]@{StatusCode=200;Content=('{"success":true,"token":"fixture-' + $global:ringlabTestStartCalls + '"}')}
    }
    if ($Uri -match '/getRandomRing\?') {
        return [pscustomobject]@{StatusCode=200;Content='{"success":true,"map":"mp_rr_district_mu1","rings":[{"x":8192,"y":8192,"r":4000}]}'}
    }
    if ($Uri -match '/submitGuess$') {
        $guess = $Body | ConvertFrom-Json
        $global:ringlabTestSubmittedTokens += $guess.token
        if ($global:ringlabTestCase -eq 'submit_failure' -and $global:ringlabTestStartCalls -eq 1) {
            return [pscustomobject]@{StatusCode=500;Content='{}'}
        }
        return [pscustomobject]@{StatusCode=200;Content='{"success":true,"finalRing":{"x":8192,"y":8192,"r":100}}'}
    }
    if ($Uri -match '/endGame$') {
        if ($global:ringlabTestCase -eq 'reset_counter' -and $global:ringlabTestStartCalls -eq 2) {
            return [pscustomobject]@{StatusCode=500;Content='{}'}
        }
        return [pscustomobject]@{StatusCode=200;Content='{"success":true}'}
    }
    throw ('Unexpected request in recovery test: ' + $Uri)
}
function Start-Sleep {
    param($Milliseconds,$Seconds)
    if ($Seconds) { $global:ringlabTestRecoveryWaits += $Seconds }
}

try {
    foreach ($code in @(500,408,429,403,401)) {
        $global:ringlabTestCase = 'http'
        $global:ringlabTestStatusCode = $code
        $global:ringlabTestStartCalls = 0
        $global:ringlabTestRecoveryWaits = @()
        $null = & $testCollector -Mode PUBLIC -Target 1 -MaxGames 6 -MaxServerRecoveries 2
        $progress = Get-Content -LiteralPath (Join-Path $tempRoot 'data\collection-progress.json') -Raw -Encoding utf8 | ConvertFrom-Json
        $expectedRecoveries = if ($code -in @(500,408)) { 2 } else { 0 }
        if ($progress.status -ne 'stopped' -or $progress.recoveries -ne $expectedRecoveries -or $global:ringlabTestStartCalls -ne ($expectedRecoveries+1)) {
            throw ('Recovery policy failed for HTTP ' + $code)
        }
        if ($progress.request_stage -ne 'startGame') { throw 'Request stage was not recorded' }
        if ($expectedRecoveries -and ($global:ringlabTestRecoveryWaits -join ',') -ne '30,60') { throw 'Retry backoff did not increase' }
        Write-Output ('PASS HTTP=' + $code + ' recoveries=' + $progress.recoveries + ' calls=' + $global:ringlabTestStartCalls)
    }
    $global:ringlabTestCase = 'http'
    $global:ringlabTestStatusCode = 500
    $global:ringlabTestStartCalls = 0
    $global:ringlabTestRecoveryWaits = @()
    $null = & $testCollector -Mode PUBLIC -Target 1 -MaxGames 8
    $progress = Get-Content -LiteralPath (Join-Path $tempRoot 'data\collection-progress.json') -Raw -Encoding utf8 | ConvertFrom-Json
    if ($progress.status -ne 'stopped' -or $progress.recoveries -ne 5 -or $global:ringlabTestStartCalls -ne 6 -or ($global:ringlabTestRecoveryWaits -join ',') -ne '30,60,120,240,300') { throw 'Default retry limit or capped backoff failed' }
    Write-Output 'PASS default retries=5; waits=30,60,120,240,300'
    $global:ringlabTestStartCalls = 0
    $global:ringlabTestRecoveryWaits = @()
    $null = & $testCollector -Mode PUBLIC -Target 1 -MaxGames 8 -MaxRecoveries 0
    $progress = Get-Content -LiteralPath (Join-Path $tempRoot 'data\collection-progress.json') -Raw -Encoding utf8 | ConvertFrom-Json
    if ($progress.recoveries -ne 0 -or $global:ringlabTestStartCalls -ne 1) { throw 'Recovery could not be disabled' }
    Write-Output 'PASS retries disabled'
    foreach ($scenario in @('api_error','captcha','rate_limit','non_json','challenge_html','network','http_exception_403')) {
        $global:ringlabTestCase = $scenario
        $global:ringlabTestStartCalls = 0
        $global:ringlabTestRecoveryWaits = @()
        $null = & $testCollector -Mode PUBLIC -Target 1 -MaxGames 6 -MaxRecoveries 2
        $progressText = Get-Content -LiteralPath (Join-Path $tempRoot 'data\collection-progress.json') -Raw -Encoding utf8
        $progress = $progressText | ConvertFrom-Json
        $expectedRecoveries = if ($scenario -in @('api_error','non_json','network')) { 2 } else { 0 }
        if ($progress.status -ne 'stopped' -or $progress.recoveries -ne $expectedRecoveries -or $global:ringlabTestStartCalls -ne ($expectedRecoveries+1)) { throw ('Wrong recovery classification: ' + $scenario) }
        if ($progressText -match 'fixture-secret') { throw 'Network exception leaked a session credential' }
        Write-Output ('PASS scenario=' + $scenario + ' recoveries=' + $progress.recoveries)
    }
    foreach ($scenario in @('submit_failure','reset_counter')) {
        $global:ringlabTestCase = $scenario
        $global:ringlabTestStartCalls = 0
        $global:ringlabTestSubmittedTokens = @()
        $global:ringlabTestRecoveryWaits = @()
        $null = & $testCollector -Mode PUBLIC -Target 1 -MaxGames 3 -MaxRecoveries 1
        $progress = Get-Content -LiteralPath (Join-Path $tempRoot 'data\collection-progress.json') -Raw -Encoding utf8 | ConvertFrom-Json
        $expectedRecoveries = if ($scenario -eq 'reset_counter') { 2 } else { 1 }
        if ($progress.status -ne 'budget_reached' -or $progress.recoveries -ne $expectedRecoveries -or $progress.consecutive_recoveries -ne 0) { throw ('Fresh-session recovery failed: ' + $scenario) }
        if ($scenario -eq 'submit_failure' -and @($global:ringlabTestSubmittedTokens | Where-Object { $_ -eq 'fixture-1' }).Count -ne 1) { throw 'A failed POST was replayed in its old session' }
        Write-Output ('PASS scenario=' + $scenario + ' fresh sessions; recovery counter reset')
    }
} finally {
    $cleanupPath = [System.IO.Path]::GetFullPath($tempRoot)
    $allowedTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $cleanupPath.StartsWith($allowedTemp,[System.StringComparison]::OrdinalIgnoreCase) -or (Split-Path -Leaf $cleanupPath) -notmatch '^ringlab-recovery-tests-[a-f0-9]{32}$') { throw 'Unsafe test cleanup path' }
    Remove-Item -LiteralPath $cleanupPath -Recurse -Force
}
