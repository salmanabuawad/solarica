from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .driver_factory import get_driver
from .schemas import PortsResponse, DeviceStatus, ConnectRequest, MeasurementsResponse, ImportStatus
from .repository import list_measurements, get_measurement
from .services import seed_from_driver, get_import_status, upload_unsynced

app = FastAPI(title='PVPM Local Reader', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.get('/health')
def health():
    return {'ok': True}

@app.get('/api/device/status', response_model=DeviceStatus)
def device_status():
    return get_driver().detect()

@app.get('/api/device/ports', response_model=PortsResponse)
def device_ports():
    return {'items': get_driver().list_ports()}

@app.post('/api/device/connect', response_model=DeviceStatus)
def device_connect(payload: ConnectRequest):
    return get_driver().connect(payload.port)

@app.post('/api/device/disconnect')
def device_disconnect():
    get_driver().disconnect()
    return {'ok': True}

@app.get('/api/measurements', response_model=MeasurementsResponse)
def measurements():
    return {'items': list_measurements()}

@app.get('/api/measurements/{measurement_id}')
def measurement_details(measurement_id: str):
    item = get_measurement(measurement_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Measurement not found')
    return item

@app.post('/api/import/start')
def import_start():
    count = seed_from_driver()
    return {'ok': True, 'imported': count}

@app.get('/api/import/status', response_model=ImportStatus)
def import_status():
    return get_import_status()

@app.post('/api/sync/upload')
def sync_upload():
    return upload_unsynced()
