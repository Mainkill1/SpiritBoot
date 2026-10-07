param(
    [string]$Root = ".reference",
    [switch]$Update
)

$ErrorActionPreference = "Stop"
$Tab = [char]9
New-Item -ItemType Directory -Force -Path $Root | Out-Null

$Repos = @(
    @{ Name="roswell"; Url="https://github.com/mborgerson/roswell.git"; Branch="main"; Recursive=$false },
    @{ Name="fancy-mouse"; Url="https://github.com/SnowyMouse/fancy-mouse-boot-rom.git"; Branch="master"; Recursive=$false },
    @{ Name="xemu-fork"; Url="https://github.com/Mainkill1/xemu.git"; Branch="main"; Recursive=$false },
    @{ Name="xemu"; Url="https://github.com/xemu-project/xemu.git"; Branch="master"; Recursive=$false },
    @{ Name="kernel-tests"; Url="https://github.com/Cxbx-Reloaded/xbox_kernel_test_suite.git"; Branch="master"; Recursive=$false },
    @{ Name="cxbx-reloaded"; Url="https://github.com/Cxbx-Reloaded/Cxbx-Reloaded.git"; Branch="master"; Recursive=$true },
    @{ Name="xb-symbol-database"; Url="https://github.com/Cxbx-Reloaded/XbSymbolDatabase.git"; Branch="master"; Recursive=$false },
    @{ Name="nxdk"; Url="https://github.com/XboxDev/nxdk.git"; Branch="master"; Recursive=$true },
    @{ Name="cromwell"; Url="https://github.com/XboxDev/cromwell.git"; Branch="master"; Recursive=$false },
    @{ Name="xboxpy"; Url="https://github.com/XboxDev/xboxpy.git"; Branch="master"; Recursive=$false },
    @{ Name="xbox-linux"; Url="https://github.com/XboxDev/xbox-linux.git"; Branch="xbox-linux"; Recursive=$false }
)

$versions = @((@("id","branch","commit","remote") -join $Tab))

foreach ($repo in $Repos) {
    $Path = Join-Path $Root $repo.Name
    if (-not (Test-Path (Join-Path $Path ".git"))) {
        Write-Host "[clone]  $($repo.Name)"
        $args = @("clone","--branch",$repo.Branch)
        if ($repo.Recursive) { $args += "--recurse-submodules" }
        $args += @($repo.Url,$Path)
        & git @args
        if ($LASTEXITCODE -ne 0) { throw "clone failed: $($repo.Name)" }
    } elseif ($Update) {
        Write-Host "[update] $($repo.Name)"
        & git -C $Path fetch --all --prune
        & git -C $Path checkout $repo.Branch
        & git -C $Path pull --ff-only
        if ($repo.Recursive) { & git -C $Path submodule update --init --recursive }
        if ($LASTEXITCODE -ne 0) { throw "update failed: $($repo.Name)" }
    } else {
        Write-Host "[keep]   $($repo.Name)"
    }

    $commit = (& git -C $Path rev-parse HEAD).Trim()
    $remote = (& git -C $Path remote get-url origin).Trim()
    $versions += (@($repo.Name,$repo.Branch,$commit,$remote) -join $Tab)
}

$versions | Set-Content (Join-Path $Root ".versions.tsv")
Write-Host "Exact revisions written to $Root/.versions.tsv"
