#!/bin/bash

echo "======================================================"
echo "            FIBECHAT DOCKER STARTUP SCRIPT            "
echo "======================================================"
echo

echo "📂 Navigating to fibechat directory..."
cd fibechat
echo "✅ Successfully changed to $(pwd)"

echo
echo "🔄 Checking Docker status..."
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running or not installed!"
    echo "🔧 Please start Docker and try again."
    exit 1
else
    echo "✅ Docker is running properly!"
fi

echo
echo "🔄 Updating from Git repository..."
echo "⏳ Checking out production release branch..."
git checkout release/prod
echo "⏳ Pulling latest changes..."
git pull
echo "✅ Repository updated successfully!"

echo
echo "🚀 Starting FibeChat services with Docker Compose..."
echo "⏳ This might take a while depending on your internet connection..."
echo "⚙️  Services are being initialized..."

sh run.sh

echo
echo "🔄 Docker Compose has been terminated."
echo "👋 Thank you for using FibeChat!"
echo "======================================================"