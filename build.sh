#!/bin/bash
set -e

echo "🔍 Installing Stockfish..."
# Try to install Stockfish (might work on Render)
apt-get update && apt-get install -y stockfish || echo "⚠️ Could not install via apt, will try alternative"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Build React app
echo "⚛️ Building React frontend..."
cd mcb-react
npm install
npm run build
cd ..

echo "✅ Build complete!" 