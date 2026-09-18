import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
import sys
from datetime import datetime
from server.constants import REGION_CONFIGS, ENVIRONMENT

def get_connection(region):
    config = REGION_CONFIGS[region]
    conn = psycopg2.connect(
        host=config['host'],
        port=config['port'],
        dbname=config['database'],
        user=config['user'],
        password=config['password']
    )
    return conn

def setup_database_regions(conn):
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER DATABASE rideshare SET PRIMARY REGION 'us-east'")
        conn.commit()
    except Exception as e:
        conn.rollback()
        if "already set" in str(e).lower() or "already exists" in str(e).lower():
            pass
        else:
            print(f"   ⚠ Warning setting primary region: {e}")
    
    regions_to_add = ['us-west', 'eu-central', 'ap-south']
    for region in regions_to_add:
        try:
            cursor.execute(f"ALTER DATABASE rideshare ADD REGION '{region}'")
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "already added" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                print(f"   ⚠ Warning adding region {region}: {e}")
    
    print("   ✓ Database regions configured")
    cursor.close()

def create_tables(conn):
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regions (
                region_id UUID PRIMARY KEY,
                region_code VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                lat_min FLOAT NOT NULL,
                lat_max FLOAT NOT NULL,
                lon_min FLOAT NOT NULL,
                lon_max FLOAT NOT NULL,
                node_count INT DEFAULT 3,
                primary_node VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"   ⚠ Warning creating regions table: {e}")
    
    for table_name in ['users', 'drivers', 'rides']:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            conn.commit()
        except Exception as e:
            conn.rollback()
    
    try:
        cursor.execute("""
            CREATE TABLE users (
                user_id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(50),
                latitude FLOAT NOT NULL,
                longitude FLOAT NOT NULL,
                region VARCHAR(50) NOT NULL,
                rating FLOAT DEFAULT 5.0,
                total_rides INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                crdb_region crdb_internal_region AS (
                    CASE region
                        WHEN 'us-east' THEN 'us-east'::crdb_internal_region
                        WHEN 'us-west' THEN 'us-west'::crdb_internal_region
                        WHEN 'eu-central' THEN 'eu-central'::crdb_internal_region
                        WHEN 'ap-south' THEN 'ap-south'::crdb_internal_region
                        ELSE 'us-east'::crdb_internal_region
                    END
                ) STORED NOT NULL
            ) LOCALITY REGIONAL BY ROW
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Failed to create users table: {e}")
    
    try:
        cursor.execute("""
            CREATE TABLE drivers (
                driver_id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(50),
                latitude FLOAT NOT NULL,
                longitude FLOAT NOT NULL,
                region VARCHAR(50) NOT NULL,
                geohash VARCHAR(50),
                vehicle_info VARCHAR(255),
                license_plate VARCHAR(50),
                availability VARCHAR(50) DEFAULT 'offline',
                rating FLOAT DEFAULT 5.0,
                total_rides INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                crdb_region crdb_internal_region AS (
                    CASE region
                        WHEN 'us-east' THEN 'us-east'::crdb_internal_region
                        WHEN 'us-west' THEN 'us-west'::crdb_internal_region
                        WHEN 'eu-central' THEN 'eu-central'::crdb_internal_region
                        WHEN 'ap-south' THEN 'ap-south'::crdb_internal_region
                        ELSE 'us-east'::crdb_internal_region
                    END
                ) STORED NOT NULL
            ) LOCALITY REGIONAL BY ROW
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Failed to create drivers table: {e}")
    
    try:
        cursor.execute("""
            CREATE TABLE rides (
                ride_id UUID PRIMARY KEY,
                user_id UUID NOT NULL,
                driver_id UUID,
                pickup_lat FLOAT NOT NULL,
                pickup_lon FLOAT NOT NULL,
                dropoff_lat FLOAT NOT NULL,
                dropoff_lon FLOAT NOT NULL,
                region VARCHAR(50) NOT NULL,
                pickup_geohash VARCHAR(50),
                status VARCHAR(50) DEFAULT 'requested',
                price FLOAT DEFAULT 0.0,
                distance_km FLOAT DEFAULT 0.0,
                duration_minutes INT DEFAULT 0,
                timestamp TIMESTAMP DEFAULT NOW(),
                crdb_region crdb_internal_region AS (
                    CASE region
                        WHEN 'us-east' THEN 'us-east'::crdb_internal_region
                        WHEN 'us-west' THEN 'us-west'::crdb_internal_region
                        WHEN 'eu-central' THEN 'eu-central'::crdb_internal_region
                        WHEN 'ap-south' THEN 'ap-south'::crdb_internal_region
                        ELSE 'us-east'::crdb_internal_region
                    END
                ) STORED NOT NULL
            ) LOCALITY REGIONAL BY ROW
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Failed to create rides table: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_region ON users (region)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_drivers_region ON drivers (region)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rides_region ON rides (region)")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"   ⚠ Warning creating indexes: {e}")
    
    cursor.close()

def configure_zones(conn, region):
    cursor = conn.cursor()
    
    region_map = {
        'us-east': 'us-east',
        'us-west': 'us-west',
        'eu-central': 'eu-central',
        'ap-south': 'ap-south'
    }
    
    crdb_region = region_map.get(region, region)
    
    for table in ['users', 'drivers', 'rides']:
        try:
            cursor.execute(f"""
                ALTER TABLE {table} CONFIGURE ZONE USING
                    num_replicas = 3
            """)
        except Exception as e:
            error_msg = str(e).lower()
            if "cannot change variable constraint" in error_msg:
                pass
            elif "constraint" in error_msg and "variable" in error_msg:
                pass
            else:
                print(f"      ⚠ Zone config for {table}: {e}")
    
    conn.commit()
    cursor.close()

def delete_all_data():
    print("=" * 70)
    print("DELETING ALL DATA FROM DATABASES")
    print("=" * 70)
    
    for region in REGION_CONFIGS.keys():
        print(f"\n🗑️  Deleting data from region: {region.upper()}")
        
        try:
            conn = get_connection(region)
            cursor = conn.cursor()
            
            cursor.execute("TRUNCATE TABLE rides CASCADE")
            print(f"   ✓ Deleted all rides")
            
            cursor.execute("TRUNCATE TABLE drivers CASCADE")
            print(f"   ✓ Deleted all drivers")
            
            cursor.execute("TRUNCATE TABLE users CASCADE")
            print(f"   ✓ Deleted all users")
            
            cursor.execute("TRUNCATE TABLE regions CASCADE")
            print(f"   ✓ Deleted all regions")
            
            conn.commit()
            cursor.close()
            conn.close()
            print(f"   ✅ Region {region.upper()} data deleted successfully")
            
        except Exception as e:
            print(f"   ❌ Error deleting data from region {region}: {e}")
            continue
    
    print("\n" + "=" * 70)
    print("✅ ALL DATA DELETED!")
    print("=" * 70)

def load_regions(conn, regions_df):
    cursor = conn.cursor()
    
    regions_df = regions_df.copy()
    regions_df['region_id'] = regions_df['region_id'].astype(str)
    regions_df['created_at'] = pd.to_datetime(regions_df['created_at'])
    
    insert_query = """
        INSERT INTO regions (region_id, region_code, name, lat_min, lat_max, lon_min, lon_max, node_count, primary_node, created_at)
        VALUES %s
        ON CONFLICT (region_id) DO NOTHING
    """
    
    values = [
        (
            row['region_id'],
            row['region_code'],
            row['name'],
            float(row['lat_min']),
            float(row['lat_max']),
            float(row['lon_min']),
            float(row['lon_max']),
            int(row['node_count']),
            row['primary_node'],
            row['created_at']
        )
        for _, row in regions_df.iterrows()
    ]
    
    execute_values(cursor, insert_query, values)
    conn.commit()
    cursor.close()
    print(f"   ✓ Loaded {len(values)} region records")

def load_users(conn, users_df, region):
    cursor = conn.cursor()
    
    region_users = users_df[users_df['region'] == region].copy()
    
    if len(region_users) == 0:
        print(f"   ⚠ No users found for region {region}")
        cursor.close()
        return
    
    region_users['user_id'] = region_users['user_id'].astype(str)
    region_users['created_at'] = pd.to_datetime(region_users['created_at'])
    
    insert_query = """
        INSERT INTO users (user_id, name, email, phone, latitude, longitude, region, rating, total_rides, created_at)
        VALUES %s
        ON CONFLICT (user_id) DO NOTHING
    """
    
    values = [
        (
            row['user_id'],
            row['name'],
            row['email'],
            str(row['phone']),
            float(row['latitude']),
            float(row['longitude']),
            row['region'],
            float(row['rating']),
            int(row['total_rides']),
            row['created_at']
        )
        for _, row in region_users.iterrows()
    ]
    
    execute_values(cursor, insert_query, values)
    conn.commit()
    cursor.close()
    print(f"   ✓ Loaded {len(values)} user records")

def load_drivers(conn, drivers_df, region):
    cursor = conn.cursor()
    
    region_drivers = drivers_df[drivers_df['region'] == region].copy()
    
    if len(region_drivers) == 0:
        print(f"   ⚠ No drivers found for region {region}")
        cursor.close()
        return
    
    region_drivers['driver_id'] = region_drivers['driver_id'].astype(str)
    region_drivers['created_at'] = pd.to_datetime(region_drivers['created_at'])
    
    insert_query = """
        INSERT INTO drivers (driver_id, name, email, phone, latitude, longitude, region, geohash, vehicle_info, license_plate, availability, rating, total_rides, created_at)
        VALUES %s
        ON CONFLICT (driver_id) DO NOTHING
    """
    
    values = [
        (
            row['driver_id'],
            row['name'],
            row['email'],
            str(row['phone']),
            float(row['latitude']),
            float(row['longitude']),
            row['region'],
            row['geohash'],
            row['vehicle_info'],
            row['license_plate'],
            row['availability'],
            float(row['rating']),
            int(row['total_rides']),
            row['created_at']
        )
        for _, row in region_drivers.iterrows()
    ]
    
    execute_values(cursor, insert_query, values)
    conn.commit()
    cursor.close()
    print(f"   ✓ Loaded {len(values)} driver records")

def load_rides(conn, rides_df, region):
    cursor = conn.cursor()
    
    region_rides = rides_df[rides_df['region'] == region].copy()
    
    if len(region_rides) == 0:
        print(f"   ⚠ No rides found for region {region}")
        cursor.close()
        return
    
    region_rides['ride_id'] = region_rides['ride_id'].astype(str)
    region_rides['user_id'] = region_rides['user_id'].astype(str)
    region_rides['driver_id'] = region_rides['driver_id'].apply(lambda x: str(x) if pd.notna(x) else None)
    region_rides['timestamp'] = pd.to_datetime(region_rides['timestamp'])
    
    insert_query = """
        INSERT INTO rides (ride_id, user_id, driver_id, pickup_lat, pickup_lon, dropoff_lat, dropoff_lon, region, pickup_geohash, status, price, distance_km, duration_minutes, timestamp)
        VALUES %s
        ON CONFLICT (ride_id) DO NOTHING
    """
    
    values = [
        (
            row['ride_id'],
            row['user_id'],
            row['driver_id'],
            float(row['pickup_lat']),
            float(row['pickup_lon']),
            float(row['dropoff_lat']),
            float(row['dropoff_lon']),
            row['region'],
            row['pickup_geohash'],
            row['status'],
            float(row['price']),
            float(row['distance_km']),
            int(row['duration_minutes']),
            row['timestamp']
        )
        for _, row in region_rides.iterrows()
    ]
    
    execute_values(cursor, insert_query, values)
    conn.commit()
    cursor.close()
    print(f"   ✓ Loaded {len(values)} ride records")

def main():
    clear_data = False
    if len(sys.argv) > 1 and sys.argv[1] in ['--clear', '-c', '--delete', '-d']:
        clear_data = True
    
    print("=" * 70)
    print("GEO-DISTRIBUTED RIDE-SHARING DATABASE SYSTEM")
    print("Data Loading Script")
    print(f"Environment: {ENVIRONMENT.upper()}")
    print("=" * 70)
    
    if clear_data:
        delete_all_data()
        print()
    
    data_dir = "generated_data"
    
    if not os.path.exists(data_dir):
        print(f"\n❌ Error: Directory '{data_dir}' not found!")
        print("   Please run data_generation.py first to generate the data.")
        return
    
    print(f"\n📂 Loading data from '{data_dir}/' directory...")
    
    try:
        users_df = pd.read_csv(f"{data_dir}/users.csv")
        drivers_df = pd.read_csv(f"{data_dir}/drivers.csv")
        rides_df = pd.read_csv(f"{data_dir}/rides.csv")
        regions_df = pd.read_csv(f"{data_dir}/regions.csv")
        
        print(f"   ✓ Loaded users.csv ({len(users_df)} records)")
        print(f"   ✓ Loaded drivers.csv ({len(drivers_df)} records)")
        print(f"   ✓ Loaded rides.csv ({len(rides_df)} records)")
        print(f"   ✓ Loaded regions.csv ({len(regions_df)} records)")
    except Exception as e:
        print(f"\n❌ Error loading CSV files: {e}")
        return
    
    print("\n" + "=" * 70)
    print("SETTING UP GEOGRAPHIC PARTITIONING")
    print("=" * 70)
    
    first_region = list(REGION_CONFIGS.keys())[0]
    print(f"\n🔧 Setting up database regions (connecting via {first_region})...")
    
    try:
        conn = get_connection(first_region)
        print(f"   ✓ Connected to {first_region} database")
        
        print(f"   Configuring database regions...")
        setup_database_regions(conn)
        
        print(f"   Creating regional tables...")
        create_tables(conn)
        print(f"   ✓ Regional tables created")
        
        conn.close()
    except Exception as e:
        print(f"   ❌ Error setting up tables: {e}")
        return
    
    print("\n" + "=" * 70)
    print("CONFIGURING GEOGRAPHIC ZONES")
    print("=" * 70)
    
    for region in REGION_CONFIGS.keys():
        print(f"\n🌍 Configuring zones for: {region.upper()}")
        try:
            conn = get_connection(region)
            configure_zones(conn, region)
            conn.close()
            print(f"   ✓ Zones configured for {region}")
        except Exception as e:
            print(f"   ⚠ Warning configuring zones for {region}: {e}")
    
    print("\n" + "=" * 70)
    print("LOADING DATA INTO REGIONAL DATABASES")
    print("=" * 70)
    
    for region in REGION_CONFIGS.keys():
        print(f"\n🌍 Processing region: {region.upper()}")
        
        try:
            conn = get_connection(region)
            print(f"   ✓ Connected to {region} database")
            
            print(f"   Loading regions...")
            load_regions(conn, regions_df)
            
            print(f"   Loading users...")
            load_users(conn, users_df, region)
            
            print(f"   Loading drivers...")
            load_drivers(conn, drivers_df, region)
            
            print(f"   Loading rides...")
            load_rides(conn, rides_df, region)
            
            conn.close()
            print(f"   ✅ Region {region.upper()} completed successfully")
            
        except Exception as e:
            print(f"   ❌ Error processing region {region}: {e}")
            continue
    
    print("\n" + "=" * 70)
    print("✅ DATA LOADING COMPLETE!")
    print("=" * 70)
    
    print("\n📊 Summary:")
    for region in REGION_CONFIGS.keys():
        users_count = len(users_df[users_df['region'] == region])
        drivers_count = len(drivers_df[drivers_df['region'] == region])
        rides_count = len(rides_df[rides_df['region'] == region])
        print(f"   {region.upper()}: {users_count} users, {drivers_count} drivers, {rides_count} rides")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ['--delete-only', '--drop-only']:
        delete_all_data()
    else:
        main()

