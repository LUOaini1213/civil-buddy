# Civil Buddy local desktop window (not Tencent WorkBuddy).
# Starts the on-machine workbench and opens an app window to 127.0.0.1.
# Does not default D:\layout. Does not log into Tencent.

param(
    [int]$Port = 0,
    [string]$JobRoot = "",
    [switch]$NoWindow
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

if ($JobRoot) {
    $jr = [IO.Path]::GetFullPath($JobRoot)
    $low = $jr.ToLower().Replace('/', '\')
    if ($low -eq 'd:\layout' -or $low.StartsWith('d:\layout\')) {
        throw 'Forbidden job root D:\layout. Use a project folder.'
    }
    if (-not (Test-Path -LiteralPath $jr)) {
        throw "CIVIL_JOB_ROOT is not a directory: $jr"
    }
    $env:CIVIL_JOB_ROOT = $jr
}

if (-not $env:CIVIL_PORT) { $env:CIVIL_PORT = "8765" }
if ($Port -gt 0) { $env:CIVIL_PORT = [string]$Port }
$usePort = [int]$env:CIVIL_PORT

function Test-PortOpen {
    param([int]$ListenPort)
    $c = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $c.BeginConnect("127.0.0.1", $ListenPort, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(200)
        if ($ok) { $c.EndConnect($iar) | Out-Null }
        return $ok
    } catch {
        return $false
    } finally {
        $c.Close()
    }
}

$already = Test-PortOpen -ListenPort $usePort
if (-not $already) {
    $exeCandidates = @(
        (Join-Path $Repo "workbench\target\release\civil-workbench.exe"),
        (Join-Path $Repo "civil-workbench.exe")
    )
    $exe = $exeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    $wb = Join-Path $Repo "workbench\run.ps1"
    $py = Join-Path $Repo "demo\run.ps1"
    if ($exe) {
        Start-Process -FilePath $exe -WorkingDirectory $Repo -WindowStyle Minimized
    } elseif (Test-Path $wb) {
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File",$wb -WorkingDirectory (Join-Path $Repo "workbench") -WindowStyle Minimized
    } elseif (Test-Path $py) {
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File",$py -WorkingDirectory (Join-Path $Repo "demo") -WindowStyle Minimized
    } else {
        throw "Missing civil-workbench.exe, workbench\run.ps1 and demo\run.ps1"
    }
    $n = 0
    while (-not (Test-PortOpen -ListenPort $usePort)) {
        $n++
        if ($n -gt 90) {
            throw "Workbench did not bind 127.0.0.1:$usePort"
        }
        Start-Sleep -Milliseconds 500
    }
}

$url = "http://127.0.0.1:$usePort/"
Write-Host "Civil Buddy $url"
if ($env:CIVIL_JOB_ROOT) { Write-Host "job root $($env:CIVIL_JOB_ROOT)" }
if ($NoWindow) { exit 0 }

$candidates = @()
if (${env:ProgramFiles(x86)}) {
    $candidates += (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe")
}
if ($env:ProgramFiles) {
    $candidates += (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe")
    $candidates += (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe")
}
if ($env:LOCALAPPDATA) {
    $candidates += (Join-Path $env:LOCALAPPDATA "Microsoft\Edge\Application\msedge.exe")
    $candidates += (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
}
$browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($browser) {
    Start-Process -FilePath $browser -ArgumentList "--app=$url","--window-size=1440,900"
} else {
    Start-Process $url
}
