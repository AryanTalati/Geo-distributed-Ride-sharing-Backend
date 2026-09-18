import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from server.constants import REGION_CONFIGS

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

def check_database_regions(conn):
    cursor = conn.cursor()
    print("\n" + "=" * 70)
    print("DATABASE REGIONS CONFIGURATION")
    print("=" * 70)
    
    try:
        cursor.execute("SHOW REGIONS FROM DATABASE rideshare")
        regions = cursor.fetchall()
        print("\n📋 Configured Regions:")
        for region in regions:
            print(f"   • {region[0]}")
    except Exception as e:
        print(f"   ⚠ Error checking regions: {e}")
    
    cursor.close()

def check_table_distribution(conn, table_name, region_name):
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
            SELECT 
                region,
                crdb_region,
                COUNT(*) as count
            FROM {table_name}
            GROUP BY region, crdb_region
            ORDER BY region
        """)
        results = cursor.fetchall()
        
        if results:
            print(f"\n   📊 {table_name.upper()} distribution:")
            total = 0
            for row in results:
                region, crdb_region, count = row
                total += count
                print(f"      Region '{region}' (crdb_region: {crdb_region}): {count} rows")
            print(f"      Total: {total} rows")
        else:
            print(f"\n   ⚠ No data found in {table_name}")
            
    except Exception as e:
        print(f"   ❌ Error checking {table_name}: {e}")
    
    cursor.close()

def check_zone_configurations(conn, table_name):
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
            SELECT 
                zone_name,
                constraints,
                num_replicas
            FROM crdb_internal.zones
            WHERE zone_name LIKE '%{table_name}%'
            ORDER BY zone_name
        """)
        results = cursor.fetchall()
        
        if results:
            print(f"\n   ⚙️  Zone configurations for {table_name}:")
            for row in results:
                zone_name, constraints, num_replicas = row
                print(f"      Zone: {zone_name}")
                print(f"         Constraints: {constraints}")
                print(f"         Replicas: {num_replicas}")
        else:
            print(f"\n   ⚠ No zone configuration found for {table_name}")
            
    except Exception as e:
        print(f"   ⚠ Could not check zone config (may require admin privileges): {e}")
    
    cursor.close()

def check_node_distribution(conn, table_name):
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
            SELECT 
                region,
                COUNT(*) as count,
                COUNT(DISTINCT crdb_region) as distinct_regions
            FROM {table_name}
            GROUP BY region
            ORDER BY region
        """)
        results = cursor.fetchall()
        
        if results:
            print(f"\n   🗺️  Node distribution for {table_name}:")
            for row in results:
                region, count, distinct_regions = row
                print(f"      Region '{region}': {count} rows")
        else:
            print(f"\n   ⚠ No data found in {table_name}")
            
    except Exception as e:
        print(f"   ❌ Error checking node distribution: {e}")
    
    cursor.close()

def check_region_mapping(conn):
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("REGION COLUMN TO CRDB_REGION MAPPING")
    print("=" * 70)
    
    for table in ['users', 'drivers', 'rides']:
        try:
            cursor.execute(f"""
                SELECT DISTINCT
                    region,
                    crdb_region
                FROM {table}
                ORDER BY region
            """)
            results = cursor.fetchall()
            
            if results:
                print(f"\n📋 {table.upper()}:")
                for row in results:
                    region, crdb_region = row
                    match = "✓" if str(region) == str(crdb_region) else "✗"
                    print(f"   {match} region='{region}' → crdb_region='{crdb_region}'")
            else:
                print(f"\n   ⚠ No data in {table}")
        except Exception as e:
            print(f"   ❌ Error checking {table}: {e}")
    
    cursor.close()

def check_data_by_region(conn, region_name):
    cursor = conn.cursor()
    
    print(f"\n" + "=" * 70)
    print(f"DATA CHECK FOR REGION: {region_name.upper()}")
    print("=" * 70)
    
    for table in ['users', 'drivers', 'rides']:
        try:
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM {table} 
                WHERE region = '{region_name}'
            """)
            count = cursor.fetchone()[0]
            print(f"   {table.upper()}: {count} rows")
        except Exception as e:
            print(f"   ❌ Error checking {table}: {e}")
    
    cursor.close()

def main():
    print("=" * 70)
    print("GEOGRAPHIC PARTITIONING VERIFICATION")
    print("=" * 70)
    
    first_region = list(REGION_CONFIGS.keys())[0]
    
    try:
        conn = get_connection(first_region)
        print(f"\n✓ Connected to {first_region} database")
        
        check_database_regions(conn)
        
        print("\n" + "=" * 70)
        print("DATA DISTRIBUTION BY REGION")
        print("=" * 70)
        
        for table in ['users', 'drivers', 'rides']:
            check_table_distribution(conn, table, first_region)
        
        check_region_mapping(conn)
        
        print("\n" + "=" * 70)
        print("ZONE CONFIGURATIONS")
        print("=" * 70)
        
        for table in ['users', 'drivers', 'rides']:
            check_zone_configurations(conn, table)
        
        print("\n" + "=" * 70)
        print("DATA COUNT BY REGION (from each regional connection)")
        print("=" * 70)
        
        for region in REGION_CONFIGS.keys():
            try:
                region_conn = get_connection(region)
                check_data_by_region(region_conn, region)
                region_conn.close()
            except Exception as e:
                print(f"   ❌ Error connecting to {region}: {e}")
        
        conn.close()
        
        print("\n" + "=" * 70)
        print("MANUAL VERIFICATION QUERIES")
        print("=" * 70)
        print("\nYou can also run these SQL queries manually:")
        print("\n1. Check data distribution:")
        print("   SELECT region, crdb_region, COUNT(*) FROM users GROUP BY region, crdb_region;")
        print("\n2. Check zone configurations:")
        print("   SHOW ZONE CONFIGURATION FOR TABLE users;")
        print("\n3. Check database regions:")
        print("   SHOW REGIONS FROM DATABASE rideshare;")
        print("\n4. Check specific region data:")
        print("   SELECT COUNT(*) FROM users WHERE region = 'us-east';")
        print("\n5. View sample data with region info:")
        print("   SELECT user_id, name, region, crdb_region FROM users LIMIT 10;")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()

