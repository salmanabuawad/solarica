using SolaricaConnector.Models;

namespace SolaricaConnector.Services;

/// <summary>
/// Simulates a connected PVPM 1540X device for development and demo use.
/// </summary>
public sealed class MockDriver : IDeviceDriver
{
    private bool _connected;
    private string? _port;

    public DeviceStatus Detect() => new(
        Connected: _connected,
        Mode: "mock",
        Port: _port,
        DeviceModel: "PVPM 1540X",
        DeviceSerial: "PVPM1540X-MOCK-001",
        FirmwareVersion: "mock-1.0",
        TransferModeRequired: true,
        TransferModeDetected: _connected,
        LastError: null
    );

    public IReadOnlyList<PortInfo> ListPorts() =>
    [
        new("MOCK1", "Mock PVPM device (port A)"),
        new("MOCK2", "Mock PVPM device (port B)"),
    ];

    public DeviceStatus Connect(string port)
    {
        _connected = true;
        _port = port;
        return Detect();
    }

    public void Disconnect()
    {
        _connected = false;
        _port = null;
    }

    public bool IsTransferMode() => _connected;

    public IReadOnlyList<Measurement> FetchMeasurements() =>
        MockDataGenerator.Generate(25);
}

// ---------------------------------------------------------------------------
// Mock data generator
// ---------------------------------------------------------------------------

internal static class MockDataGenerator
{
    public static IReadOnlyList<Measurement> Generate(int count)
    {
        var rng = new Random(42);
        var baseTime = DateTime.UtcNow.AddDays(-count);
        var customers = new[] { "Qun Energy", "SolarTech Ltd", "PV Solutions" };
        var moduleTypes = new[] { "CS6U-320P", "JAM72S10-380/MR", "LR4-72HBD-430M" };
        var sites = new[] { "S.1.1", "S.1.2", "S.2.1", "S.2.2", "S.3.1" };
        var list = new List<Measurement>(count);

        for (int i = 0; i < count; i++)
        {
            double voc = 38.0 + rng.NextDouble() * 4.0;
            double isc = 8.8 + rng.NextDouble() * 0.6;
            double ff = 0.74 + rng.NextDouble() * 0.07;
            double vpmax = voc * (0.76 + rng.NextDouble() * 0.06);
            double ipmax = isc * (0.90 + rng.NextDouble() * 0.05);
            double ppk = vpmax * ipmax;

            var measuredAt = baseTime.AddHours(i * 4);
            var id = Guid.NewGuid().ToString("N");

            list.Add(new Measurement(
                Id: id,
                ExternalMeasurementKey: $"PVPM-{id[..8].ToUpper()}",
                MeasuredAt: measuredAt,
                Customer: customers[rng.Next(customers.Length)],
                Installation: $"Plant-{rng.Next(1, 4):D2}",
                StringNo: sites[rng.Next(sites.Length)],
                ModuleType: moduleTypes[rng.Next(moduleTypes.Length)],
                ModuleReference: null,
                ModulesSeries: 20,
                ModulesParallel: 1,
                NominalPowerW: 320.0,
                PpkWp: Math.Round(ppk, 3),
                RsOhm: Math.Round(0.25 + rng.NextDouble() * 0.30, 4),
                RpOhm: Math.Round(80.0 + rng.NextDouble() * 80.0, 2),
                VocV: Math.Round(voc, 4),
                IscA: Math.Round(isc, 4),
                VpmaxV: Math.Round(vpmax, 4),
                IpmaxA: Math.Round(ipmax, 4),
                FfPercent: Math.Round(ff * 100, 2),
                SweepDurationMs: Math.Round(100.0 + rng.NextDouble() * 100.0, 1),
                IrradianceWM2: Math.Round(700.0 + rng.NextDouble() * 350.0, 1),
                SensorTempC: Math.Round(25.0 + rng.NextDouble() * 25.0, 1),
                ModuleTempC: Math.Round(30.0 + rng.NextDouble() * 25.0, 1),
                IrradianceSensorType: "Si-pyranometer",
                IrradianceSensorSerial: $"SEN-{rng.Next(1000, 9999)}",
                ImportSource: "mock",
                SyncStatus: "unsynced",
                Notes: null,
                CurvePoints: GenerateCurve(voc, isc)
            ));
        }
        return list;
    }

    private static IReadOnlyList<CurvePoint> GenerateCurve(double voc, double isc, int n = 50)
    {
        var pts = new List<CurvePoint>(n);
        for (int i = 0; i < n; i++)
        {
            double v = voc * i / (n - 1);
            double exponent = (v - voc) / (0.026 * 25);
            double current = Math.Max(0.0, isc * (1 - Math.Exp(exponent)));
            pts.Add(new(i, Math.Round(v, 4), Math.Round(current, 4)));
        }
        return pts;
    }
}
