#!/usr/bin/env bash
set -e

if [ -f dist/SolaricaConnector ]; then
    echo "Starting Solarica .NET Connector on http://127.0.0.1:8765 ..."
    cd dist && ./SolaricaConnector
else
    echo "Build output not found. Run ./install.sh first, or:"
    cd SolaricaConnector && dotnet run
fi
