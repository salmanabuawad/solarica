using SolaricaConnector.Models;

namespace SolaricaConnector.Services;

/// <summary>
/// Common interface all device drivers must implement.
/// Mirrors the Python connector's PVPMDriver Protocol.
/// </summary>
public interface IDeviceDriver
{
    DeviceStatus Detect();
    IReadOnlyList<PortInfo> ListPorts();
    DeviceStatus Connect(string port);
    void Disconnect();
    bool IsTransferMode();
    IReadOnlyList<Measurement> FetchMeasurements();
}
