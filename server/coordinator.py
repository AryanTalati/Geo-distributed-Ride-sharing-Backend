import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
from datetime import datetime
import time
import threading
from constants import REGION_CONFIGS, REGION_BOUNDS

class Coordinator:
    def __init__(self):
        self.connections = {}
        self.connection_status = {}
        self.connection_lock = threading.Lock()
        self.heartbeat_interval = 30
        self.heartbeat_thread = None
        self._initialize_connections()
        self._start_heartbeat()
    
    def _initialize_connections(self):
        for region, config in REGION_CONFIGS.items():
            self._connect_region(region, config)
    
    def _connect_region(self, region, config=None):
        if config is None:
            config = REGION_CONFIGS.get(region)
            if config is None:
                return False
        
        try:
            conn = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                dbname=config['database'],
                user=config['user'],
                password=config['password'],
                connect_timeout=5
            )
            conn.autocommit = True
            with self.connection_lock:
                if region in self.connections:
                    try:
                        self.connections[region].close()
                    except:
                        pass
                self.connections[region] = conn
                self.connection_status[region] = 'healthy'
            return True
        except Exception as e:
            with self.connection_lock:
                self.connection_status[region] = 'unhealthy'
            print(f"Warning: Could not connect to {region}: {e}")
            return False
    
    def _check_connection_health(self, region):
        if region not in self.connections:
            return False
        
        conn = self.connections[region]
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        except:
            return False
    
    def _reconnect_region(self, region):
        config = REGION_CONFIGS.get(region)
        if config is None:
            return False
        return self._connect_region(region, config)
    
    def _start_heartbeat(self):
        def heartbeat_loop():
            while True:
                time.sleep(self.heartbeat_interval)
                with self.connection_lock:
                    regions_to_check = list(self.connections.keys())
                
                for region in regions_to_check:
                    is_healthy = self._check_connection_health(region)
                    with self.connection_lock:
                        if is_healthy:
                            self.connection_status[region] = 'healthy'
                        else:
                            self.connection_status[region] = 'unhealthy'
                            if region in self.connections:
                                try:
                                    self.connections[region].close()
                                except:
                                    pass
                                del self.connections[region]
                            self._reconnect_region(region)
        
        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
    
    def _determine_region(self, latitude, longitude):
        for region, bounds in REGION_BOUNDS.items():
            if bounds['lat_min'] <= latitude <= bounds['lat_max'] and bounds['lon_min'] <= longitude <= bounds['lon_max']:
                return region
        return 'us-east'
    
    def _get_fallback_regions(self, primary_region):
        all_regions = list(REGION_CONFIGS.keys())
        fallback_order = []
        
        for region in all_regions:
            if region != primary_region:
                fallback_order.append(region)
        
        return fallback_order
    
    def _get_connection(self, region, retry=True):
        with self.connection_lock:
            if region in self.connections:
                if self.connection_status.get(region) == 'healthy':
                    if self._check_connection_health(region):
                        return self.connections[region]
                    else:
                        self.connection_status[region] = 'unhealthy'
                        try:
                            self.connections[region].close()
                        except:
                            pass
                        del self.connections[region]
        
        if retry:
            if self._reconnect_region(region):
                with self.connection_lock:
                    if region in self.connections:
                        return self.connections[region]
        
        raise ValueError(f"Region {region} not available")
    
    def _get_available_region(self, preferred_region):
        if preferred_region:
            try:
                self._get_connection(preferred_region, retry=True)
                return preferred_region
            except:
                pass
        
        fallback_regions = self._get_fallback_regions(preferred_region or 'us-east')
        
        for region in fallback_regions:
            try:
                self._get_connection(region, retry=True)
                return region
            except:
                continue
        
        raise Exception("No available regions")
    
    def _execute_with_retry(self, operation_func, max_retries=3, initial_delay=0.1):
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return operation_func()
            except (psycopg2.OperationalError, psycopg2.InterfaceError, ValueError) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    raise
            except Exception as e:
                raise
        
        raise last_exception
    
    def create_ride(self, user_id, pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
                    driver_id=None, status='requested', price=0.0, distance_km=0.0,
                    duration_minutes=0, pickup_geohash=None):
        preferred_region = self._determine_region(pickup_lat, pickup_lon)
        ride_id = str(uuid.uuid4())
        
        def create_operation():
            region = self._get_available_region(preferred_region)
            conn = self._get_connection(region, retry=True)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            try:
                cursor.execute("""
                    INSERT INTO rides (ride_id, user_id, driver_id, pickup_lat, pickup_lon,
                                     dropoff_lat, dropoff_lon, region, pickup_geohash,
                                     status, price, distance_km, duration_minutes, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING *
                """, (ride_id, user_id, driver_id, pickup_lat, pickup_lon,
                      dropoff_lat, dropoff_lon, region, pickup_geohash,
                      status, price, distance_km, duration_minutes))
                
                result = cursor.fetchone()
                conn.commit()
                return dict(result) if result else {}
            except Exception as e:
                conn.rollback()
                raise Exception(f"Failed to create ride in {region}: {e}")
            finally:
                cursor.close()
        
        return self._execute_with_retry(create_operation)
    
    def get_ride(self, ride_id):
        regions_to_try = list(REGION_CONFIGS.keys())
        
        for region in regions_to_try:
            try:
                conn = self._get_connection(region, retry=False)
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                try:
                    cursor.execute("""
                        SELECT * FROM rides WHERE ride_id = %s
                    """, (ride_id,))
                    
                    result = cursor.fetchone()
                    if result:
                        cursor.close()
                        return dict(result)
                except Exception as e:
                    pass
                finally:
                    cursor.close()
            except:
                continue
        
        return None
    
    def get_rides(self, region=None, user_id=None, driver_id=None, status=None, limit=100):
        all_rides = []
        try:
            limit_value = int(limit) if limit is not None else 100
        except (TypeError, ValueError):
            limit_value = 100
        if limit_value < 0:
            limit_value = 100
        if limit_value == 0:
            return []
        
        if region and region not in REGION_CONFIGS:
            return []
        
        regions_to_search = [region] if region else REGION_CONFIGS.keys()
        
        for reg in regions_to_search:
            try:
                conn = self._get_connection(reg, retry=False)
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                try:
                    query = "SELECT * FROM rides WHERE region = %s"
                    params = [reg]
                    
                    if user_id:
                        query += " AND user_id = %s"
                        params.append(user_id)
                    
                    if driver_id:
                        query += " AND driver_id = %s"
                        params.append(driver_id)
                    
                    if status:
                        query += " AND status = %s"
                        params.append(status)
                    
                    query += " ORDER BY timestamp DESC LIMIT %s"
                    params.append(limit_value)
                    
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    
                    for row in results:
                        all_rides.append(dict(row))
                except Exception as e:
                    pass
                finally:
                    cursor.close()
            except:
                continue
        
        all_rides.sort(key=lambda x: x.get('timestamp', datetime.min), reverse=True)
        return all_rides[:limit_value]
    
    def update_ride(self, ride_id, **kwargs):
        ride = self.get_ride(ride_id)
        if not ride:
            return None
        
        original_region_preferred = ride['region']
        pickup_lat = kwargs.get('pickup_lat', ride['pickup_lat'])
        pickup_lon = kwargs.get('pickup_lon', ride['pickup_lon'])
        new_region_preferred = self._determine_region(pickup_lat, pickup_lon)
        
        if new_region_preferred != original_region_preferred:
            def update_cross_region():
                original_region = self._get_available_region(original_region_preferred)
                new_region = self._get_available_region(new_region_preferred)
                
                old_conn = self._get_connection(original_region, retry=True)
                new_conn = self._get_connection(new_region, retry=True)
                old_cursor = old_conn.cursor(cursor_factory=RealDictCursor)
                
                try:
                    old_cursor.execute("SELECT * FROM rides WHERE ride_id = %s", (ride_id,))
                    ride_data = old_cursor.fetchone()
                    if not ride_data:
                        old_cursor.close()
                        return None
                    
                    ride_dict = dict(ride_data)
                    ride_dict.update(kwargs)
                    ride_dict['region'] = new_region
                    
                    old_cursor.execute("DELETE FROM rides WHERE ride_id = %s", (ride_id,))
                    old_conn.commit()
                    old_cursor.close()
                    
                    new_cursor = new_conn.cursor(cursor_factory=RealDictCursor)
                    new_cursor.execute("""
                        INSERT INTO rides (ride_id, user_id, driver_id, pickup_lat, pickup_lon,
                                         dropoff_lat, dropoff_lon, region, pickup_geohash,
                                         status, price, distance_km, duration_minutes, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING *
                    """, (ride_dict['ride_id'], ride_dict['user_id'], ride_dict.get('driver_id'),
                          ride_dict['pickup_lat'], ride_dict['pickup_lon'],
                          ride_dict['dropoff_lat'], ride_dict['dropoff_lon'],
                          ride_dict['region'], ride_dict.get('pickup_geohash'),
                          ride_dict['status'], ride_dict['price'],
                          ride_dict['distance_km'], ride_dict['duration_minutes'],
                          ride_dict['timestamp']))
                    
                    result = new_cursor.fetchone()
                    new_conn.commit()
                    new_cursor.close()
                    return dict(result) if result else ride_dict
                except Exception as e:
                    old_conn.rollback()
                    new_conn.rollback()
                    raise Exception(f"Failed to update ride: {e}")
            
            return self._execute_with_retry(update_cross_region)
        
        def update_same_region():
            original_region = self._get_available_region(original_region_preferred)
            conn = self._get_connection(original_region, retry=True)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            allowed_fields = ['driver_id', 'status', 'price', 'distance_km', 'duration_minutes',
                             'pickup_lat', 'pickup_lon', 'dropoff_lat', 'dropoff_lon', 'pickup_geohash']
            
            update_fields = []
            params = []
            for field, value in kwargs.items():
                if field in allowed_fields and value is not None:
                    update_fields.append(f"{field} = %s")
                    params.append(value)
            
            if 'pickup_lat' in kwargs or 'pickup_lon' in kwargs:
                update_fields.append("region = %s")
                params.append(new_region_preferred)
            
            if not update_fields:
                cursor.close()
                return ride
            
            params.append(ride_id)
            query = f"UPDATE rides SET {', '.join(update_fields)} WHERE ride_id = %s RETURNING *"
            
            try:
                cursor.execute(query, params)
                result = cursor.fetchone()
                conn.commit()
                return dict(result) if result else ride
            except Exception as e:
                conn.rollback()
                raise Exception(f"Failed to update ride: {e}")
            finally:
                cursor.close()
        
        return self._execute_with_retry(update_same_region)
    
    def delete_ride(self, ride_id):
        ride = self.get_ride(ride_id)
        if not ride:
            return False
        
        preferred_region = ride['region']
        
        def delete_operation():
            region = self._get_available_region(preferred_region)
            conn = self._get_connection(region, retry=True)
            cursor = conn.cursor()
            
            try:
                cursor.execute("DELETE FROM rides WHERE ride_id = %s", (ride_id,))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                conn.rollback()
                raise Exception(f"Failed to delete ride: {e}")
            finally:
                cursor.close()
        
        return self._execute_with_retry(delete_operation)
    
    def get_connection_status(self):
        status = {}
        with self.connection_lock:
            for region in REGION_CONFIGS.keys():
                if region in self.connections:
                    is_healthy = self._check_connection_health(region)
                    status[region] = 'healthy' if is_healthy else 'unhealthy'
                else:
                    status[region] = 'disconnected'
        return status
    
    def close_all_connections(self):
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            pass
        with self.connection_lock:
            for region, conn in self.connections.items():
                try:
                    conn.close()
                except Exception as e:
                    print(f"Error closing connection to {region}: {e}")
            self.connections.clear()
            self.connection_status.clear()

coordinator = Coordinator()

