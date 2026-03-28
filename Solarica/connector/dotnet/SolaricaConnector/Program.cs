// Solarica .NET Connector – ASP.NET Core Minimal API
// Exposes the same REST contract as the Python connector.
//
// Run:
//   dotnet run
//
// Install as Windows Service:
//   dotnet publish -r win-x64 -c Release --self-contained
//   sc create SolaricaConnector binPath="C:\path\to\solarica_connector.exe"
//   sc start SolaricaConnector

using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.EntityFrameworkCore;
using SolaricaConnector.Data;
using SolaricaConnector.Models;
using SolaricaConnector.Services;

const string ConnectorVersion = "1.0.0";

var builder = WebApplication.CreateBuilder(args);

// Windows Service support
builder.Host.UseWindowsService();

// JSON serialization – camelCase to match Python connector contract
builder.Services.ConfigureHttpJsonOptions(o =>
{
    o.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
    o.SerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    o.SerializerOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
});

// CORS – allow the Solarica web app to call from any localhost origin
builder.Services.AddCors(o =>
    o.AddDefaultPolicy(p => p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader())
);

// SQLite via EF Core
var dbPath = builder.Configuration["LocalDbPath"] ?? "./data/connector.db";
Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(dbPath))!);
builder.Services.AddDbContext<ConnectorDbContext>(o =>
    o.UseSqlite($"Data Source={dbPath}"));

// Services
builder.Services.AddScoped<MeasurementRepository>();
builder.Services.AddScoped<SyncService>();
builder.Services.AddHttpClient();

// Driver – selected by config key "PvpmDriver"
builder.Services.AddSingleton<IDeviceDriver>(_ =>
{
    var driver = builder.Configuration["PvpmDriver"] ?? "mock";
    return driver.ToLowerInvariant() switch
    {
        "serial" => (IDeviceDriver)new SerialDriver(),
        _ => new MockDriver(),
    };
});

var app = builder.Build();
app.UseCors();

// Ensure DB is created
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<ConnectorDbContext>();
    db.Database.EnsureCreated();
}

// ---------------------------------------------------------------------------
// Health / detection
// ---------------------------------------------------------------------------

app.MapGet("/health", () => new HealthResponse(Ok: true, Version: ConnectorVersion, Runtime: "dotnet"));

// ---------------------------------------------------------------------------
// Device
// ---------------------------------------------------------------------------

app.MapGet("/api/device/status", (IDeviceDriver driver) => driver.Detect());

app.MapGet("/api/device/ports", (IDeviceDriver driver) =>
    new PortsResponse(driver.ListPorts()));

app.MapPost("/api/device/connect", (ConnectRequest req, IDeviceDriver driver) =>
    driver.Connect(req.Port));

app.MapPost("/api/device/disconnect", (IDeviceDriver driver) =>
{
    driver.Disconnect();
    return Results.Ok(new { ok = true });
});

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

app.MapPost("/api/import/start", async (
    IDeviceDriver driver,
    MeasurementRepository repo,
    CancellationToken ct) =>
{
    try
    {
        var measurements = driver.FetchMeasurements();
        foreach (var m in measurements)
            await repo.UpsertAsync(m, ct);
        await repo.SetSyncStateAsync("import_state", "completed", ct);
        await repo.SetSyncStateAsync("last_imported_count", measurements.Count.ToString(), ct);
        return Results.Ok(new ImportStartResult(Ok: true, Imported: measurements.Count));
    }
    catch (NotImplementedException ex)
    {
        return Results.Problem(ex.Message, statusCode: 501);
    }
    catch (Exception ex)
    {
        return Results.Problem(ex.Message, statusCode: 500);
    }
});

app.MapGet("/api/import/status", async (MeasurementRepository repo, CancellationToken ct) =>
{
    var state = await repo.GetSyncStateAsync("import_state", "idle", ct);
    var lastCount = int.TryParse(
        await repo.GetSyncStateAsync("last_imported_count", "0", ct), out var n) ? n : 0;
    var unsynced = await repo.CountUnsyncedAsync(ct);
    return new ImportStatus(State: state, LastImportedCount: lastCount, UnsyncedCount: unsynced);
});

// ---------------------------------------------------------------------------
// Measurements (local cache)
// ---------------------------------------------------------------------------

app.MapGet("/api/measurements", async (MeasurementRepository repo, CancellationToken ct) =>
    new MeasurementsResponse(await repo.ListAsync(ct)));

app.MapGet("/api/measurements/{id}", async (string id, MeasurementRepository repo, CancellationToken ct) =>
{
    var m = await repo.GetAsync(id, ct);
    return m is null ? Results.NotFound(new { detail = "Measurement not found" }) : Results.Ok(m);
});

// ---------------------------------------------------------------------------
// Sync to cloud backend
// ---------------------------------------------------------------------------

app.MapPost("/api/sync/upload", async (SyncService sync, CancellationToken ct) =>
    await sync.UploadUnsyncedAsync(ct));

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

app.MapGet("/api/export/csv", async (MeasurementRepository repo, CancellationToken ct) =>
{
    var measurements = await repo.ListAsync(ct);
    var sb = new StringBuilder();
    sb.AppendLine("id,measuredAt,customer,installation,stringNo,moduleType,ppkWp,rsOhm,rpOhm," +
                  "vocV,iscA,vpmaxV,ipmaxA,ffPercent,irradianceWM2,moduleTempC,sensorTempC," +
                  "irradianceSensorType,irradianceSensorSerial,importSource,syncStatus");
    foreach (var m in measurements)
    {
        sb.AppendLine(string.Join(",",
            Csv(m.Id), Csv(m.MeasuredAt.ToString("o")), Csv(m.Customer), Csv(m.Installation),
            Csv(m.StringNo), Csv(m.ModuleType), m.PpkWp, m.RsOhm, m.RpOhm,
            m.VocV, m.IscA, m.VpmaxV, m.IpmaxA, m.FfPercent, m.IrradianceWM2,
            m.ModuleTempC, m.SensorTempC, Csv(m.IrradianceSensorType),
            Csv(m.IrradianceSensorSerial), Csv(m.ImportSource), Csv(m.SyncStatus)));
    }
    var bytes = Encoding.UTF8.GetBytes(sb.ToString());
    return Results.File(bytes, "text/csv", "measurements.csv");
});

app.MapGet("/api/export/json", async (MeasurementRepository repo, CancellationToken ct) =>
{
    var measurements = await repo.ListAsync(ct);
    var json = JsonSerializer.Serialize(measurements, new JsonSerializerOptions
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    });
    var bytes = Encoding.UTF8.GetBytes(json);
    return Results.File(bytes, "application/json", "measurements.json");
});

app.Run();

// ---------------------------------------------------------------------------

static string Csv(object? value)
{
    if (value is null) return "";
    var s = value.ToString() ?? "";
    return s.Contains(',') || s.Contains('"') ? $"\"{s.Replace("\"", "\"\"")}\"" : s;
}
