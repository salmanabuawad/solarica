using Microsoft.EntityFrameworkCore;
using SolaricaConnector.Data;
using SolaricaConnector.Models;

namespace SolaricaConnector.Services;

public sealed class MeasurementRepository(ConnectorDbContext db)
{
    public async Task UpsertAsync(Measurement m, CancellationToken ct = default)
    {
        var existing = await db.Measurements
            .Include(e => e.CurvePoints)
            .FirstOrDefaultAsync(e => e.Id == m.Id, ct);

        if (existing is null)
        {
            existing = new MeasurementEntity { Id = m.Id, MeasuredAt = m.MeasuredAt };
            db.Measurements.Add(existing);
        }

        MapToEntity(m, existing);
        db.CurvePoints.RemoveRange(existing.CurvePoints);
        existing.CurvePoints = (m.CurvePoints ?? [])
            .Select(p => new CurvePointEntity
            {
                MeasurementId = m.Id,
                PointIndex = p.PointIndex,
                VoltageV = p.VoltageV,
                CurrentA = p.CurrentA,
            })
            .ToList();

        await db.SaveChangesAsync(ct);
    }

    public async Task<IReadOnlyList<Measurement>> ListAsync(CancellationToken ct = default)
    {
        var rows = await db.Measurements
            .Include(e => e.CurvePoints.OrderBy(p => p.PointIndex))
            .OrderByDescending(e => e.MeasuredAt)
            .ToListAsync(ct);
        return rows.Select(ToModel).ToList();
    }

    public async Task<Measurement?> GetAsync(string id, CancellationToken ct = default)
    {
        var row = await db.Measurements
            .Include(e => e.CurvePoints.OrderBy(p => p.PointIndex))
            .FirstOrDefaultAsync(e => e.Id == id, ct);
        return row is null ? null : ToModel(row);
    }

    public async Task<int> CountUnsyncedAsync(CancellationToken ct = default) =>
        await db.Measurements.CountAsync(e => e.SyncStatus != "synced", ct);

    public async Task MarkSyncedAsync(IEnumerable<string> ids, CancellationToken ct = default)
    {
        var idSet = ids.ToHashSet();
        var rows = await db.Measurements
            .Where(e => idSet.Contains(e.Id))
            .ToListAsync(ct);
        foreach (var row in rows)
            row.SyncStatus = "synced";
        await db.SaveChangesAsync(ct);
    }

    public async Task<string> GetSyncStateAsync(string key, string defaultValue = "", CancellationToken ct = default)
    {
        var row = await db.SyncState.FindAsync([key], ct);
        return row?.Value ?? defaultValue;
    }

    public async Task SetSyncStateAsync(string key, string value, CancellationToken ct = default)
    {
        var row = await db.SyncState.FindAsync([key], ct);
        if (row is null)
        {
            db.SyncState.Add(new SyncStateEntity { Key = key, Value = value });
        }
        else
        {
            row.Value = value;
        }
        await db.SaveChangesAsync(ct);
    }

    // ---------------------------------------------------------------------------

    private static void MapToEntity(Measurement m, MeasurementEntity e)
    {
        e.ExternalMeasurementKey = m.ExternalMeasurementKey;
        e.MeasuredAt = m.MeasuredAt;
        e.Customer = m.Customer;
        e.Installation = m.Installation;
        e.StringNo = m.StringNo;
        e.ModuleType = m.ModuleType;
        e.ModuleReference = m.ModuleReference;
        e.ModulesSeries = m.ModulesSeries;
        e.ModulesParallel = m.ModulesParallel;
        e.NominalPowerW = m.NominalPowerW;
        e.PpkWp = m.PpkWp;
        e.RsOhm = m.RsOhm;
        e.RpOhm = m.RpOhm;
        e.VocV = m.VocV;
        e.IscA = m.IscA;
        e.VpmaxV = m.VpmaxV;
        e.IpmaxA = m.IpmaxA;
        e.FfPercent = m.FfPercent;
        e.SweepDurationMs = m.SweepDurationMs;
        e.IrradianceWM2 = m.IrradianceWM2;
        e.SensorTempC = m.SensorTempC;
        e.ModuleTempC = m.ModuleTempC;
        e.IrradianceSensorType = m.IrradianceSensorType;
        e.IrradianceSensorSerial = m.IrradianceSensorSerial;
        e.ImportSource = m.ImportSource;
        e.SyncStatus = m.SyncStatus;
        e.Notes = m.Notes;
    }

    private static Measurement ToModel(MeasurementEntity e) => new(
        Id: e.Id,
        ExternalMeasurementKey: e.ExternalMeasurementKey,
        MeasuredAt: e.MeasuredAt,
        Customer: e.Customer,
        Installation: e.Installation,
        StringNo: e.StringNo,
        ModuleType: e.ModuleType,
        ModuleReference: e.ModuleReference,
        ModulesSeries: e.ModulesSeries,
        ModulesParallel: e.ModulesParallel,
        NominalPowerW: e.NominalPowerW,
        PpkWp: e.PpkWp,
        RsOhm: e.RsOhm,
        RpOhm: e.RpOhm,
        VocV: e.VocV,
        IscA: e.IscA,
        VpmaxV: e.VpmaxV,
        IpmaxA: e.IpmaxA,
        FfPercent: e.FfPercent,
        SweepDurationMs: e.SweepDurationMs,
        IrradianceWM2: e.IrradianceWM2,
        SensorTempC: e.SensorTempC,
        ModuleTempC: e.ModuleTempC,
        IrradianceSensorType: e.IrradianceSensorType,
        IrradianceSensorSerial: e.IrradianceSensorSerial,
        ImportSource: e.ImportSource,
        SyncStatus: e.SyncStatus,
        Notes: e.Notes,
        CurvePoints: e.CurvePoints
            .OrderBy(p => p.PointIndex)
            .Select(p => new CurvePoint(p.PointIndex, p.VoltageV, p.CurrentA))
            .ToList()
    );
}
