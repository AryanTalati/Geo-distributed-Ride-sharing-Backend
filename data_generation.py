import uuid
import random
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

import pandas as pd
import numpy as np
from faker import Faker
from server.constants import ENVIRONMENT

USERS_PER_REGION_LOCAL = 250
DRIVERS_PER_REGION_LOCAL = 100
RIDES_PER_REGION_LOCAL = 500

USERS_PER_REGION_CLOUD = 30000
DRIVERS_PER_REGION_CLOUD = 5000
RIDES_PER_REGION_CLOUD = 50000

USERS_PER_REGION = USERS_PER_REGION_CLOUD if ENVIRONMENT == 'cloud' else USERS_PER_REGION_LOCAL
DRIVERS_PER_REGION = DRIVERS_PER_REGION_CLOUD if ENVIRONMENT == 'cloud' else DRIVERS_PER_REGION_LOCAL
RIDES_PER_REGION = RIDES_PER_REGION_CLOUD if ENVIRONMENT == 'cloud' else RIDES_PER_REGION_LOCAL

random.seed(42)
np.random.seed(42)


# REGION CONFIGURATION
class Region(Enum):
    """Geographic regions for data partitioning."""
    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_CENTRAL = "eu-central"
    AP_SOUTH = "ap-south"


# Region boundaries (latitude, longitude ranges)
REGION_BOUNDS = {
    Region.US_EAST: {
        'lat_min': 25.0, 'lat_max': 45.0,
        'lon_min': -80.0, 'lon_max': -65.0,
        'name': 'US East Coast'
    },
    Region.US_WEST: {
        'lat_min': 30.0, 'lat_max': 50.0,
        'lon_min': -125.0, 'lon_max': -110.0,
        'name': 'US West Coast'
    },
    Region.EU_CENTRAL: {
        'lat_min': 45.0, 'lat_max': 55.0,
        'lon_min': 5.0, 'lon_max': 15.0,
        'name': 'Central Europe'
    },
    Region.AP_SOUTH: {
        'lat_min': 10.0, 'lat_max': 25.0,
        'lon_min': 70.0, 'lon_max': 90.0,
        'name': 'South Asia'
    }
}


# Major cities in each region
CITIES = {
    Region.US_EAST: [
        ('New York', 40.7128, -74.0060),
        ('Boston', 42.3601, -71.0589),
        ('Miami', 25.7617, -80.1918),
        ('Philadelphia', 39.9526, -75.1652),
        ('Washington DC', 38.9072, -77.0369),
    ],
    Region.US_WEST: [
        ('Los Angeles', 34.0522, -118.2437),
        ('San Francisco', 37.7749, -122.4194),
        ('Seattle', 47.6062, -122.3321),
        ('San Diego', 32.7157, -117.1611),
        ('Portland', 45.5152, -122.6784),
    ],
    Region.EU_CENTRAL: [
        ('Berlin', 52.5200, 13.4050),
        ('Munich', 48.1351, 11.5820),
        ('Frankfurt', 50.1109, 8.6821),
        ('Zurich', 47.3769, 8.5417),
        ('Vienna', 48.2082, 16.3738),
    ],
    Region.AP_SOUTH: [
        ('Mumbai', 19.0760, 72.8777),
        ('Delhi', 28.6139, 77.2090),
        ('Bangalore', 12.9716, 77.5946),
        ('Chennai', 13.0827, 80.2707),
        ('Kolkata', 22.5726, 88.3639),
    ]
}


# DATA MODELS (4 SCHEMAS)
@dataclass
class User:
    """User entity for the ride-sharing system."""
    user_id: str
    name: str
    email: str
    phone: str
    latitude: float
    longitude: float
    region: str
    rating: float = 5.0
    total_rides: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Driver:
    """Driver entity for the ride-sharing system."""
    driver_id: str
    name: str
    email: str
    phone: str
    latitude: float
    longitude: float
    region: str
    geohash: str
    vehicle_info: str
    license_plate: str
    availability: str = 'offline'
    rating: float = 5.0
    total_rides: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Ride:
    """Ride entity for the ride-sharing system."""
    ride_id: str
    user_id: str
    driver_id: Optional[str]
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    region: str
    pickup_geohash: str
    status: str = 'requested'
    price: float = 0.0
    distance_km: float = 0.0
    duration_minutes: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RegionInfo:
    """Region entity for the ride-sharing system - the 4th schema."""
    region_id: str
    region_code: str
    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    node_count: int = 3
    primary_node: str = ""
    created_at: datetime = field(default_factory=datetime.now)


