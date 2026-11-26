import asyncio
import os

from contextlib import asynccontextmanager
from aiohttp import ClientSession
from dotenv import load_dotenv
from fastapi import FastAPI, Request

from airstageApi import ApiCloud
from airstageAC import AirstageAC, FanSpeed

load_dotenv()

USERNAME = os.environ.get("AIRSTAGE_USERNAME")
PASSWORD = os.environ.get("AIRSTAGE_PASSWORD")
COUNTRY = os.environ.get("AIRSTAGE_COUNTRY")


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


@app.get("/")
def read_root():
    return {"message": "Airstage Mini API up and running"}


@app.get("/device_info")
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


@app.get("/device/temperature")
async def get_temperature(request: Request):
    device = request.app.state.device
    await device.refresh_parameters()
    return device.get_target_temperature()


@app.get("/device/operating_mode")
async def get_operating_mode(request: Request):
    device = request.app.state.device
    await device.refresh_parameters()
    result = device.get_operating_mode()

    print("OPERATING MODE:", repr(result), type(result))

    return result.value if result is not None else None


@app.get("/device/fan_speed")
async def get_fan_speed(request: Request):
    device = request.app.state.device
    await device.refresh_parameters()
    return device.get_fan_speed()


@app.post("/device/switch_on")
async def switch_on_device(request: Request):
    device = request.app.state.device
    await device.refresh_parameters()

    device_status = device.get_device_on_off_state()

    if device_status is None:
        return {"status": "error", "message": "Cannot read device status"}

    if device_status:
        return {"status": "already_on"}

    await device.turn_on()

    return {"status": "success", "action": "switch_on"}


@app.post("/device/switch_off")
async def switch_off_device(request: Request):
    device = request.app.state.device
    await device.refresh_parameters()

    device_status = device.get_device_on_off_state()

    if device_status is None:
        return {"status": "error", "message": "Cannot read device status"}

    if not device_status:
        return {"status": "already_off"}

    await device.turn_off()

    return {"status": "success", "action": "switch_off"}
