[CmdletBinding()]
param([string]$Tag, [string]$Output, [switch]$Candidate)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (-not $Output) { $Output = Join-Path $Root '.artifacts/dist' }
if ($Candidate) {
    # A candidate packages the working tree; it is never a publishable release.
    if ($Tag) { throw 'A candidate build takes no tag.' }
} elseif (-not $Tag) {
    $Tag = 'v' + ((Get-Content (Join-Path $Root 'package.json') -Raw | ConvertFrom-Json).version)
}
Push-Location $Root
try {
    if ($Candidate) {
        & python scripts/release/package.py --preflight --candidate
    } else {
        & python scripts/release/package.py --preflight --tag $Tag
    }
    if ($LASTEXITCODE -ne 0) { throw 'Source preflight failed.' }
    & pnpm install --frozen-lockfile --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw 'Root dependency installation failed.' }
    & pnpm --dir src/workbench/frontend install --frozen-lockfile --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    $PreviousSourcemap = $env:GENERATE_SOURCEMAP
    try {
        $env:GENERATE_SOURCEMAP = 'false'
        & pnpm --dir src/workbench/frontend build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { $env:GENERATE_SOURCEMAP = $PreviousSourcemap }
    & node scripts/build-mcp.ts
    if ($LASTEXITCODE -ne 0) { throw 'MCP build failed.' }
    if ($Candidate) {
        & python scripts/release/package.py --candidate --output $Output
    } else {
        & python scripts/release/package.py --tag $Tag --output $Output
    }
    if ($LASTEXITCODE -ne 0) { throw 'Release assembly failed.' }
} finally { Pop-Location }