# Create the 4 region records
REGION_RECORDS = {
    Region.US_EAST: RegionInfo(
        region_id=str(uuid.uuid4()),
        region_code="us-east",
        name="US East Coast",
        lat_min=25.0, lat_max=45.0,
        lon_min=-80.0, lon_max=-65.0,
        primary_node="us-east-primary"
    ),
    Region.US_WEST: RegionInfo(
        region_id=str(uuid.uuid4()),
        region_code="us-west",
        name="US West Coast",
        lat_min=30.0, lat_max=50.0,
        lon_min=-125.0, lon_max=-110.0,
        primary_node="us-west-primary"
    ),
    Region.EU_CENTRAL: RegionInfo(
        region_id=str(uuid.uuid4()),
        region_code="eu-central",
        name="Central Europe",
        lat_min=45.0, lat_max=55.0,
        lon_min=5.0, lon_max=15.0,
        primary_node="eu-central-primary"
    ),
    Region.AP_SOUTH: RegionInfo(
        region_id=str(uuid.uuid4()),
        region_code="ap-south",
        name="South Asia",
        lat_min=10.0, lat_max=25.0,
        lon_min=70.0, lon_max=90.0,
        primary_node="ap-south-primary"
    ),
}


# GEOHASH IMPLEMENTATION
class GeoHasher:
    """
    Custom geohash implementation for geographic coordinate encoding.
    
    Geohashing converts (lat, lon) into a string where:
    - Nearby locations share common prefixes
    - Longer strings = more precision
    
    Precision levels:
    - 4 chars: ~39 km (good for regional queries)
    - 6 chars: ~1.2 km (good for nearby driver search)
    - 8 chars: ~38 meters
    """
    
    BASE32_ALPHABET = '0123456789bcdefghjkmnpqrstuvwxyz'
    DECODE_MAP = {char: i for i, char in enumerate(BASE32_ALPHABET)}
    
    def __init__(self, precision: int = 6):
        self.precision = precision
    
    def encode(self, latitude: float, longitude: float) -> str:
        """Encode latitude/longitude into a geohash string."""
        lat_range = (-90.0, 90.0)
        lon_range = (-180.0, 180.0)
        
        geohash = []
        bits = 0
        current_char = 0
        is_longitude = True
        
        while len(geohash) < self.precision:
            if is_longitude:
                mid = (lon_range[0] + lon_range[1]) / 2
                if longitude >= mid:
                    current_char = (current_char << 1) | 1
                    lon_range = (mid, lon_range[1])
                else:
                    current_char = current_char << 1
                    lon_range = (lon_range[0], mid)
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if latitude >= mid:
                    current_char = (current_char << 1) | 1
                    lat_range = (mid, lat_range[1])
                else:
                    current_char = current_char << 1
                    lat_range = (lat_range[0], mid)
            
            is_longitude = not is_longitude
            bits += 1
            
            if bits == 5:
                geohash.append(self.BASE32_ALPHABET[current_char])
                bits = 0
                current_char = 0
        
        return ''.join(geohash)
    
    def decode(self, geohash: str) -> Tuple[float, float]:
        """Decode a geohash string back to (latitude, longitude)."""
        lat_range = (-90.0, 90.0)
        lon_range = (-180.0, 180.0)
        is_longitude = True
        
        for char in geohash:
            value = self.DECODE_MAP[char]
            for i in range(4, -1, -1):
                bit = (value >> i) & 1
                if is_longitude:
                    mid = (lon_range[0] + lon_range[1]) / 2
                    if bit:
                        lon_range = (mid, lon_range[1])
                    else:
                        lon_range = (lon_range[0], mid)
                else:
                    mid = (lat_range[0] + lat_range[1]) / 2
                    if bit:
                        lat_range = (mid, lat_range[1])
                    else:
                        lat_range = (lat_range[0], mid)
                is_longitude = not is_longitude
        
        latitude = (lat_range[0] + lat_range[1]) / 2
        longitude = (lon_range[0] + lon_range[1]) / 2
        return latitude, longitude
    
    def get_neighbors(self, geohash: str) -> Dict[str, str]:
        """Get the 8 neighboring geohash cells."""
        lat, lon = self.decode(geohash)
        lat_delta = 180.0 / (2 ** (len(geohash) * 5 // 2))
        lon_delta = 360.0 / (2 ** (len(geohash) * 5 // 2))
        
        return {
            'n': self.encode(lat + lat_delta, lon),
            's': self.encode(lat - lat_delta, lon),
            'e': self.encode(lat, lon + lon_delta),
            'w': self.encode(lat, lon - lon_delta),
            'ne': self.encode(lat + lat_delta, lon + lon_delta),
            'nw': self.encode(lat + lat_delta, lon - lon_delta),
            'se': self.encode(lat - lat_delta, lon + lon_delta),
            'sw': self.encode(lat - lat_delta, lon - lon_delta),
        }


# DATA GENERATOR
class RideshareDataGenerator:
    """Generates realistic synthetic data for the ride-sharing system."""
    
    def __init__(self, seed: int = 42):
        self.fake = Faker()
        Faker.seed(seed)
        random.seed(seed)
        
        self.vehicle_types = ['Sedan', 'SUV', 'Hatchback', 'Minivan', 'Compact']
        self.vehicle_brands = ['Toyota', 'Honda', 'Ford', 'BMW', 'Mercedes', 'Hyundai', 'Volkswagen']
        self.colors = ['Black', 'White', 'Silver', 'Blue', 'Red', 'Gray']
    
    def _get_random_location_near_city(self, region: Region) -> Tuple[float, float, str]:
        city_name, base_lat, base_lon = random.choice(CITIES[region])
        lat = base_lat + random.uniform(-0.1, 0.1)
        lon = base_lon + random.uniform(-0.1, 0.1)
        return lat, lon, city_name
    
    def generate_user(self, region: Region) -> User:
        lat, lon, city = self._get_random_location_near_city(region)
        return User(
            user_id=str(uuid.uuid4()),
            name=self.fake.name(),
            email=self.fake.email(),
            phone=self.fake.phone_number(),
            latitude=round(lat, 6),
            longitude=round(lon, 6),
            region=region.value,
            rating=round(random.uniform(3.5, 5.0), 2),
            total_rides=random.randint(0, 100)
        )
    
    def generate_driver(self, region: Region, geohash_func) -> Driver:
        lat, lon, city = self._get_random_location_near_city(region)
        geohash = geohash_func(lat, lon)
        vehicle = f"{random.choice(self.colors)} {random.choice(self.vehicle_brands)} {random.choice(self.vehicle_types)}"
        
        if region in [Region.US_EAST, Region.US_WEST]:
            plate = f"{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()}-{random.randint(1000, 9999)}"
        elif region == Region.EU_CENTRAL:
            plate = f"{self.fake.random_uppercase_letter()}-{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()} {random.randint(100, 9999)}"
        else:
            plate = f"MH{random.randint(10, 99)}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()}{random.randint(1000, 9999)}"
        
        return Driver(
            driver_id=str(uuid.uuid4()),
            name=self.fake.name(),
            email=self.fake.email(),
            phone=self.fake.phone_number(),
            latitude=round(lat, 6),
            longitude=round(lon, 6),
            region=region.value,
            geohash=geohash,
            vehicle_info=vehicle,
            license_plate=plate,
            availability=random.choice(['online', 'offline', 'on_ride']),
            rating=round(random.uniform(4.0, 5.0), 2),
            total_rides=random.randint(0, 500)
        )
    
    def _haversine(self, lat1, lon1, lat2, lon2) -> float:
        from math import radians, sin, cos, sqrt, atan2
        R = 6371
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    
    def generate_ride(self, user: User, driver: Optional[Driver], geohash_func) -> Ride:
        pickup_lat = user.latitude + random.uniform(-0.01, 0.01)
        pickup_lon = user.longitude + random.uniform(-0.01, 0.01)
        dropoff_lat = user.latitude + random.uniform(-0.05, 0.05)
        dropoff_lon = user.longitude + random.uniform(-0.05, 0.05)
        
        distance = self._haversine(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)
        duration = int(distance * 3 + random.randint(5, 15))
        price = round(2.5 + distance * 1.5 + duration * 0.2, 2)
        
        status_weights = {'completed': 0.80, 'cancelled': 0.10, 'in_progress': 0.05, 'requested': 0.05}
        status = random.choices(list(status_weights.keys()), list(status_weights.values()))[0]
        
        return Ride(
            ride_id=str(uuid.uuid4()),
            user_id=user.user_id,
            driver_id=driver.driver_id if driver and status != 'requested' else None,
            pickup_lat=round(pickup_lat, 6),
            pickup_lon=round(pickup_lon, 6),
            dropoff_lat=round(dropoff_lat, 6),
            dropoff_lon=round(dropoff_lon, 6),
            region=user.region,
            pickup_geohash=geohash_func(pickup_lat, pickup_lon),
            status=status,
            price=price if status == 'completed' else 0,
            distance_km=round(distance, 2),
            duration_minutes=duration,
            timestamp=self.fake.date_time_between(start_date='-30d', end_date='now')
        )
    
    def generate_dataset(self, users_per_region: int = 250, 
                         drivers_per_region: int = 100,
                         rides_per_region: int = 500,
                         geohash_func=None) -> Dict:
        
        if geohash_func is None:
            geohash_func = lambda lat, lon: f"placeholder_{lat:.2f}_{lon:.2f}"
        
        data = {'users': [], 'drivers': [], 'rides': []}
        
        for region in Region:
            print(f"  Generating data for {region.value}...")
            
            region_users = [self.generate_user(region) for _ in range(users_per_region)]
            data['users'].extend(region_users)
            
            region_drivers = [self.generate_driver(region, geohash_func) for _ in range(drivers_per_region)]
            data['drivers'].extend(region_drivers)
            
            for _ in range(rides_per_region):
                user = random.choice(region_users)
                driver = random.choice(region_drivers) if region_drivers else None
                ride = self.generate_ride(user, driver, geohash_func)
                data['rides'].append(ride)
        
        return data


# MAIN EXECUTION
def main():
    
    print("=" * 70)
    print("GEO-DISTRIBUTED RIDE-SHARING DATABASE SYSTEM")
    print("Data Generation Script")
    print(f"Environment: {ENVIRONMENT.upper()}")
    print("=" * 70)
    
    # Initialize GeoHasher
    hasher = GeoHasher(precision=6)
    print("\n✓ GeoHasher initialized")
    
    # Show geohash examples
    print("\n📍 Geohash Examples:")
    print(f"   New York (40.7128, -74.0060) → {hasher.encode(40.7128, -74.0060)}")
    print(f"   Los Angeles (34.0522, -118.2437) → {hasher.encode(34.0522, -118.2437)}")
    print(f"   Berlin (52.5200, 13.4050) → {hasher.encode(52.5200, 13.4050)}")
    print(f"   Mumbai (19.0760, 72.8777) → {hasher.encode(19.0760, 72.8777)}")
    
    # Generate data
    print("\n" + "=" * 70)
    print("GENERATING SYNTHETIC DATA")
    print("=" * 70)
    
    generator = RideshareDataGenerator(seed=42)
    dataset = generator.generate_dataset(
        users_per_region=USERS_PER_REGION,
        drivers_per_region=DRIVERS_PER_REGION,
        rides_per_region=RIDES_PER_REGION,
        geohash_func=hasher.encode
    )
    
    print(f"\n✅ Dataset Generated Successfully!")
    print(f"   Total Users: {len(dataset['users'])}")
    print(f"   Total Drivers: {len(dataset['drivers'])}")
    print(f"   Total Rides: {len(dataset['rides'])}")
    print(f"   Total Regions: {len(REGION_RECORDS)}")
    
    # Show sample data
    print("\n" + "=" * 70)
    print("SAMPLE DATA")
    print("=" * 70)
    
    print("\n📊 Sample User:")
    sample_user = dataset['users'][0]
    print(f"   Name: {sample_user.name}")
    print(f"   Email: {sample_user.email}")
    print(f"   Region: {sample_user.region}")
    print(f"   Location: ({sample_user.latitude}, {sample_user.longitude})")
    print(f"   Rating: {sample_user.rating}")
    
    print("\n📊 Sample Driver:")
    sample_driver = dataset['drivers'][0]
    print(f"   Name: {sample_driver.name}")
    print(f"   Vehicle: {sample_driver.vehicle_info}")
    print(f"   License Plate: {sample_driver.license_plate}")
    print(f"   Geohash: {sample_driver.geohash}")
    print(f"   Availability: {sample_driver.availability}")
    
    print("\n📊 Sample Ride:")
    sample_ride = dataset['rides'][0]
    print(f"   Ride ID: {sample_ride.ride_id[:8]}...")
    print(f"   Status: {sample_ride.status}")
    print(f"   Distance: {sample_ride.distance_km} km")
    print(f"   Duration: {sample_ride.duration_minutes} minutes")
    print(f"   Price: ${sample_ride.price}")
    
    print("\n📊 Sample Region:")
    sample_region = REGION_RECORDS[Region.US_EAST]
    print(f"   Region ID: {sample_region.region_id[:8]}...")
    print(f"   Code: {sample_region.region_code}")
    print(f"   Name: {sample_region.name}")
    print(f"   Bounds: Lat [{sample_region.lat_min}, {sample_region.lat_max}]")
    print(f"   Primary Node: {sample_region.primary_node}")
    
    # Data distribution
    print("\n" + "=" * 70)
    print("DATA DISTRIBUTION BY REGION")
    print("=" * 70)
    
    for region in Region:
        user_count = len([u for u in dataset['users'] if u.region == region.value])
        driver_count = len([d for d in dataset['drivers'] if d.region == region.value])
        ride_count = len([r for r in dataset['rides'] if r.region == region.value])
        print(f"\n   {region.value.upper()} ({REGION_BOUNDS[region]['name']})")
        print(f"      Users: {user_count}")
        print(f"      Drivers: {driver_count}")
        print(f"      Rides: {ride_count}")
    
    # Export to CSV files
    print("\n" + "=" * 70)
    print("EXPORTING DATA TO CSV FILES")
    print("=" * 70)
    
    output_dir = "generated_data"
    os.makedirs(output_dir, exist_ok=True)
    
    # Convert to DataFrames
    users_df = pd.DataFrame([vars(u) for u in dataset['users']])
    drivers_df = pd.DataFrame([vars(d) for d in dataset['drivers']])
    rides_df = pd.DataFrame([vars(r) for r in dataset['rides']])
    regions_df = pd.DataFrame([vars(r) for r in REGION_RECORDS.values()])
    
    # Save to CSV
    users_df.to_csv(f"{output_dir}/users.csv", index=False)
    drivers_df.to_csv(f"{output_dir}/drivers.csv", index=False)
    rides_df.to_csv(f"{output_dir}/rides.csv", index=False)
    regions_df.to_csv(f"{output_dir}/regions.csv", index=False)
    
    print(f"\n✅ Data exported to '{output_dir}/' directory:")
    print(f"   • users.csv    ({len(users_df)} records)")
    print(f"   • drivers.csv  ({len(drivers_df)} records)")
    print(f"   • rides.csv    ({len(rides_df)} records)")
    print(f"   • regions.csv  ({len(regions_df)} records)")
    
    print("\n" + "=" * 70)
    print("✅ DATA GENERATION COMPLETE!")
    print("=" * 70)
    
    # Return dataset for use if imported as module
    return dataset, REGION_RECORDS


if __name__ == "__main__":
    main()