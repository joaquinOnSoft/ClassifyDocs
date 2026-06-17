@echo off
setlocal

cls

set "COMPOSE_FILE=docker-compose.yaml;docker-compose.windows.yaml"

REM Build image
docker compose build

REM Resume service
docker compose up -d

endlocal