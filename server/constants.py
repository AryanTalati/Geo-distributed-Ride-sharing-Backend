import os
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv('ENVIRONMENT', 'local').lower()
if ENVIRONMENT not in ['local', 'cloud']:
    ENVIRONMENT = 'local'

REGION_CONFIGS = {
    'us-east': {
        'host': os.getenv('US_EAST_HOST', 'localhost'),
        'port': int(os.getenv('US_EAST_PORT', '26201')),
        'database': os.getenv('DATABASE_NAME', 'rideshare'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', '')
    },
    'us-west': {
        'host': os.getenv('US_WEST_HOST', 'localhost'),
        'port': int(os.getenv('US_WEST_PORT', '26204')),
        'database': os.getenv('DATABASE_NAME', 'rideshare'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', '')
    },
    'eu-central': {
        'host': os.getenv('EU_CENTRAL_HOST', 'localhost'),
        'port': int(os.getenv('EU_CENTRAL_PORT', '26207')),
        'database': os.getenv('DATABASE_NAME', 'rideshare'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', '')
    },
    'ap-south': {
        'host': os.getenv('AP_SOUTH_HOST', 'localhost'),
        'port': int(os.getenv('AP_SOUTH_PORT', '26210')),
        'database': os.getenv('DATABASE_NAME', 'rideshare'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', '')
    }
}

REGION_BOUNDS = {
    'us-east': {
        'lat_min': 25.0, 'lat_max': 45.0,
        'lon_min': -80.0, 'lon_max': -65.0
    },
    'us-west': {
        'lat_min': 30.0, 'lat_max': 50.0,
        'lon_min': -125.0, 'lon_max': -110.0
    },
    'eu-central': {
        'lat_min': 45.0, 'lat_max': 55.0,
        'lon_min': 5.0, 'lon_max': 15.0
    },
    'ap-south': {
        'lat_min': 10.0, 'lat_max': 25.0,
        'lon_min': 70.0, 'lon_max': 90.0
    }
}

