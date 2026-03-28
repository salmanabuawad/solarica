@echo off
echo Starting Solarica .NET Connector (direct mode, not as service)...

if exist dist\SolaricaConnector.exe (
    cd dist
    SolaricaConnector.exe
) else (
    echo Build output not found. Run install.bat first, or:
    cd SolaricaConnector
    dotnet run
)
