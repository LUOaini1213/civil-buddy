# 无管理员权限启动 skjolber-service（用户目录 JDK17 + Maven）
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts/start_skjolber_user.ps1
#
# 不写系统环境变量；仅当前进程使用 JAVA_HOME / PATH。

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$ServiceDir = Join-Path $Root "skjolber-service"

# 常见用户目录 JDK / Maven（无管理员安装）
$JdkCandidates = @(
  "$env:USERPROFILE\tools\jdk-17",
  "$env:USERPROFILE\tools\jdk17",
  "$env:USERPROFILE\jdk-17",
  "$env:LOCALAPPDATA\Programs\Eclipse Adoptium\jdk-17*",
  "$env:LOCALAPPDATA\Programs\Microsoft\jdk-17*",
  "C:\Users\$env:USERNAME\tools\jdk-17"
)
$MvnCandidates = @(
  "$env:USERPROFILE\tools\maven",
  "$env:USERPROFILE\tools\apache-maven-3.9.11",
  "$env:USERPROFILE\apache-maven-3.9.11",
  "C:\Users\$env:USERNAME\tools\maven"
)

function Find-FirstExisting($paths) {
  foreach ($p in $paths) {
    $resolved = Get-Item $p -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($resolved -and (Test-Path $resolved.FullName)) {
      return $resolved.FullName
    }
  }
  return $null
}

$jdk = Find-FirstExisting $JdkCandidates
$mvnHome = Find-FirstExisting $MvnCandidates

if (-not $jdk) {
  # 已在 PATH 的 java
  $javaCmd = Get-Command java -ErrorAction SilentlyContinue
  if (-not $javaCmd) {
    Write-Host @"
[错误] 未找到用户目录 JDK 17。

无管理员安装（任选）:
  1) 下载 Temurin 17 .zip（非 .msi）解压到:  %USERPROFILE%\tools\jdk-17
  2) 或 winget --scope user install EclipseAdoptium.Temurin.17.JDK

然后重新运行本脚本。
"@
    exit 1
  }
  Write-Host "使用 PATH 中的 java: $($javaCmd.Source)"
} else {
  $env:JAVA_HOME = $jdk
  $env:Path = "$jdk\bin;" + $env:Path
  Write-Host "JAVA_HOME=$jdk"
}

if ($mvnHome) {
  $env:Path = "$mvnHome\bin;" + $env:Path
  Write-Host "Maven home=$mvnHome"
}

$mvn = Get-Command mvn -ErrorAction SilentlyContinue
if (-not $mvn) {
  Write-Host @"
[错误] 未找到 Maven。

无管理员: 下载 Maven binary zip 解压到 %USERPROFILE%\tools\maven
  https://maven.apache.org/download.cgi
"@
  exit 1
}

Write-Host "java:"; java -version 2>&1 | Select-Object -First 1
Write-Host "mvn:"; mvn -version 2>&1 | Select-Object -First 2
Write-Host ""
Write-Host "Starting skjolber-service on http://127.0.0.1:8080 ..."
Write-Host "  GET  /api/v1/packer/health"
Write-Host "  POST /api/v1/packer/pack"
Write-Host ""

Set-Location $ServiceDir
# 用户级本地仓库，避免写 Program Files
$env:MAVEN_OPTS = $env:MAVEN_OPTS
if (-not $env:MAVEN_USER_HOME) {
  $env:MAVEN_USER_HOME = Join-Path $env:USERPROFILE ".m2"
}

mvn -q -DskipTests spring-boot:run
