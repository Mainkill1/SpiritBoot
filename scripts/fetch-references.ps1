param(
    [string]$Root = ".reference"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Root | Out-Null

function Get-ReferenceRepo {
    param(
        [string]$Name,
        [string]$Url,
        [switch]$Recursive
    )

    $Path = Join-Path $Root $Name

    if (Test-Path (Join-Path $Path ".git")) {
        Write-Host "[update] $Name"
        git -C $Path pull --ff-only
        if ($Recursive) {
            git -C $Path submodule update --init --recursive --depth 1
        }
        return
    }

    Write-Host "[clone]  $Name"
    if ($Recursive) {
        git clone --depth 1 --recurse-submodules --shallow-submodules $Url $Path
    }
    else {
        git clone --depth 1 $Url $Path
    }
}

Get-ReferenceRepo -Name "cromwell"      -Url "https://github.com/XboxDev/cromwell.git"
Get-ReferenceRepo -Name "xemu"          -Url "https://github.com/xemu-project/xemu.git"
Get-ReferenceRepo -Name "cxbx-reloaded" -Url "https://github.com/Cxbx-Reloaded/Cxbx-Reloaded.git"
Get-ReferenceRepo -Name "nxdk"          -Url "https://github.com/XboxDev/nxdk.git" -Recursive
Get-ReferenceRepo -Name "xboxpy"        -Url "https://github.com/XboxDev/xboxpy.git"
Get-ReferenceRepo -Name "xbox-linux"    -Url "https://github.com/XboxDev/xbox-linux.git"

Write-Host ""
Write-Host "Reference repositories are available under: $Root"
Write-Host "They are research inputs, not automatically part of the SpiritBoot build."
