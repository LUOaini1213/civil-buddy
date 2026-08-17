$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
Set-Location $PSScriptRoot
if (-not $env:CIVIL_PORT) { $env:CIVIL_PORT = "8765" }
cargo run --release --bin civil-workbench
