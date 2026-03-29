# Direct USB PVPM access

This refactor switches the Python connector default to direct USB / serial mode.

## How it works

1. Connect the PVPM to Windows via USB.
2. Start the Python connector.
3. Call:
   - `GET /api/device/ports`
   - `POST /api/device/auto-connect`
4. On the PVPM device, press **Transfer**.
5. Call `POST /api/import/start`.

The connector listens on the FTDI COM port and captures streamed `.SUI` files
directly from the device, then parses them into the canonical measurement schema.

## Limitations

- The device still has to be placed into **Transfer Mode** manually.
- This is direct USB access to the device stream, but it is not an interactive
  command protocol for writing data back into the PVPM.
- For write/control operations, the real PVPM command set still needs vendor
  documentation or protocol validation.

## Recommended env

```env
PVPM_DRIVER=serial
SERIAL_BAUD_RATE=115200
SERIAL_TIMEOUT_SECONDS=3
CONNECTOR_PORT=8765
```
