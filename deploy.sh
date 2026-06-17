#!/bin/bash

clear

# Build image
docker compose build

# Resume service
docker compose up -d
