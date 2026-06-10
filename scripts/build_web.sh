#!/bin/bash
set -e
echo "Building React frontend..."
cd web
npm install
npm run build
cd ..
echo "Copying dist to agentguard/web/dist/..."
rm -rf agentguard/web/dist
cp -r web/dist agentguard/web/dist
echo "Done."
