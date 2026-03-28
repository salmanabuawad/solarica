using System.Net.Http.Json;
using SolaricaConnector.Models;

namespace SolaricaConnector.Services;

public sealed class SyncService(
    MeasurementRepository repo,
    IHttpClientFactory httpClientFactory,
    IConfiguration config)
{
    public async Task<SyncUploadResult> UploadUnsyncedAsync(CancellationToken ct = default)
    {
        var all = await repo.ListAsync(ct);
        var unsynced = all.Where(m => m.SyncStatus != "synced").ToList();
        if (unsynced.Count == 0)
            return new SyncUploadResult(0);

        var backendUrl = config["BackendBaseUrl"]?.TrimEnd('/') ?? "http://localhost:8000";
        var url = $"{backendUrl}/api/import/batch";
        var payload = new
        {
            measurements = unsynced.Select(ToBackendPayload).ToList(),
            allow_duplicates = false,
        };

        try
        {
            var client = httpClientFactory.CreateClient();
            var response = await client.PostAsJsonAsync(url, payload, ct);
            response.EnsureSuccessStatusCode();
            await repo.MarkSyncedAsync(unsynced.Select(m => m.Id), ct);
            return new SyncUploadResult(unsynced.Count);
        }
        catch (Exception ex)
        {
            return new SyncUploadResult(0, ex.Message);
        }
    }

    private static object ToBackendPayload(Measurement m) => new
    {
        measured_at = m.MeasuredAt.ToString("o"),
        device_serial = m.ExternalMeasurementKey,
        sensor_serial = m.IrradianceSensorSerial,
        irradiance_sensor_serial = m.IrradianceSensorSerial,
        customer = m.Customer,
        module_type = m.ModuleType,
        remarks = m.Notes,
        ppk = m.PpkWp,
        rs = m.RsOhm,
        rp = m.RpOhm,
        voc = m.VocV,
        isc = m.IscA,
        vpmax = m.VpmaxV,
        ipmax = m.IpmaxA,
        pmax = m.PpkWp,
        fill_factor = m.FfPercent,
        ff = m.FfPercent,
        eeff = m.IrradianceWM2,
        tmod = m.ModuleTempC,
        tcell = m.SensorTempC,
        source_file = m.ImportSource,
        device_record_id = m.Id,
        sync_source = "solarica-connector-dotnet",
        iv_curve = (m.CurvePoints ?? [])
            .Select(p => new { voltage = p.VoltageV, current = p.CurrentA })
            .ToList(),
    };
}
