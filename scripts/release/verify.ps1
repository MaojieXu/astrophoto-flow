[CmdletBinding()]
param([string]$ReleaseDirectory, [string]$Report, [switch]$KeepTemporary)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (-not $ReleaseDirectory) { $ReleaseDirectory = Join-Path $Root '.artifacts/dist' }
$ReleaseDirectory = [IO.Path]::GetFullPath($ReleaseDirectory)
if (-not $Report) { $Report = Join-Path $ReleaseDirectory 'verification.json' }
$Report = [IO.Path]::GetFullPath($Report)
$Temporary = Join-Path ([IO.Path]::GetTempPath()) ('apf acceptance ' + [Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($Temporary)
$WindowsPowerShell = Join-Path $PSHOME 'powershell.exe'
$Result = [ordered]@{
    schema_version = 2
    status = 'failed'
    platform = 'windows-x64'
    version = $null
    commit = $null
    publication = $null
    artifacts = @{}
    checks = @()
    logs = @{}
    error = $null
}
$Stopped = $true

# Quote one argument for the Win32 command line; argument arrays are the only
# way this script passes values, never a shell string.
function Quote-Argument([string]$Value) {
    if ($Value -eq '') { return '""' }
    if ($Value -notmatch '[\s"]') { return $Value }
    $Builder = New-Object Text.StringBuilder
    [void]$Builder.Append('"')
    $Backslashes = 0
    foreach ($Character in $Value.ToCharArray()) {
        if ($Character -eq [char]92) { $Backslashes++; continue }
        if ($Character -eq [char]34) {
            [void]$Builder.Append([string][char]92 * ($Backslashes * 2 + 1))
            [void]$Builder.Append('"')
            $Backslashes = 0
            continue
        }
        if ($Backslashes -gt 0) { [void]$Builder.Append([string][char]92 * $Backslashes); $Backslashes = 0 }
        [void]$Builder.Append($Character)
    }
    if ($Backslashes -gt 0) { [void]$Builder.Append([string][char]92 * ($Backslashes * 2)) }
    [void]$Builder.Append('"')
    return $Builder.ToString()
}

# Run one program and keep its exit code and both streams; never throw on a
# non-zero exit so negative scenarios can assert the refusal.
function Invoke-Program([string]$Executable, [string[]]$Arguments, [int]$Timeout = 1800000) {
    $Start = New-Object Diagnostics.ProcessStartInfo
    $Start.FileName = $Executable
    $Start.Arguments = ($Arguments | ForEach-Object { Quote-Argument $_ }) -join ' '
    $Start.UseShellExecute = $false
    $Start.RedirectStandardOutput = $true
    $Start.RedirectStandardError = $true
    $Start.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
    $Start.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    $Process = [Diagnostics.Process]::Start($Start)
    $Stdout = $Process.StandardOutput.ReadToEndAsync()
    $Stderr = $Process.StandardError.ReadToEndAsync()
    if (-not $Process.WaitForExit($Timeout)) {
        $Process.Kill()
        throw 'An acceptance subprocess timed out; the temporary directory was kept for inspection.'
    }
    return [ordered]@{
        ExitCode = $Process.ExitCode
        Stdout = $Stdout.GetAwaiter().GetResult()
        Stderr = $Stderr.GetAwaiter().GetResult()
    }
}

function Invoke-Json([string]$Executable, [string[]]$Arguments, [int]$Timeout = 1800000) {
    $Run = Invoke-Program $Executable $Arguments $Timeout
    if ($Run.ExitCode -ne 0) { throw ('Subprocess failed: ' + $Run.Stderr + $Run.Stdout) }
    return ($Run.Stdout | ConvertFrom-Json)
}

function Assert-Refusal([string]$Name, $Run, [string]$Expected) {
    if ($Run.ExitCode -eq 0) { throw ($Name + ': the command should have been refused.') }
    $Text = $Run.Stderr + $Run.Stdout
    if (-not $Text.Contains($Expected)) { throw ($Name + ': refused without the expected diagnostic ' + $Expected + '; saw ' + $Text) }
}

function Get-ControllerCommand($Receipt) {
    $Uv = Join-Path $Receipt.install_root ('runtimes/uv/' + $Receipt.runtime.uv + '/uv.exe')
    $Backend = Join-Path $Receipt.install_root ('versions/' + $Receipt.version + '/workbench/backend')
    return [ordered]@{
        Executable = $Uv
        Backend = $Backend
        Prefix = @('run', '--locked', '--no-sync', '--project', $Backend, '--directory', $Backend, 'python', '-m', 'astrophotoflow.cli')
    }
}

function Invoke-Controller($Receipt, [string[]]$Arguments) {
    $Command = Get-ControllerCommand $Receipt
    $PreviousEnvironment = $env:UV_PROJECT_ENVIRONMENT
    $PreviousPython = $env:UV_PYTHON_INSTALL_DIR
    $PreviousCache = $env:UV_CACHE_DIR
    try {
        $env:UV_PROJECT_ENVIRONMENT = Join-Path $Command.Backend '.venv'
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $Receipt.install_root 'runtimes/python'
        $env:UV_CACHE_DIR = Join-Path $Receipt.install_root 'cache/uv'
        $env:PYTHONUTF8 = '1'
        return (Invoke-Program $Command.Executable ($Command.Prefix + $Arguments) 900000)
    } finally {
        $env:UV_PROJECT_ENVIRONMENT = $PreviousEnvironment
        $env:UV_PYTHON_INSTALL_DIR = $PreviousPython
        $env:UV_CACHE_DIR = $PreviousCache
    }
}

try {
    if ($env:OS -ne 'Windows_NT' -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Acceptance requires Windows x64.' }
    $ManifestPath = Join-Path $ReleaseDirectory 'release-manifest.json'
    $Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $Result.version = $Manifest.version
    $Result.commit = $Manifest.commit
    $Result.publication = $Manifest.publication
    if ($Manifest.schema_version -ne 2) { throw 'The acceptance entry expects a schema 2 release manifest.' }
    if (@('published', 'candidate') -notcontains $Manifest.publication) { throw 'The manifest has an unknown publication state.' }
    $CandidateFile = Join-Path $ReleaseDirectory 'candidate.json'
    if ($Manifest.publication -eq 'candidate') {
        if (-not (Test-Path -LiteralPath $CandidateFile)) { throw 'A candidate manifest must ship a candidate.json record.' }
        $Candidate = Get-Content -LiteralPath $CandidateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($Candidate.publishable -ne $false -or $Candidate.publication -ne 'candidate') { throw 'candidate.json does not forbid publication.' }
        $Result.logs['candidate'] = $Candidate
    }

    foreach ($Line in (Get-Content -LiteralPath (Join-Path $ReleaseDirectory 'SHA256SUMS'))) {
        if ($Line -notmatch '^([a-f0-9]{64})  ([^/\\]+)$') { throw 'Invalid SHA256SUMS record.' }
        $Hash = $Matches[1]; $Name = $Matches[2]
        if ((Get-FileHash -LiteralPath (Join-Path $ReleaseDirectory $Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Hash) { throw ('Asset checksum mismatch: ' + $Name) }
        $Result.artifacts[$Name] = $Hash
    }
    $Result.checks += 'asset-checksums'

    # The installer and the MCP ship in the same tarball; extract and install it
    # exactly the way a user would, then drive the MCP over stdio.
    $Tarball = Join-Path $ReleaseDirectory ([string]$Manifest.mcp.file)
    $Expanded = Join-Path $Temporary 'mcp package'
    [void][IO.Directory]::CreateDirectory($Expanded)
    $Extract = Invoke-Program (Join-Path $env:SystemRoot 'System32/tar.exe') @('-xf', $Tarball, '-C', $Expanded)
    if ($Extract.ExitCode -ne 0) { throw ('Cannot expand the MCP tarball: ' + $Extract.Stderr) }
    $InstallerPath = Join-Path $Expanded 'package/dist/installer/install.ps1'
    if (-not (Test-Path -LiteralPath $InstallerPath)) { throw 'The MCP tarball does not contain the lifecycle installer.' }
    $Result.checks += 'mcp-installer-extracted'
    $Npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $Npm) { throw 'npm.cmd is not on PATH; the host must provide Node.js.' }
    $McpPrefix = Join-Path $Temporary 'mcp install'
    $Install = Invoke-Program $Npm @('install', '--prefix', $McpPrefix, '--no-audit', '--no-fund', '--loglevel', 'error', $Tarball) 900000
    if ($Install.ExitCode -ne 0) { throw ('npm could not install the MCP tarball: ' + $Install.Stderr) }
    $McpEntry = Join-Path $McpPrefix 'node_modules/@xu123/astrophoto-flow/dist/index.js'
    if (-not (Test-Path -LiteralPath $McpEntry)) { throw 'The installed MCP has no dist/index.js entry point.' }
    $Result.checks += 'mcp-tarball-install'

    $Node = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
    if (-not $Node) { throw 'node.exe is not on PATH; the host must provide Node.js.' }

    # Scenario 1: a fresh MCP-first install in paths with spaces, then the full
    # init -> start -> nodes -> stop -> start cycle through public tool calls.
    $InstallRoot = Join-Path $Temporary 'application with spaces'
    $Workspace = Join-Path $Temporary 'workspace with spaces'
    $ScenarioPath = Join-Path $Temporary 'scenario.json'
    $Scenario = [ordered]@{
        version = $Manifest.version
        workspace = $Workspace
        installRoot = $InstallRoot
        webIndexSha256 = $Manifest.web_index_sha256
        mcp = [ordered]@{
            command = $Node
            args = @($McpEntry, '--install-root', $InstallRoot, '--workspace', $Workspace, '--candidate-manifest', $ManifestPath)
        }
        expectNotInstalled = $true
        occupiedPorts = @(8188, 8190)
    }
    if ($Manifest.publication -ne 'candidate') {
        $Scenario.mcp.args = @($McpEntry, '--install-root', $InstallRoot, '--workspace', $Workspace)
    }
    [IO.File]::WriteAllText($ScenarioPath, ($Scenario | ConvertTo-Json -Depth 6))
    $Probe = Invoke-Program $Node @((Join-Path $PSScriptRoot 'probe-mcp.ts'), $ScenarioPath) 2400000
    if ($Probe.ExitCode -ne 0) { throw ('The MCP lifecycle probe failed: ' + $Probe.Stderr + $Probe.Stdout) }
    $Observed = $Probe.Stdout | ConvertFrom-Json
    foreach ($Check in $Observed.checks) { $Result.checks += $Check }
    $Receipt = Get-Content -LiteralPath (Join-Path $InstallRoot 'installation.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Receipt.version -ne $Manifest.version -or $Receipt.publication -ne $Manifest.publication) { throw 'The installation receipt does not match the manifest.' }
    if ($Receipt.source -ne 'candidate' -and $Manifest.publication -eq 'candidate') { throw 'A candidate manifest did not produce a candidate installation receipt.' }

    # Scenario 2: a reinstall over the same root and workspace keeps user data.
    $ConfigHash = (Get-FileHash -LiteralPath (Join-Path $Workspace 'config.toml')).Hash
    $Sentinel = Join-Path $Workspace 'preserve-this-original.txt'
    [IO.File]::WriteAllText($Sentinel, 'Original workspace data must survive reinstall.')
    $SentinelHash = (Get-FileHash -LiteralPath $Sentinel).Hash
    $Reinstall = Invoke-Json $WindowsPowerShell @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $InstallerPath,
        '-Version', $Manifest.version, '-InstallRoot', $InstallRoot, '-Workspace', $Workspace,
        '-OperationId', 'acceptance-reinstall', '-Json', '-ManifestPath', $ManifestPath
    ) 1800000
    if ($Reinstall.status -ne 'installed') { throw 'The reinstall did not report installed.' }
    if ((Get-FileHash -LiteralPath (Join-Path $Workspace 'config.toml')).Hash -ne $ConfigHash) { throw 'The reinstall rewrote the workspace configuration.' }
    if ((Get-FileHash -LiteralPath $Sentinel).Hash -ne $SentinelHash) { throw 'The reinstall lost existing workspace data.' }
    $Result.checks += 'idempotent-reinstall-preserves-workspace'

    # Scenario 3: an interrupted uv download resumes from the partial file.
    $ResumeRoot = Join-Path $Temporary 'resume root'
    $ResumeWorkspace = Join-Path $Temporary 'resume workspace'
    $ResumeCache = Join-Path $ResumeRoot 'cache'
    [void][IO.Directory]::CreateDirectory($ResumeCache)
    [IO.File]::WriteAllText((Join-Path $ResumeRoot '.astrophoto-flow-installation'), $Manifest.repository)
    $UvArchiveName = 'uv-' + $Manifest.runtime.uv.version + '-windows-x64.zip'
    $SourceArchive = Join-Path $InstallRoot ('cache/' + $UvArchiveName)
    $PartialArchive = Join-Path $ResumeCache ($UvArchiveName + '.partial')
    $InputFile = [IO.File]::OpenRead($SourceArchive)
    $PartialFile = [IO.File]::Create($PartialArchive)
    try {
        $Remaining = [long]($InputFile.Length / 2)
        $Buffer = New-Object byte[] 65536
        while ($Remaining -gt 0) {
            $Count = $InputFile.Read($Buffer, 0, [int][Math]::Min($Buffer.Length, $Remaining))
            if ($Count -eq 0) { throw 'Cannot prepare the interrupted-download scenario.' }
            $PartialFile.Write($Buffer, 0, $Count)
            $Remaining -= $Count
        }
    } finally { $InputFile.Dispose(); $PartialFile.Dispose() }
    $Resume = Invoke-Json $WindowsPowerShell @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $InstallerPath,
        '-Version', $Manifest.version, '-InstallRoot', $ResumeRoot, '-Workspace', $ResumeWorkspace,
        '-OperationId', 'acceptance-resume', '-Json', '-ManifestPath', $ManifestPath
    ) 1800000
    if ($Resume.status -ne 'installed') { throw 'The resumed install did not report installed.' }
    if (Test-Path -LiteralPath $PartialArchive) { throw 'The installer left the interrupted download partial file behind.' }
    if ((Get-FileHash -LiteralPath (Join-Path $ResumeRoot ('cache/' + $UvArchiveName)) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Manifest.runtime.uv.sha256) {
        throw 'The resumed runtime archive has the wrong checksum.'
    }
    $Result.checks += 'interrupted-download-resumed'

    # Scenario 4: a corrupt payload hash is refused before anything is activated.
    $BadDirectory = Join-Path $Temporary 'bad candidate'
    [void][IO.Directory]::CreateDirectory($BadDirectory)
    Copy-Item -LiteralPath (Join-Path $ReleaseDirectory $Manifest.workbench.file) -Destination (Join-Path $BadDirectory $Manifest.workbench.file)
    $BadManifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $BadManifest.workbench.sha256 = '0' * 64
    $BadPath = Join-Path $BadDirectory 'release-manifest.json'
    [IO.File]::WriteAllText($BadPath, ($BadManifest | ConvertTo-Json -Depth 8))
    $BadRoot = Join-Path $Temporary 'rejected installation'
    $BadWorkspace = Join-Path $Temporary 'unused workspace'
    $BadRun = Invoke-Program $WindowsPowerShell @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $InstallerPath,
        '-Version', $Manifest.version, '-InstallRoot', $BadRoot, '-Workspace', $BadWorkspace,
        '-OperationId', 'acceptance-checksum', '-Json', '-ManifestPath', $BadPath
    ) 900000
    Assert-Refusal 'checksum-failure-not-activated' $BadRun 'SHA-256 mismatch'
    if (Test-Path -LiteralPath (Join-Path $BadRoot 'installation.json')) { throw 'A corrupt candidate was activated.' }
    $Result.checks += 'checksum-failure-not-activated'

    # Scenario 5: directory guards refuse an unknown non-empty root, a root that
    # is also the workspace, and a workspace inside the managed version tree.
    $UnknownRoot = Join-Path $Temporary 'unknown root'
    [void][IO.Directory]::CreateDirectory($UnknownRoot)
    [IO.File]::WriteAllText((Join-Path $UnknownRoot 'someone-elses-file.txt'), 'not ours')
    $UnknownRun = Invoke-Program $WindowsPowerShell @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $InstallerPath,
        '-Version', $Manifest.version, '-InstallRoot', $UnknownRoot, '-Workspace', (Join-Path $Temporary 'unknown workspace'),
        '-OperationId', 'acceptance-unknown', '-Json', '-ManifestPath', $ManifestPath
    ) 900000
    Assert-Refusal 'directory-guard-non-empty-root' $UnknownRun 'INSTALL_ROOT_NOT_EMPTY'
    if (@(Get-ChildItem -LiteralPath $UnknownRoot -Force).Count -ne 1 -or [IO.File]::ReadAllText((Join-Path $UnknownRoot 'someone-elses-file.txt')) -ne 'not ours') {
        throw 'The refused install changed an unknown directory.'
    }
    $SameRun = Invoke-Program $WindowsPowerShell @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $InstallerPath,
        '-Version', $Manifest.version, '-InstallRoot', $UnknownRoot, '-Workspace', $UnknownRoot,
        '-OperationId', 'acceptance-same-root', '-Json', '-ManifestPath', $ManifestPath
    ) 900000
    Assert-Refusal 'directory-guard-workspace-is-root' $SameRun 'Workspace must differ from the install root.'
    $InsideVersions = Join-Path $InstallRoot ('versions/' + $Manifest.version + '/nested workspace')
    $VersionRun = Invoke-Program $WindowsPowerShell @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $InstallerPath,
        '-Version', $Manifest.version, '-InstallRoot', $InstallRoot, '-Workspace', $InsideVersions,
        '-OperationId', 'acceptance-versions', '-Json', '-ManifestPath', $ManifestPath
    ) 900000
    Assert-Refusal 'directory-guard-workspace-in-versions' $VersionRun 'Workspace must be outside version, runtime and cache directories.'
    $Result.checks += 'directory-guards'

    # Scenario 6: a process record whose pid belongs to someone else is refused,
    # and the foreign process is left alive.
    $Foreign = Start-Process -FilePath $WindowsPowerShell -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 300') -PassThru
    try {
        Start-Sleep -Milliseconds 500
        $ForeignProcess = Get-Process -Id $Foreign.Id
        $Record = [ordered]@{
            schema_version = 1
            workspace = $Workspace
            version = $Manifest.version
            operation_id = 'start-foreign-pid'
            phase = 'ready'
            started_at = [DateTime]::UtcNow.ToString('o')
            service = [ordered]@{ pid = $Foreign.Id; create_time = 0.0; exe = $ForeignProcess.Path; cmdline = @('not', 'our', 'service'); cwd = $Temporary }
            engine = $null
            client = $null
            message = $null
        }
        [IO.File]::WriteAllText((Join-Path $Workspace 'run/processes.json'), ($Record | ConvertTo-Json -Depth 6))
        $ForeignStop = Invoke-Controller $Receipt @('stop', '--workspace', $Workspace, '--json')
        Assert-Refusal 'foreign-pid-stop-refused' $ForeignStop 'PROCESS_IDENTITY_MISMATCH'
        if ($null -eq (Get-Process -Id $Foreign.Id -ErrorAction SilentlyContinue)) { throw 'The refused stop killed a process it did not own.' }
    } finally {
        Remove-Item -LiteralPath (Join-Path $Workspace 'run/processes.json') -ErrorAction SilentlyContinue
        if ($null -ne (Get-Process -Id $Foreign.Id -ErrorAction SilentlyContinue)) { Stop-Process -Id $Foreign.Id -Force }
    }
    $Result.checks += 'foreign-pid-stop-refused'

    # Scenario 7: after every stop the MCP still answers and the workspace keeps
    # its configuration, database and assets.
    $FinalScenario = [ordered]@{
        version = $Manifest.version
        workspace = $Workspace
        installRoot = $InstallRoot
        webIndexSha256 = $Manifest.web_index_sha256
        mcp = [ordered]@{
            command = $Node
            args = @($McpEntry, '--install-root', $InstallRoot, '--workspace', $Workspace)
        }
        expectNotInstalled = $false
        occupiedPorts = @()
    }
    [IO.File]::WriteAllText($ScenarioPath, ($FinalScenario | ConvertTo-Json -Depth 6))
    $Final = Invoke-Program $Node @((Join-Path $PSScriptRoot 'probe-mcp.ts'), $ScenarioPath) 2400000
    if ($Final.ExitCode -ne 0) { throw ('The final MCP cycle failed: ' + $Final.Stderr + $Final.Stdout) }
    if (-not (Test-Path -LiteralPath (Join-Path $Workspace 'data/workbench.sqlite3'))) { throw 'The workspace lost its database.' }
    if (-not (Test-Path -LiteralPath (Join-Path $Workspace 'data/engine/user'))) { throw 'The workspace lost its asset directories.' }
    $Result.checks += 'workspace-data-preserved'
    $Stopped = $true
    $Result.status = 'passed'
} catch {
    $Result.error = $_.Exception.Message
    [Console]::Error.WriteLine($Result.error)
    $Stopped = $false
} finally {
    if (-not $Stopped) {
        try {
            $CleanupReceipt = Get-Content -LiteralPath (Join-Path $Temporary 'application with spaces/installation.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $Cleanup = Invoke-Controller $CleanupReceipt @('stop', '--workspace', $CleanupReceipt.workspace, '--json')
            $Stopped = $Cleanup.ExitCode -eq 0
        } catch { [Console]::Error.WriteLine('Temporary workspace shutdown remains unconfirmed.') }
    }
    if (-not (Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($Report)))) { [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Report)) }
    [IO.File]::WriteAllText($Report, ($Result | ConvertTo-Json -Depth 8))
    if ($Stopped -and -not $KeepTemporary) { Remove-Item -LiteralPath $Temporary -Recurse -Force -ErrorAction SilentlyContinue }
    else { [Console]::Error.WriteLine('Acceptance directory retained: ' + $Temporary) }
}
if ($Result.status -ne 'passed') { exit 1 }
Write-Output $Report
