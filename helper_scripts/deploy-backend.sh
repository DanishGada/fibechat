#!/bin/bash

# Deployment script for backend services
echo "🚀 Starting backend deployment..."

# Try fibechat directory first, fallback to home directory
cd /home/danishg/ || {
    echo "❌ Critical error: Failed to access both directories"
    exit 1
}

echo "✅ Directory changed to: $(pwd)"
echo "🔧 Executing backend deployment script..."

sh deploy-backend.sh || {
    echo "💥 Backend deployment failed!"
    exit 1
}

echo "🎉 Backend deployment completed successfully!"