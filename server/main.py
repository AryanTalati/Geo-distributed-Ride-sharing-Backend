from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from coordinator import coordinator
from contextlib import asynccontextmanager
import time

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    coordinator.close_all_connections()

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def add_process_time_header(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - start) * 1000.0
    response.headers["X-Process-Time-ms"] = f"{process_time_ms:.2f}"
    return response

class RideCreate(BaseModel):
    user_id: str
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    driver_id: Optional[str] = None
    status: str = "requested"
    price: float = 0.0
    distance_km: float = 0.0
    duration_minutes: int = 0
    pickup_geohash: Optional[str] = None

class RideUpdate(BaseModel):
    driver_id: Optional[str] = None
    status: Optional[str] = None
    price: Optional[float] = None
    distance_km: Optional[float] = None
    duration_minutes: Optional[int] = None
    pickup_lat: Optional[float] = None
    pickup_lon: Optional[float] = None
    dropoff_lat: Optional[float] = None
    dropoff_lon: Optional[float] = None
    pickup_geohash: Optional[str] = None

class RideResponse(BaseModel):
    ride_id: str
    user_id: str
    driver_id: Optional[str]
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    region: str
    pickup_geohash: Optional[str]
    status: str
    price: float
    distance_km: float
    duration_minutes: int
    timestamp: str

@app.get("/")
def read_root():
    return {"message": "Ride-sharing api running..."}

@app.get("/rides")
def get_rides(region=None, user_id=None, driver_id=None, status=None, limit=100):
    rides = coordinator.get_rides(region=region, user_id=user_id, driver_id=driver_id, status=status, limit=limit)
    return rides

@app.get("/rides/{ride_id}")
def get_ride(ride_id):
    ride = coordinator.get_ride(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return ride

@app.post("/rides", status_code=201)
def create_ride(ride: RideCreate):
    result = coordinator.create_ride(
        user_id=ride.user_id,
        pickup_lat=ride.pickup_lat,
        pickup_lon=ride.pickup_lon,
        dropoff_lat=ride.dropoff_lat,
        dropoff_lon=ride.dropoff_lon,
        driver_id=ride.driver_id,
        status=ride.status,
        price=ride.price,
        distance_km=ride.distance_km,
        duration_minutes=ride.duration_minutes,
        pickup_geohash=ride.pickup_geohash
    )
    return result

@app.put("/rides/{ride_id}")
def update_ride(ride_id, ride: RideUpdate):
    update_data = ride.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    result = coordinator.update_ride(ride_id, **update_data)
    if not result:
        raise HTTPException(status_code=404, detail="Ride not found")
    return result

@app.delete("/rides/{ride_id}")
def delete_ride(ride_id):
    deleted = coordinator.delete_ride(ride_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ride not found")
    return {"message": "Ride deleted successfully", "ride_id": ride_id}

@app.get("/health/connections")
def get_connection_health():
    status = coordinator.get_connection_status()
    return {"regions": status}
