param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw '未找到虚拟环境，请按 README 安装依赖。' }
Push-Location -LiteralPath $projectRoot
try { & $pythonPath -m ringlab.server --port $Port }
finally { Pop-Location }
