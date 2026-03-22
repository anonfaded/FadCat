param(
    [switch]$SkipPyInstaller
)

$ErrorActionPreference = 'Stop'

Set-Location (Join-Path $PSScriptRoot '..\..')
$projectRoot = (Get-Location).Path

function Get-VersionMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$VersionFilePath
    )

    $content = Get-Content -LiteralPath $VersionFilePath -Raw

    function Get-MatchValue {
        param(
            [string]$Pattern,
            [string]$DefaultValue = ''
        )

        $match = [regex]::Match($content, $Pattern)
        if ($match.Success) {
            return $match.Groups[1].Value
        }

        return $DefaultValue
    }

    return [pscustomobject]@{
        AppName = Get-MatchValue -Pattern '__app_name__\s*=\s*"([^"]+)"' -DefaultValue 'FadCat'
        AppVersion = Get-MatchValue -Pattern '__version__\s*=\s*"([^"]+)"' -DefaultValue '1.0.0'
        AppDescription = Get-MatchValue -Pattern '__description__\s*=\s*"([^"]+)"' -DefaultValue 'FadCat'
        AppAuthor = Get-MatchValue -Pattern '__author__\s*=\s*"([^"]+)"' -DefaultValue 'Faded'
        AppCompany = Get-MatchValue -Pattern '__company__\s*=\s*"([^"]+)"' -DefaultValue 'FadSec Lab'
        AppWebsiteURL = Get-MatchValue -Pattern '__website_url__\s*=\s*"([^"]+)"' -DefaultValue 'https://fadseclab.com'
        AppGithubURL = Get-MatchValue -Pattern '__github_url__\s*=\s*"([^"]+)"' -DefaultValue 'https://github.com/anofaded/FadCat'
    }
}

function Get-InstallerVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Version
    )

    $parts = $Version.Split('.')
    if ($parts.Count -gt 4) {
        $parts = $parts[0..3]
    }

    while ($parts.Count -lt 4) {
        $parts += '0'
    }

    return ($parts -join '.')
}

function Get-IsccPath {
    $candidates = @(
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw 'Inno Setup compiler not found. Install Inno Setup 6 or add ISCC.exe to PATH.'
}

$metadata = Get-VersionMetadata -VersionFilePath (Join-Path $projectRoot 'src\version.py')
$installerVersion = Get-InstallerVersion -Version $metadata.AppVersion
$isccPath = Get-IsccPath
$specPath = Join-Path $projectRoot 'build\FadCat-Windows.spec'
$cliSpecPath = Join-Path $projectRoot 'build\FadCat-Windows-CLI.spec'
$issPath = Join-Path $projectRoot 'build\windows\fadcat.iss'

Write-Host "Building $($metadata.AppName) v$($metadata.AppVersion)"
Write-Host "Using Inno Setup compiler: $isccPath"

if (-not $SkipPyInstaller) {
    $pythonCommand = $null
    $pythonArguments = @()

    if (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonCommand = 'py'
        $pythonArguments = @('-3')
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCommand = 'python'
    }
    else {
        throw 'Python launcher not found. Install Python or make it available on PATH.'
    }

    try {
        & $pythonCommand @pythonArguments -m PyInstaller --version *> $null
    }
    catch {
        throw 'PyInstaller is not installed in the active Python environment. Install it with "pip install pyinstaller" and rerun the build.'
    }

    Write-Host "Building FadCat GUI version (console=False)..." -ForegroundColor Yellow
    & $pythonCommand @pythonArguments -m PyInstaller -y $specPath

    if ($LASTEXITCODE -ne 0) {
        throw 'PyInstaller GUI build failed.'
    }

    Write-Host "Building FadCat CLI version (console=True for stdin)..." -ForegroundColor Yellow
    & $pythonCommand @pythonArguments -m PyInstaller -y $cliSpecPath

    if ($LASTEXITCODE -ne 0) {
        throw 'PyInstaller CLI build failed.'
    }

    $distPath = Join-Path $projectRoot 'dist'
    $cliExeSrc = Join-Path (Join-Path $distPath 'FadCat-CLI') 'FadCat-CLI.exe'
    $cliExeDest = Join-Path (Join-Path $distPath 'FadCat') 'FadCat-CLI.exe'

    if (Test-Path $cliExeSrc) {
        Copy-Item -Path $cliExeSrc -Destination $cliExeDest -Force
        Write-Host "Copied FadCat-CLI.exe to bundle" -ForegroundColor Green
    }
    else {
        Write-Host "Warning: FadCat-CLI.exe not found at $cliExeSrc" -ForegroundColor Yellow
    }
}

Write-Host "Building Inno Setup installer..." -ForegroundColor Yellow

$appName = $metadata.AppName
$appVersion = $metadata.AppVersion
$appDesc = $metadata.AppDescription
$appAuthor = $metadata.AppAuthor
$appCompany = $metadata.AppCompany
$appWebsite = $metadata.AppWebsiteURL
$appGithub = $metadata.AppGithubURL

$isccArguments = @(
    "/DAppName=$appName"
    "/DAppVersion=$appVersion"
    "/DAppVersionInfo=$installerVersion"
    "/DAppDescription=$appDesc"
    "/DAppAuthor=$appAuthor"
    "/DAppCompany=$appCompany"
    "/DAppWebsiteURL=$appWebsite"
    "/DAppGithubURL=$appGithub"
    $issPath
)

& $isccPath @isccArguments

if ($LASTEXITCODE -ne 0) {
    throw 'Inno Setup compilation failed.'
}

Write-Host 'Windows installer build completed successfully.' -ForegroundColor Green
