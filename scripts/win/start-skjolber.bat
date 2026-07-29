@echo off
chcp 65001 >nul
title skjolber-service :8080 (用户权限, 无需管理员)
cd /d "%~dp0"

REM 用户目录 JDK（无管理员 zip 解压即可）
if exist "%USERPROFILE%\tools\jdk-17" set "JAVA_HOME=%USERPROFILE%\tools\jdk-17"
if defined JAVA_HOME set "PATH=%JAVA_HOME%\bin;%PATH%"

where java >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 java。
  echo 无管理员: 下载 Temurin 17 zip 解压到 %%USERPROFILE%%\tools\jdk-17
  pause
  exit /b 1
)

set "JAR=%~dp0skjolber-service\target\skjolber-service-1.0.0.jar"
set "RUNDIR=%USERPROFILE%\tools\skjolber-run"
if not exist "%JAR%" (
  echo [提示] 未找到已编译 jar，尝试用 Maven 打包...
  if exist "%USERPROFILE%\tools\maven" set "PATH=%USERPROFILE%\tools\maven\bin;%PATH%"
  where mvn >nul 2>&1
  if errorlevel 1 (
    echo [错误] 无 jar 且无 mvn。请先在有网时执行:
    echo   cd skjolber-service ^& mvn -DskipTests package
    pause
    exit /b 1
  )
  cd skjolber-service
  call mvn -q -DskipTests package
  cd /d "%~dp0"
)

if not exist "%JAR%" (
  echo [错误] 打包后仍无 jar: %JAR%
  pause
  exit /b 1
)

REM 中文路径下 java -jar 可能异常：复制到用户 ASCII 目录再启动
if not exist "%RUNDIR%" mkdir "%RUNDIR%"
copy /Y "%JAR%" "%RUNDIR%\skjolber-service-1.0.0.jar" >nul

echo 启动 skjolber http://127.0.0.1:8080
echo   健康检查: http://127.0.0.1:8080/api/v1/packer/health
echo   网关请设 SKJOLBER_URL=http://127.0.0.1:8080 或使用已写好的 .env
echo Ctrl+C 停止
echo.
java -jar "%RUNDIR%\skjolber-service-1.0.0.jar"
pause
