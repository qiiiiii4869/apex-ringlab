$ErrorActionPreference = 'Stop'
$collectorPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\collect-ringguessr.ps1'
$collectorCode = Get-Content -LiteralPath $collectorPath -Raw -Encoding utf8
$assignment = ($collectorCode -split "`n" | Where-Object { $_ -match '^\[string\[\]\]\$modes\s*=' })
if (-not $assignment) { throw 'Missing typed mode selection' }
$selection = [scriptblock]::Create($assignment)
foreach ($testMode in @('PUBLIC', 'ALGS', 'BOTH')) {
    $Mode = $testMode
    . $selection
    [string[]]$expected = if ($testMode -eq 'BOTH') { @('PUBLIC', 'ALGS') } else { @($testMode) }
    if ($modes -isnot [string[]] -or $modes.Count -ne $expected.Count) { throw ('Wrong mode array: ' + $testMode) }
    for ($game = 0; $game -lt 4; $game++) {
        $actual = $modes[$game % $modes.Count]
        if ($actual -ne $expected[$game % $expected.Count]) { throw ('Wrong selected mode: ' + $testMode) }
    }
    Write-Output ('PASS mode=' + $testMode + ' selection=' + ($modes -join ','))
}
