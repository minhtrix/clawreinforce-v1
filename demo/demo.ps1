[CmdletBinding()]
param(
    [switch]$SkipLiveGuard,
    [switch]$SkipOpenAIProbe,
    [switch]$SkipServe,
    [int]$Port = 8788
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputRoot = Join-Path $repoRoot "demo-output"
$localPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$clawExecutable = $null
$clawPrefix = @()

if (Test-Path -LiteralPath $localPython) {
    $clawExecutable = $localPython
    $clawPrefix = @("-m", "clawreinforce")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -c "import clawreinforce" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $clawExecutable = (Get-Command python).Source
        $clawPrefix = @("-m", "clawreinforce")
    }
}
if (-not $clawExecutable -and (Get-Command clawreinforce -ErrorAction SilentlyContinue)) {
    $clawExecutable = (Get-Command clawreinforce).Source
}

function Invoke-ClawJson {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [int[]]$AllowedExitCodes = @(0)
    )
    Write-Host "`n> clawreinforce $($Arguments -join ' ')" -ForegroundColor Cyan
    $lines = & $clawExecutable @clawPrefix @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = $lines -join "`n"
    Write-Host $text
    if ($exitCode -notin $AllowedExitCodes) {
        throw "clawreinforce exited with $exitCode"
    }
    return $text | ConvertFrom-Json
}

Push-Location $repoRoot
try {
    if (-not $clawExecutable) {
        throw 'clawreinforce is not installed. Run: python -m pip install -e . (or install it in .venv).'
    }
    New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

    Write-Host "`n[1/4] Guard a real ClawHub skill" -ForegroundColor Magenta
    if ($SkipLiveGuard) {
        Write-Host "SKIPPED (--SkipLiveGuard). Expected: review; reason: skill has no golden cases."
    } else {
        $guard = Invoke-ClawJson -AllowedExitCodes @(0, 2) -Arguments @(
            "guard", "https://clawhub.ai/jaaneek/skills/x-search",
            "--tier", "openai:gpt-5.6-sol"
        )
        if ($guard.verdict -ne "review" -or $guard.reasons -notcontains "skill has no golden cases") {
            throw "Live guard no longer matches the storyboard."
        }
    }
    Write-Host "Guard cost: `$0.00 - no golden cases means no model request." -ForegroundColor Yellow
    if (-not $SkipOpenAIProbe -and $env:OPENAI_API_KEY) {
        Write-Host "Optional paid connectivity proof; typically under `$0.01 at current GPT-5.6 Sol rates."
        $null = Invoke-ClawJson -Arguments @("models", "--project", ".", "--probe", "openai:gpt-5.6-sol")
    } elseif (-not $SkipOpenAIProbe) {
        Write-Host "OPENAI_API_KEY is absent; skipping the optional paid probe."
    }

    Write-Host "`n[2/4] Certify and render signed evidence (zero keys)" -ForegroundColor Magenta
    $certify = Invoke-ClawJson -Arguments @(
        "certify", "examples/uppercase-skill", "--tier", "fixture:upper-if-skilled"
    )
    if ($certify.report.tiers[0].pass_rate -ne 1.0) { throw "Fixture certification did not pass." }
    $certificate = Join-Path $outputRoot "uppercase-certificate.json"
    Copy-Item -LiteralPath $certify.certificate_path -Destination $certificate -Force
    $badge = Join-Path $outputRoot "uppercase-badge.svg"
    $null = Invoke-ClawJson -Arguments @("badge", $certificate, "--output", $badge)

    Write-Host "`n[3/4] Measure uplift and export evidence (zero keys)" -ForegroundColor Magenta
    $csv = Join-Path $outputRoot "arena.csv"
    $png = Join-Path $outputRoot "arena.png"
    $bench = Invoke-ClawJson -Arguments @(
        "bench", "examples/uppercase-task", "examples/uppercase-skill",
        "--tier", "fixture:upper-if-skilled", "--trials", "2",
        "--csv", $csv, "--png", $png
    )
    if ($bench.report.summary.uplift -ne 1.0) { throw "Fixture uplift was not +1.0." }
    foreach ($path in @($certificate, $badge, $csv, $png)) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Missing demo artifact: $path" }
    }
    Write-Host "Artifacts ready in $outputRoot" -ForegroundColor Green

    Write-Host "`n[4/4] Open the four-tab GUI" -ForegroundColor Magenta
    Write-Host "Open http://127.0.0.1:$Port and follow docs/DEMO.md."
    if ($SkipServe) {
        Write-Host "SKIPPED (--SkipServe)."
    } else {
        & $clawExecutable @clawPrefix serve --project . --host 127.0.0.1 --port $Port
        if ($LASTEXITCODE -ne 0) { throw "Server exited with $LASTEXITCODE" }
    }
} finally {
    Pop-Location
}
