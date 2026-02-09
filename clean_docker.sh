#!/bin/bash
# clean_docker.sh
# Script to forcefully clean up Docker resources for ai_daytrader to fix KeyError issues.

echo "Stopping containers..."
docker-compose down

echo "Force removing containers (by name)..."
docker rm -f ai_daytrader
docker rm -f ai_trader

echo "Finding and removing any 'ai_daytrader' related containers by ID..."
# Filter for containers using the image or name and kill them
docker ps -a | grep "ai_daytrader" | awk '{print $1}' | xargs -r docker rm -f

echo "Removing the image..."
docker rmi -f ai_daytrader:latest

echo "Pruning stopped containers (interactive)..."
docker container prune

echo "Cleanup complete. Try running 'docker-compose up -d --build' now."
