using System.IO.Ports;
using SolaricaConnector.Models;

namespace SolaricaConnector.Services;

/// <summary>
/// Reads measurements directly from a PVPM 1540X over a serial/USB-CDC port.
///
/// Note: The PVPM serial protocol is not yet reverse-engineered.
/// This driver correctly enumerates COM ports; FetchMeasurements() throws
/// NotImplementedException until the protocol is documented.
/// </summary>
public sealed class SerialDriver : IDeviceDriver
{
    private bool _connected;
    private string? _port;
    private string? _lastError;

    public DeviceStatus Detect() => new(
        Connected: _connected,
        Mode: "serial",
        Port: _port,
        DeviceModel: null,
        DeviceSerial: null,
        FirmwareVersion: null,
        TransferModeRequired: true,
        TransferModeDetected: false,
        LastError: _lastError
    );

    public IReadOnlyList<PortInfo> ListPorts() =>
        SerialPort.GetPortNames()
            .Select(name => new PortInfo(name, $"Serial port {name}"))
            .ToList();

    public DeviceStatus Connect(string port)
    {
        _connected = true;
        _port = port;
        _lastError =
            "Serial protocol not implemented. " +
            "Use the vendor_export driver to read exported files, " +
            "or capture serial traffic to implement this driver.";
        return Detect();
    }

    public void Disconnect()
    {
        _connected = false;
        _port = null;
        _lastError = null;
    }

    public bool IsTransferMode() => false;

    public IReadOnlyList<Measurement> FetchMeasurements() =>
        throw new NotImplementedException(
            "PVPM serial protocol is not yet implemented. " +
            "Use the VendorExportDriver instead."
        );
}
