import asyncio
import os

from contextlib import asynccontextmanager
from aiohttp import ClientSession
from dotenv import load_dotenv
from fastapi import FastAPI, Request

from airstageApi import ApiCloud
from airstageAC import AirstageAC, OperationMode, FanSpeed

from pydantic import BaseModel

load_dotenv()

USERNAME = os.environ.get("AIRSTAGE_USERNAME")
PASSWORD = os.environ.get("AIRSTAGE_PASSWORD")
COUNTRY = os.environ.get("AIRSTAGE_COUNTRY")


class DeviceSettings(BaseModel):
    mode: str
    fan: str
    temperature: float
    power: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.api = None
    app.state.device = None

    session = ClientSession()
    app.state.session = session

    try:
        print("AIRSTAGE: connecting...")

        api = ApiCloud(
            username=USERNAME,
            password=PASSWORD,
            country=COUNTRY,
            region="eu",
            session=session,
        )

        print("AIRSTAGE: requesting devices...")
        devices = await api.get_devices()

        if devices:
            dsn = next(iter(devices))

            print("AIRSTAGE: refreshing parameters...")
            device = AirstageAC(dsn, api)
            await device.refresh_parameters()

            app.state.api = api
            app.state.device = device

            print("AIRSTAGE initialized:", dsn)
        else:
            print("AIRSTAGE: no devices found")

    except Exception:
        import traceback
        traceback.print_exc()

    yield

    await session.close()
    print("AIRSTAGE API shutting down")


app = FastAPI(
    title="Airstage Mini API",
    description="Minimal FastAPI backend for Airstage AC devices",
    version="1.0.0",
    lifespan=lifespan,
    contact={
        "name": "Atanas Chebishev",
        "url": "https://chebishev.github.io/",
        "email": "atanas.chebishev@gmail.com",
    },
    license_info={
        "name": "MIT License",
        "identifier": "MIT",
    },
)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("favicon.ico")


@app.get("/")
def read_root():
    return {"message": "Airstage Mini API up and running"}


@app.get("/device/status")
async def get_device_status(request: Request):
    device = request.app.state.device

    await device.refresh_parameters()

    return {
        "status": "success",
        "data": {
            "power": device.get_device_on_off_state(),
            "temperature": device.get_target_temperature(),
            "operating_mode": device.get_operating_mode(),
            "fan_speed": device.get_fan_speed(),
        }
    }


@app.post("/device/settings")
async def set_device_settings(data: DeviceSettings, request: Request):
    device = request.app.state.device
    await device.refresh_parameters()

    results = {}

    # POWER
    device_status = device.get_device_on_off_state()

    if device_status is None:
        return {"status": "error", "message": "Cannot read device status"}

    if data.power != device_status:
        if data.power:
            await device.turn_on()
            results["power"] = "ON"
        else:
            await device.turn_off()
            results["power"] = "OFF"

    # Останалите настройки се променят само ако климатикът трябва да работи
    if data.power:

        current_mode = device.get_operating_mode()
        if current_mode != OperationMode[data.mode]:
            await device.set_operation_mode(OperationMode[data.mode])
            results["mode"] = data.mode

        current_fan = device.get_fan_speed()
        if current_fan != FanSpeed[data.fan]:
            await device.set_fan_speed(FanSpeed[data.fan])
            results["fan"] = data.fan

        current_temp = device.get_target_temperature()
        if current_temp != data.temperature:
            await device.set_target_temperature(data.temperature)
            results["temperature"] = data.temperature

    return {
        "status": "success",
        "updated": results
    }
    