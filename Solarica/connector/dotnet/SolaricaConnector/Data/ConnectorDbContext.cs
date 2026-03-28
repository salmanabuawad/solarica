using Microsoft.EntityFrameworkCore;

namespace SolaricaConnector.Data;

// ---------------------------------------------------------------------------
// EF Core entity classes
// ---------------------------------------------------------------------------

public class MeasurementEntity
{
    public string Id { get; set; } = string.Empty;
    public string? ExternalMeasurementKey { get; set; }
    public DateTime MeasuredAt { get; set; }
    public string? Customer { get; set; }
    public string? Installation { get; set; }
    public string? StringNo { get; set; }
    public string? ModuleType { get; set; }
    public string? ModuleReference { get; set; }
    public int? ModulesSeries { get; set; }
    public int? ModulesParallel { get; set; }
    public double? NominalPowerW { get; set; }
    public double? PpkWp { get; set; }
    public double? RsOhm { get; set; }
    public double? RpOhm { get; set; }
    public double? VocV { get; set; }
    public double? IscA { get; set; }
    public double? VpmaxV { get; set; }
    public double? IpmaxA { get; set; }
    public double? FfPercent { get; set; }
    public double? SweepDurationMs { get; set; }
    public double? IrradianceWM2 { get; set; }
    public double? SensorTempC { get; set; }
    public double? ModuleTempC { get; set; }
    public string? IrradianceSensorType { get; set; }
    public string? IrradianceSensorSerial { get; set; }
    public string? ImportSource { get; set; }
    public string SyncStatus { get; set; } = "unsynced";
    public string? Notes { get; set; }
    public string? RawPayloadJson { get; set; }

    public List<CurvePointEntity> CurvePoints { get; set; } = [];
}

public class CurvePointEntity
{
    public int Id { get; set; }
    public string MeasurementId { get; set; } = string.Empty;
    public int PointIndex { get; set; }
    public double VoltageV { get; set; }
    public double CurrentA { get; set; }
}

public class SyncStateEntity
{
    public string Key { get; set; } = string.Empty;
    public string Value { get; set; } = string.Empty;
}

// ---------------------------------------------------------------------------
// DbContext
// ---------------------------------------------------------------------------

public class ConnectorDbContext(DbContextOptions<ConnectorDbContext> options) : DbContext(options)
{
    public DbSet<MeasurementEntity> Measurements => Set<MeasurementEntity>();
    public DbSet<CurvePointEntity> CurvePoints => Set<CurvePointEntity>();
    public DbSet<SyncStateEntity> SyncState => Set<SyncStateEntity>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<MeasurementEntity>(e =>
        {
            e.HasKey(m => m.Id);
            e.HasMany(m => m.CurvePoints)
             .WithOne()
             .HasForeignKey(p => p.MeasurementId)
             .OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<CurvePointEntity>(e =>
        {
            e.HasKey(p => p.Id);
            e.HasIndex(p => new { p.MeasurementId, p.PointIndex });
        });

        modelBuilder.Entity<SyncStateEntity>(e =>
        {
            e.HasKey(s => s.Key);
        });
    }
}
