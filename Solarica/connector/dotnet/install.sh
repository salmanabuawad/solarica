#!/usr/bin/env bash
set -e

echo "============================================================"
echo " Solarica .NET Connector - Linux / macOS Installer"
echo "============================================================"
echo

if ! command -v dotnet &>/dev/null; then
    echo "ERROR: .NET 8 SDK not found."
    echo "Install from: https://dotnet.microsoft.com/download/dotnet/8.0"
    exit 1
fi

dotnet --version

echo
echo "[1/2] Publishing self-contained executable..."
cd SolaricaConnector
dotnet publish -c Release --self-contained true -o ../dist --nologo -v quiet
cd ..

echo "[2/2] Creating data folder..."
mkdir -p dist/data

chmod +x start.sh

echo
echo "============================================================"
echo " Installation complete!"
echo
echo " Run: ./start.sh"
echo " Or start the published binary: ./dist/SolaricaConnector"
echo " Edit dist/appsettings.json to configure."
echo "============================================================"
