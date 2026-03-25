#!/bin/bash
set -e

echo "📤 Pushing to git..."
git push

echo "🛑 Tearing down containers..."
docker-compose down

echo "🔨 Building containers..."
docker-compose build

echo "🚀 Starting containers..."
docker-compose up -d

echo "✅ Done! Containers are running."
docker-compose ps
