#!/bin/bash

cd /home/danishg || {
    echo "❌ Failed to change directory to /home/danishg"
    exit 1
}

sh deploy-full.sh