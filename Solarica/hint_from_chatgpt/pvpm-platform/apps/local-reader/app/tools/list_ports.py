import serial.tools.list_ports

for port in serial.tools.list_ports.comports():
    print(f"{port.device} - {port.description}")
