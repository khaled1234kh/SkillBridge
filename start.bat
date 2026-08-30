@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is required. Install it from https://www.docker.com/products/docker-desktop/
  pause
  exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is installed but is not running. Start it and try again.
  pause
  exit /b 1
)

echo Building and starting SkillBridge containers...
docker compose up --build -d
if errorlevel 1 (
  echo.
  echo Startup failed. The error above explains why.
  docker compose ps
  pause
  exit /b 1
)

echo.
echo SkillBridge is starting in Docker.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
docker compose ps
pause
