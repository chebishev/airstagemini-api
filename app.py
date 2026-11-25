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
    async with ClientSession() as session:

        api = ApiCloud(
            username=USERNAME,
            password=PASSWORD,
            country=COUNTRY,
            region="eu",
            session=session,
        )

        devices = await api.get_devices()

        if not devices:
            raise RuntimeError("No AIRSTAGE devices found")

        dsn = next(iter(devices))

        device = AirstageAC(dsn, api)
        await device.refresh_parameters()

        # Запазваме обектите за всички endpoints
        app.state.api = api
        app.state.device = device

        print("AIRSTAGE initialized:", dsn)

        yield

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
async def get_device_info(request: Request):
    device = request.app.state.device

    await device.refresh_parameters()

    needed_parameters = ("iu_onoff", "iu_set_tmp", "iu_op_mode", "iu_fan_spd")

    device_parameters = {
        parameter: device._lastGoodValue[parameter]
        for parameter in needed_parameters
        if parameter in device._lastGoodValue
    }

    return device_parameters


@app.get("/device/temperature")
async def get_temperature(request: Request):
    device = request.app.state.device
    return device.get_target_temperature()


@app.get("/device/operating_mode")
async def get_operating_mode(request: Request):
    device = request.app.state.device
    return device.get_operating_mode()


@app.get("/device/fan_speed")
async def get_fan_speed(request: Request):
    device = request.app.state.device
    return device.get_fan_speed()


@app.post("/device/switch_on")
async def switch_on_device(request: Request):
    device = request.app.state.device

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

    device_status = device.get_device_on_off_state()

    if device_status is None:
        return {"status": "error", "message": "Cannot read device status"}

    if not device_status:
        return {"status": "already_off"}

    await device.turn_off()

    return {"status": "success", "action": "switch_off"}
