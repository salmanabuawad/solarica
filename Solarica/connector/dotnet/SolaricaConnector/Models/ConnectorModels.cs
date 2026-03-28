// Solarica Connector – shared JSON models.
// These match the Python connector's schema exactly (camelCase field names).

using System.Text.Json.Serialization;

namespace SolaricaConnector.Models;

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

public record HealthResponse(
    bool Ok,
    string Version,
    string Runtime = "dotnet"
);

// ---------------------------------------------------------------------------
// Device
// ---------------------------------------------------------------------------

public record PortInfo(string Name, string Description);

public record PortsResponse(IReadOnlyList<PortInfo> Items);

public record ConnectRequest(string Port);

public record DeviceStatus(
    bool Connected,
    string Mode,
    string? Port,
    string? DeviceModel,
    string? DeviceSerial,
    string? FirmwareVersion,
    bool TransferModeRequired = true,
    bool TransferModeDetected = false,
    string? LastError = null
);

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

public record ImportStartResult(bool Ok, int Imported);

public record ImportStatus(
    string State,
    int LastImportedCount = 0,
    int UnsyncedCount = 0
);

// ---------------------------------------------------------------------------
// Measurements
// ---------------------------------------------------------------------------

public record CurvePoint(int PointIndex, double VoltageV, double CurrentA);

public record Measurement(
    string Id,
    string? ExternalMeasurementKey,
    DateTime MeasuredAt,
    string? Customer,
    string? Installation,
    string? StringNo,
    string? ModuleType,
    string? ModuleReference,
    int? ModulesSeries,
    int? ModulesParallel,
    double? NominalPowerW,
    double? PpkWp,
    double? RsOhm,
    double? RpOhm,
    double? VocV,
    double? IscA,
    double? VpmaxV,
    double? IpmaxA,
    double? FfPercent,
    double? SweepDurationMs,
    double? IrradianceWM2,
    double? SensorTempC,
    double? ModuleTempC,
    string? IrradianceSensorType,
    string? IrradianceSensorSerial,
    string? ImportSource,
    string SyncStatus = "unsynced",
    string? Notes = null,
    IReadOnlyList<CurvePoint>? CurvePoints = null
);

public record MeasurementsResponse(IReadOnlyList<Measurement> Items);

// ---------------------------------------------------------------------------
// Sync
// ---------------------------------------------------------------------------

public record SyncUploadResult(int Uploaded, string? Error = null);
