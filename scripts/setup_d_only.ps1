# Run from anywhere in Windows PowerShell. Keeps every cache/temp/venv inside D:\AgentX\wasl\.cache.
$ErrorActionPreference = "Stop"
$root  = "D:\AgentX\wasl"
$cache = "$root\.cache"
foreach ($d in "hf\hub", "torch", "pip", "tmp", "claude_tmp") { New-Item -ItemType Directory -Force "$cache\$d" | Out-Null }

$env:HF_HOME = "$cache\hf"; $env:HUGGINGFACE_HUB_CACHE = "$cache\hf\hub"; $env:SENTENCE_TRANSFORMERS_HOME = "$cache\hf"
$env:TORCH_HOME = "$cache\torch"; $env:PIP_CACHE_DIR = "$cache\pip"
$env:TMP = "$cache\tmp"; $env:TEMP = "$cache\tmp"; $env:TMPDIR = "$cache\tmp"

$venv = "$cache\venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    py -3.12 -m venv $venv
    & "$venv\Scripts\python.exe" -m pip install -q --upgrade pip
    & "$venv\Scripts\python.exe" -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu
    & "$venv\Scripts\python.exe" -m pip install -q -r "$root\requirements.txt"
}
if (Test-Path "$root\.venv") { Remove-Item -Recurse -Force "$root\.venv" }  # old venv (was on D:, superseded)
Write-Host "venv ready: $venv"
