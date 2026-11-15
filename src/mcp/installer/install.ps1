[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+(-dev\.\d+)?$')][string]$Version,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'AstroPhotoFlow'),
    [string]$Workspace,
    [string]$ManifestPath,
    [string]$OperationId,
    [string]$LogPath,
    [switch]$Json
)
# Fixed source installer: downloads the pinned workbench payload and uv runtime,
# prepares the locked Python environment and initializes the workspace.
#
# It never installs Node, npm or the MCP package: the host supplies Node and the
# MCP connection, and this script only writes application state below InstallRoot.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
# A detached host may start this script without console handles, so console
# encoding and console writes are best effort while the log file is mandatory.
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch { }
$Repository = 'MaojieXu/astrophoto-flow'
$PreviousCache = $env:UV_CACHE_DIR
$PreviousPython = $env:UV_PYTHON_INSTALL_DIR
$PreviousEnvironment = $env:UV_PROJECT_ENVIRONMENT
$PreviousPythonUtf8 = $env:PYTHONUTF8
$PreviousTls = [Net.ServicePointManager]::SecurityProtocol
$OperationFile = $null
$Phase = 'preparing'

function Log([string]$Message) {
    $Line = '[' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') + '] ' + $Message
    try { [Console]::Error.WriteLine($Line) } catch { }
    if ($LogPath) { [IO.File]::AppendAllText($LogPath, $Line + "`n") }
}
function Write-JsonFile([string]$Path, $Value, [int]$Depth) {
    $Temporary = $Path + '.tmp'
    [IO.File]::WriteAllText($Temporary, ($Value | ConvertTo-Json -Depth $Depth))
    if (Test-Path -LiteralPath $Path) {
        $Backup = $Path + '.bak'
        [IO.File]::Replace($Temporary, $Path, $Backup)
        Remove-Item -LiteralPath $Backup -Force -ErrorAction SilentlyContinue
    } else {
        [IO.File]::Move($Temporary, $Path)
    }
}
function Write-State([string]$Status, [string]$StatePhase, [string]$Message) {
    if (-not $OperationFile) { return }
    $Now = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $State = [ordered]@{
        schema_version = 1
        operation_id   = $OperationId
        action         = 'init'
        status         = $Status
        phase          = $StatePhase
        version        = $Version
        install_root   = $InstallRoot
        workspace      = $Workspace
        source         = $script:Source
        publication    = $script:Publication
        started_at     = $script:StartedAt
        updated_at     = $Now
        message        = $Message
        log            = $LogPath
    }
    Write-JsonFile $OperationFile $State 5
}
function Set-Phase([string]$StatePhase, [string]$Message) {
    $script:Phase = $StatePhase
    Write-State 'running' $StatePhase $Message
    Log ($StatePhase + ': ' + $Message)
}
function Tool([string]$Executable, [string[]]$Arguments) {
    $Lines = @(& $Executable @Arguments)
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $([IO.Path]::GetFileName($Executable)) (exit $LASTEXITCODE)." }
    return ($Lines -join "`n")
}
function Check-Hash([string]$Path, [string]$Expected) {
    if ($Expected -notmatch '^[a-f0-9]{64}$') { throw "Invalid expected SHA-256 for $([IO.Path]::GetFileName($Path))." }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Expected) {
        throw ("SHA-256 mismatch: " + [IO.Path]::GetFileName($Path) + '.')
    }
}
function Download([string]$Url, [string]$Destination, [string]$Expected) {
    if (Test-Path -LiteralPath $Destination) { Check-Hash $Destination $Expected; return }
    $Partial = $Destination + '.partial'
    if (Test-Path -LiteralPath $Partial) {
        if ((Get-FileHash -LiteralPath $Partial -Algorithm SHA256).Hash.ToLowerInvariant() -eq $Expected) {
            Move-Item -LiteralPath $Partial -Destination $Destination
            return
        }
    }
    $Offset = 0L
    if (Test-Path -LiteralPath $Partial) { $Offset = (Get-Item -LiteralPath $Partial).Length }
    Log ('Downloading ' + $Url + ' from offset ' + $Offset)
    $Request = [Net.HttpWebRequest]::Create($Url)
    $Request.UserAgent = 'AstroPhotoFlow-Installer'
    $Request.Timeout = 60000
    if ($Offset -gt 0) { $Request.AddRange($Offset) }
    try { $Response = $Request.GetResponse() }
    catch [Net.WebException] {
        if ($Offset -gt 0 -and $_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 416) {
            $_.Exception.Response.Dispose()
            Remove-Item -LiteralPath $Partial
            Download $Url $Destination $Expected
            return
        }
        throw
    }
    try {
        $Mode = [IO.FileMode]::Create
        if ($Offset -gt 0 -and [int]$Response.StatusCode -eq 206) { $Mode = [IO.FileMode]::Append }
        $File = [IO.File]::Open($Partial, $Mode, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $Response.GetResponseStream().CopyTo($File) } finally { $File.Dispose() }
    } finally { $Response.Dispose() }
    try { Check-Hash $Partial $Expected } catch { Remove-Item -LiteralPath $Partial; throw }
    Move-Item -LiteralPath $Partial -Destination $Destination
}
function Expand-Safe([string]$Archive, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [void][IO.Directory]::CreateDirectory($Destination)
    $Prefix = [IO.Path]::GetFullPath($Destination).TrimEnd('\') + '\'
    $Zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($Entry in $Zip.Entries) {
            if ($Entry.FullName.Contains(':')) { throw 'Archive contains an invalid path.' }
            $Target = [IO.Path]::GetFullPath((Join-Path $Destination $Entry.FullName))
            if (-not $Target.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive path escapes its installation directory.' }
            if (($Entry.ExternalAttributes -shr 16 -band 61440) -eq 40960) { throw 'Archive symlinks are not supported.' }
            if ($Entry.FullName.EndsWith('/') -or $Entry.FullName.EndsWith('\')) { [void][IO.Directory]::CreateDirectory($Target); continue }
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Target))
            [IO.Compression.ZipFileExtensions]::ExtractToFile($Entry, $Target, $false)
        }
    } finally { $Zip.Dispose() }
}
function Assert-Owned([string]$Path, [string]$Message) {
    $Full = [IO.Path]::GetFullPath($Path)
    if ($Full.TrimEnd('\') -eq [IO.Path]::GetPathRoot($Full).TrimEnd('\')) { throw $Message }
    return $Full
}

try {
    # MCP hosts may pass a minimal environment without OS/PROCESSOR_ARCHITECTURE.
    if ([Environment]::OSVersion.Platform -ne 'Win32NT' -or [Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64' -or [Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -ne 'X64') { throw 'PLATFORM_UNSUPPORTED: Windows x64 is required.' }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    if (-not $OperationId) { $OperationId = 'init-' + [Guid]::NewGuid().ToString('N') }
    if ($OperationId -notmatch '^[a-z0-9][a-z0-9-]{0,63}$') { throw 'Invalid operation id.' }
    $InstallRoot = Assert-Owned $InstallRoot 'Install root must not be a drive root.'
    if (-not $Workspace) { $Workspace = Join-Path $InstallRoot 'workspace' }
    $Workspace = Assert-Owned $Workspace 'Workspace must not be a drive root.'
    foreach ($Owned in @('versions', 'runtimes', 'cache')) {
        $OwnedPrefix = [IO.Path]::GetFullPath((Join-Path $InstallRoot $Owned)).TrimEnd('\') + '\'
        if (($Workspace.TrimEnd('\') + '\').StartsWith($OwnedPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Workspace must be outside version, runtime and cache directories.' }
    }
    if ($InstallRoot.TrimEnd('\') -eq $Workspace.TrimEnd('\')) { throw 'Workspace must differ from the install root.' }
    if (-not $LogPath) { $LogPath = Join-Path ([IO.Path]::GetTempPath()) ('astrophotoflow-install-' + $OperationId + '.log') }

    [void][IO.Directory]::CreateDirectory($InstallRoot)
    $script:StartedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $script:Source = $(if ($ManifestPath) { 'candidate' } else { 'release' })
    $script:Publication = $(if ($ManifestPath) { 'candidate' } else { 'published' })

    $Ownership = Join-Path $InstallRoot '.astrophoto-flow-installation'
    if (Test-Path -LiteralPath $Ownership) {
        if ((Get-Content -LiteralPath $Ownership -Raw).Trim() -ne $Repository) { throw 'Install root belongs to a different application.' }
    } else {
        if (@(Get-ChildItem -LiteralPath $InstallRoot -Force).Count -gt 0) { throw 'INSTALL_ROOT_NOT_EMPTY: install root is not empty and is not owned by this installer.' }
        [IO.File]::WriteAllText($Ownership, $Repository)
    }
    $OperationFile = Join-Path $InstallRoot 'install-operation.json'

    Set-Phase 'preparing' 'Validating paths and release identity.'
    $Cache = Join-Path $InstallRoot 'cache'
    [void][IO.Directory]::CreateDirectory($Cache)
    $ReleaseUrl = 'https://github.com/' + $Repository + '/releases/download/v' + $Version
    $CandidateDirectory = $null
    if ($ManifestPath) {
        $ManifestPath = [IO.Path]::GetFullPath($ManifestPath)
        if (-not (Test-Path -LiteralPath $ManifestPath)) { throw 'MANIFEST_MISSING: the candidate manifest does not exist.' }
        $CandidateDirectory = [IO.Path]::GetDirectoryName($ManifestPath)
    } else {
        $ManifestPath = Join-Path $Cache ('manifest-' + $Version + '.json')
        Invoke-WebRequest -UseBasicParsing -Uri ($ReleaseUrl + '/release-manifest.json') -OutFile $ManifestPath
    }
    $Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Manifest.schema_version -ne 2 -or $Manifest.version -ne $Version -or $Manifest.repository -ne $Repository) { throw 'Invalid release manifest identity.' }
    if ($Manifest.commit -notmatch '^[a-f0-9]{40}$') { throw 'Invalid release commit identity.' }
    if (@('published', 'candidate') -notcontains $Manifest.publication) { throw 'Invalid release publication state.' }
    if ($script:Publication -eq 'candidate' -and $Manifest.publication -ne 'candidate') { throw 'A local manifest must be marked as a candidate.' }
    if ($script:Publication -eq 'published' -and $Manifest.publication -ne 'published') { throw 'A published release must be served from the public release source.' }
    $script:Publication = $Manifest.publication
    if ($Manifest.runtime.uv.version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid uv version.' }
    if ($Manifest.runtime.python -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid Python version.' }
    $ExpectedUv = 'https://github.com/astral-sh/uv/releases/download/' + $Manifest.runtime.uv.version + '/uv-x86_64-pc-windows-msvc.zip'
    $UvSource = $Manifest.runtime.uv.url
    if (-not $CandidateDirectory) {
        if ($UvSource -ne $ExpectedUv) { throw 'Runtime download source does not match the official versioned URL.' }
    } elseif ($UvSource -ne $ExpectedUv -and $UvSource -notmatch '^[A-Za-z0-9._-]+$') { throw 'Invalid uv artifact name.' }
    $PayloadName = [string]$Manifest.workbench.file
    if (-not $PayloadName -or [IO.Path]::GetFileName($PayloadName) -ne $PayloadName) { throw 'Invalid release asset name.' }
    if (-not $CandidateDirectory) { $Payload = Join-Path $Cache $PayloadName }
    else {
        $Payload = Join-Path $CandidateDirectory $PayloadName
        if (-not (Test-Path -LiteralPath $Payload)) {
            $Payload = Join-Path $Cache $PayloadName
            Download ($ReleaseUrl + '/' + $PayloadName) $Payload $Manifest.workbench.sha256
        }
    }

    Set-Phase 'downloading' 'Acquiring the workbench payload.'
    $PayloadSha = [string]$Manifest.workbench.sha256
    if ($CandidateDirectory) { Check-Hash $Payload $PayloadSha }
    else { Download ($ReleaseUrl + '/' + $PayloadName) $Payload $PayloadSha }

    Set-Phase 'verifying' 'Verifying payload checksums.'
    Check-Hash $Payload $PayloadSha

    Set-Phase 'extracting' 'Extracting the pinned workbench version.'
    $VersionDirectory = Join-Path $InstallRoot ('versions/' + $Version)
    $Marker = Join-Path $VersionDirectory '.payload-sha256'
    if (Test-Path -LiteralPath $VersionDirectory) {
        if (-not (Test-Path -LiteralPath $Marker) -or (Get-Content -LiteralPath $Marker -Raw).Trim() -ne $PayloadSha) {
            throw 'VERSION_DIRECTORY_CONFLICT: this version directory holds a different or incomplete payload.'
        }
    } else {
        $Stage = $VersionDirectory + '.extracting'
        if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
        Expand-Safe $Payload $Stage
        [IO.File]::WriteAllText((Join-Path $Stage '.payload-sha256'), $PayloadSha)
        Move-Item -LiteralPath $Stage -Destination $VersionDirectory
    }
    $Backend = Join-Path $VersionDirectory 'workbench/backend'
    if (-not (Test-Path -LiteralPath (Join-Path $Backend 'astrophotoflow/cli.py'))) {
        throw 'CONTROLLER_UNAVAILABLE: the payload has no workbench controller.'
    }
    $ProductIdentityPath = Join-Path $Backend 'release-version.json'
    if (-not (Test-Path -LiteralPath $ProductIdentityPath)) { throw 'Payload has no release identity.' }
    $ProductIdentity = Get-Content -LiteralPath $ProductIdentityPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($ProductIdentity.version -ne $Version -or $ProductIdentity.commit -ne $Manifest.commit) {
        throw 'Payload identity does not match the release manifest.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $Backend 'web/index.html'))) { throw 'Payload has no packaged frontend.' }

    Set-Phase 'runtime' 'Preparing the pinned uv and Python runtime.'
    $UvRoot = Join-Path $InstallRoot ('runtimes/uv/' + $Manifest.runtime.uv.version)
    $Uv = Join-Path $UvRoot 'uv.exe'
    if (-not (Test-Path -LiteralPath $Uv)) {
        $UvArchive = Join-Path $Cache ('uv-' + $Manifest.runtime.uv.version + '-windows-x64.zip')
        if ($CandidateDirectory -and $UvSource -ne $ExpectedUv) {
            $LocalUv = Join-Path $CandidateDirectory $UvSource
            if (-not (Test-Path -LiteralPath $LocalUv)) { throw 'MANIFEST_MISSING: the candidate uv archive does not exist.' }
            Check-Hash $LocalUv $Manifest.runtime.uv.sha256
            Copy-Item -LiteralPath $LocalUv -Destination $UvArchive -Force
        } else {
            Download $ExpectedUv $UvArchive $Manifest.runtime.uv.sha256
        }
        $UvStage = $UvRoot + '.extracting'
        if (Test-Path -LiteralPath $UvStage) { Remove-Item -LiteralPath $UvStage -Recurse -Force }
        Expand-Safe $UvArchive $UvStage
        [void][IO.Directory]::CreateDirectory($UvRoot)
        $UvFiles = @(Get-ChildItem -LiteralPath $UvStage -Filter uv.exe -Recurse)
        if ($UvFiles.Count -ne 1) { throw 'uv archive must contain exactly one uv.exe.' }
        Copy-Item -LiteralPath $UvFiles[0].FullName -Destination ($Uv + '.tmp') -Force
        [IO.File]::Move(($Uv + '.tmp'), $Uv)
        Remove-Item -LiteralPath $UvStage -Recurse -Force
    }
    $env:UV_CACHE_DIR = Join-Path $Cache 'uv'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $InstallRoot 'runtimes/python'
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $Backend '.venv'
    $env:PYTHONUTF8 = '1'
    [void](Tool $Uv @('python', 'install', $Manifest.runtime.python, '--no-bin', '--no-registry'))

    Set-Phase 'dependencies' 'Installing the locked Python environment.'
    [void](Tool $Uv @('sync', '--project', $Backend, '--locked', '--python', $Manifest.runtime.python))
    [void](Tool $Uv @('run', '--project', $Backend, '--directory', $Backend, '--locked', '--no-sync', 'python', '-c', 'import fastapi, uvicorn, httpx, sqlalchemy, alembic, psutil, aiohttp, pydantic'))

    Set-Phase 'workspace' 'Initializing or adopting the workspace.'
    [void](Tool $Uv @('run', '--project', $Backend, '--directory', $Backend, '--locked', '--no-sync', 'python', '-m', 'astrophotoflow.cli', 'init', '--workspace', $Workspace, '--json'))
    if (-not (Test-Path -LiteralPath (Join-Path $Workspace 'config.toml'))) { throw 'Controller init did not create a workspace configuration.' }

    Set-Phase 'installed' 'Recording the installation receipt.'
    $Receipt = [ordered]@{
        schema_version   = 1
        version          = $Version
        commit           = $Manifest.commit
        install_root     = $InstallRoot
        workspace        = $Workspace
        source           = $script:Source
        publication      = $script:Publication
        installed_at     = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        workbench_sha256 = $PayloadSha
        runtime          = [ordered]@{ uv = $Manifest.runtime.uv.version; python = $Manifest.runtime.python }
    }
    Write-JsonFile (Join-Path $InstallRoot 'installation.json') $Receipt 5
    Write-State 'succeeded' 'installed' 'Installation completed.'
    $Outcome = [ordered]@{ status = 'installed'; version = $Version; install_root = $InstallRoot; workspace = $Workspace; source = $script:Source; publication = $script:Publication }
    if ($Json) { $Outcome | ConvertTo-Json -Depth 4 -Compress }
    else { 'AstroPhotoFlow ' + $Version + ' installed in ' + $InstallRoot + ' (' + $script:Publication + ').' }
} catch {
    $Message = $_.Exception.Message
    try { [Console]::Error.WriteLine($Message) } catch { }
    if ($LogPath) { try { [IO.File]::AppendAllText($LogPath, $Message + "`n") } catch { } }
    try { Write-State 'failed' 'failed' $Message } catch { try { [Console]::Error.WriteLine('Cannot record the failed install operation.') } catch { } }
    exit 1
} finally {
    $env:UV_CACHE_DIR = $PreviousCache
    $env:UV_PYTHON_INSTALL_DIR = $PreviousPython
    $env:UV_PROJECT_ENVIRONMENT = $PreviousEnvironment
    $env:PYTHONUTF8 = $PreviousPythonUtf8
    [Net.ServicePointManager]::SecurityProtocol = $PreviousTls
}
