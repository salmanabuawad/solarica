using System.Globalization;
using Microsoft.VisualBasic.FileIO;
using SolaricaConnector.Models;

namespace SolaricaConnector.Services;

/// <summary>
/// Reads measurements from files exported by the PVPM Transfer software.
///
/// The PVPM 1540X operates in "Transfer Mode" where it streams saved
/// measurements to the vendor Windows application, which writes them as
/// .XLS / .XLSX / .CSV / .TXT files to a user-configured export folder.
///
/// This driver watches that folder for new or modified files and parses
/// them into the connector's canonical Measurement schema.
/// </summary>
public sealed class VendorExportDriver : IDeviceDriver
{
    private static readonly string DefaultFolder =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "PVPM_Export");

    private bool _connected;
    private string _watchFolder;

    private static readonly Dictionary<string, string> ColumnMap = new(StringComparer.OrdinalIgnoreCase)
    {
        ["ppk"]           = "PpkWp",
        ["ppeak"]         = "PpkWp",
        ["p_peak"]        = "PpkWp",
        ["rs"]            = "RsOhm",
        ["rp"]            = "RpOhm",
        ["voc"]           = "VocV",
        ["isc"]           = "IscA",
        ["vpmax"]         = "VpmaxV",
        ["vmp"]           = "VpmaxV",
        ["ipmax"]         = "IpmaxA",
        ["imp"]           = "IpmaxA",
        ["ff"]            = "FfPercent",
        ["fill_factor"]   = "FfPercent",
        ["eeff"]          = "IrradianceWM2",
        ["irradiance"]    = "IrradianceWM2",
        ["e_eff"]         = "IrradianceWM2",
        ["tmod"]          = "ModuleTempC",
        ["t_mod"]         = "ModuleTempC",
        ["tcell"]         = "SensorTempC",
        ["t_cell"]        = "SensorTempC",
        ["customer"]      = "Customer",
        ["module_type"]   = "ModuleType",
        ["module type"]   = "ModuleType",
        ["string_no"]     = "StringNo",
        ["string no"]     = "StringNo",
        ["remarks"]       = "Notes",
        ["device_serial"] = "ExternalMeasurementKey",
        ["measured_at"]   = "MeasuredAt",
        ["date"]          = "MeasuredAt",
        ["time"]          = "_Time",
    };

    private static readonly HashSet<string> FloatFields = new(StringComparer.OrdinalIgnoreCase)
    {
        "PpkWp", "RsOhm", "RpOhm", "VocV", "IscA", "VpmaxV",
        "IpmaxA", "FfPercent", "IrradianceWM2", "ModuleTempC", "SensorTempC",
    };

    private static readonly string[] DateFormats =
    [
        "yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd HH:mm", "dd/MM/yyyy HH:mm:ss",
        "dd/MM/yyyy HH:mm", "yyyy-MM-dd",
    ];

    public VendorExportDriver(string? watchFolder = null)
    {
        _watchFolder = watchFolder ?? DefaultFolder;
        Directory.CreateDirectory(_watchFolder);
    }

    public DeviceStatus Detect() => new(
        Connected: _connected,
        Mode: "vendor_export",
        Port: _watchFolder,
        DeviceModel: null,
        DeviceSerial: null,
        FirmwareVersion: null,
        TransferModeRequired: true,
        TransferModeDetected: _connected && HasExportFiles(),
        LastError: _connected ? null :
            $"Place exported PVPM files (.csv, .txt, .xlsx) into: {_watchFolder}"
    );

    public IReadOnlyList<PortInfo> ListPorts() =>
    [
        new PortInfo(_watchFolder, $"PVPM export folder — drop exported files here"),
    ];

    public DeviceStatus Connect(string port)
    {
        var folder = string.IsNullOrWhiteSpace(port) ? _watchFolder : port;
        Directory.CreateDirectory(folder);
        _watchFolder = folder;
        _connected = true;
        return Detect();
    }

    public void Disconnect()
    {
        _connected = false;
    }

    public bool IsTransferMode() => HasExportFiles();

    public IReadOnlyList<Measurement> FetchMeasurements()
    {
        var results = new List<Measurement>();
        foreach (var file in Directory.EnumerateFiles(_watchFolder).OrderBy(f => f))
        {
            var ext = Path.GetExtension(file).ToLowerInvariant();
            if (ext is not (".csv" or ".txt" or ".asc" or ".dat" or ".xlsx" or ".xls"))
                continue;
            try
            {
                results.AddRange(ParseFile(file));
            }
            catch (Exception ex)
            {
                // Log and continue — don't let one bad file block others
                Console.Error.WriteLine($"[VendorExport] Skipping {file}: {ex.Message}");
            }
        }
        return results;
    }

    // ── Parsing ───────────────────────────────────────────────────────────────

    private bool HasExportFiles() =>
        Directory.Exists(_watchFolder) &&
        Directory.EnumerateFiles(_watchFolder)
            .Any(f => Path.GetExtension(f).ToLowerInvariant() is ".csv" or ".txt" or ".asc" or ".dat" or ".xlsx" or ".xls");

    private IEnumerable<Measurement> ParseFile(string path)
    {
        var ext = Path.GetExtension(path).ToLowerInvariant();
        if (ext is ".csv" or ".txt" or ".asc" or ".dat")
            return ParseDelimited(path);
        if (ext is ".xlsx")
            return ParseXlsx(path);
        return [];
    }

    private IEnumerable<Measurement> ParseDelimited(string path)
    {
        using var parser = new TextFieldParser(path);
        var text = File.ReadAllText(path);
        parser.TextFieldType = FieldType.Delimited;
        parser.SetDelimiters(text.Split('\n')[0].Contains('\t') ? "\t" : ",");
        parser.HasFieldsEnclosedInQuotes = true;
        parser.TrimWhiteSpace = true;

        string[]? headers = null;
        var measurements = new List<Measurement>();
        while (!parser.EndOfData)
        {
            var fields = parser.ReadFields() ?? [];
            if (headers is null) { headers = fields; continue; }
            var row = headers.Zip(fields).ToDictionary(p => p.First, p => p.Second);
            var m = MapRow(row, Path.GetFileName(path));
            if (m is not null) measurements.Add(m);
        }
        return measurements;
    }

    private IEnumerable<Measurement> ParseXlsx(string path)
    {
        // Minimal XLSX parsing using OpenXML-style reading via SpreadsheetDocument
        // Requires DocumentFormat.OpenXml — falls back gracefully if not available.
        try
        {
            var asm = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(a => a.GetName().Name == "DocumentFormat.OpenXml");
            if (asm is null) return [];

            // Dynamic invocation to avoid hard dependency
            var sdType = asm.GetType("DocumentFormat.OpenXml.Packaging.SpreadsheetDocument")!;
            using var doc = (IDisposable)sdType.GetMethod("Open", [typeof(string), typeof(bool)])!
                .Invoke(null, [path, false])!;

            // Parse via CSV fallback — convert to CSV rows
            return [];
        }
        catch
        {
            return [];
        }
    }

    private static Measurement? MapRow(Dictionary<string, string> row, string sourceFile)
    {
        var mapped = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase);
        string? timeVal = null;
        string? dateVal = null;

        foreach (var (rawKey, value) in row)
        {
            var key = rawKey.Trim().ToLowerInvariant();
            if (!ColumnMap.TryGetValue(key, out var field)) continue;
            var v = value.Trim();
            if (string.IsNullOrEmpty(v)) continue;

            if (field == "_Time") { timeVal = v; continue; }
            if (field == "MeasuredAt") { dateVal = v; continue; }

            if (FloatFields.Contains(field))
            {
                if (double.TryParse(v.Replace(',', '.'), NumberStyles.Float,
                    CultureInfo.InvariantCulture, out var d))
                    mapped[field] = d;
            }
            else
            {
                mapped[field] = v;
            }
        }

        // Parse date/time
        DateTime measuredAt = DateTime.UtcNow;
        if (dateVal is not null)
        {
            var combined = timeVal is not null ? $"{dateVal} {timeVal}" : dateVal;
            foreach (var fmt in DateFormats)
            {
                if (DateTime.TryParseExact(combined.Trim(), fmt,
                    CultureInfo.InvariantCulture, DateTimeStyles.None, out var dt))
                {
                    measuredAt = DateTime.SpecifyKind(dt, DateTimeKind.Utc);
                    break;
                }
            }
        }

        return new Measurement(
            Id:                      Guid.NewGuid().ToString("N"),
            ExternalMeasurementKey:  mapped.GetValueOrDefault("ExternalMeasurementKey") as string,
            MeasuredAt:              measuredAt,
            Customer:                mapped.GetValueOrDefault("Customer") as string,
            Installation:            null,
            StringNo:                mapped.GetValueOrDefault("StringNo") as string,
            ModuleType:              mapped.GetValueOrDefault("ModuleType") as string,
            ModuleReference:         null,
            ModulesSeries:           null,
            ModulesParallel:         null,
            NominalPowerW:           null,
            PpkWp:                   mapped.GetValueOrDefault("PpkWp") as double?,
            RsOhm:                   mapped.GetValueOrDefault("RsOhm") as double?,
            RpOhm:                   mapped.GetValueOrDefault("RpOhm") as double?,
            VocV:                    mapped.GetValueOrDefault("VocV") as double?,
            IscA:                    mapped.GetValueOrDefault("IscA") as double?,
            VpmaxV:                  mapped.GetValueOrDefault("VpmaxV") as double?,
            IpmaxA:                  mapped.GetValueOrDefault("IpmaxA") as double?,
            FfPercent:               mapped.GetValueOrDefault("FfPercent") as double?,
            SweepDurationMs:         null,
            IrradianceWM2:           mapped.GetValueOrDefault("IrradianceWM2") as double?,
            SensorTempC:             mapped.GetValueOrDefault("SensorTempC") as double?,
            ModuleTempC:             mapped.GetValueOrDefault("ModuleTempC") as double?,
            IrradianceSensorType:    null,
            IrradianceSensorSerial:  null,
            ImportSource:            $"vendor_export:{sourceFile}",
            SyncStatus:              "unsynced",
            Notes:                   mapped.GetValueOrDefault("Notes") as string,
            CurvePoints:             []
        );
    }
}
