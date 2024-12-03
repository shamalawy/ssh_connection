from netmiko import ConnectHandler, NetMikoTimeoutException, NetMikoAuthenticationException
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from datetime import datetime
import time
import threading
import schedule
import logging
import os
import socket

from database import engine, Base, get_db  # Added get_db import here

from models import NetworkConnection
from database import engine, Base, SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NetworkConnectionManager:
    def __init__(self):
        # Create tables
        Base.metadata.create_all(bind=engine)
        self.connections = {}
        
        # Synchronize connections on startup
        self.synchronize_connections()

    def _validate_hostname(self, hostname):
        """
        Validate if the hostname is a valid DNS name or IP address
        
        :param hostname: Hostname or IP address to validate
        :return: True if valid, False otherwise
        """
        try:
            # Try to resolve the hostname
            socket.gethostbyname(hostname)
            return True
        except socket.error:
            return False

    def synchronize_connections(self):
        """
        Synchronize connections with the database, ensuring:
        1. All database-defined devices are connected
        2. No extra connections exist
        3. Disconnected devices are removed from active connections
        """
        # Create a new database session
        db = SessionLocal()
        
        try:
            # Retrieve all saved network connections from the database
            saved_connections = db.query(NetworkConnection).all()
            
            # Track which hostnames we've processed
            processed_hostnames = set()
            
            # Use ThreadPoolExecutor to connect to devices in parallel
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_hostname = {
                    executor.submit(self._connect_or_maintain_connection, db, connection): connection.hostname
                    for connection in saved_connections
                }
                
                for future in as_completed(future_to_hostname):
                    hostname = future_to_hostname[future]
                    processed_hostnames.add(hostname)
                    
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error processing {hostname}: {str(e)}")
            
            # Remove any connections not in the database
            self._cleanup_extra_connections(processed_hostnames)
            
            # Commit any status changes
            db.commit()
        
        except Exception as e:
            logger.error(f"Error during connection synchronization: {str(e)}")
        
        finally:
            # Close the database session
            db.close()

    def _connect_or_maintain_connection(self, db, connection):
        """
        Connect to or maintain a connection for a given device
        """
        try:
            hostname = connection.hostname
            
            # Check if connection already exists
            if hostname in self.connections:
                # Verify the existing connection is still valid
                try:
                    # Send a simple command to test connection
                    self.connections[hostname]['ssh_conn'].send_command('show version')
                    return  # Connection is good, move to next device
                except:
                    # Connection is no longer valid, remove it
                    self._disconnect_device(hostname)
            
            # Attempt to establish a new connection
            ssh_conn = self._create_connection(connection)
            
            if ssh_conn:
                # Store the connection
                self.connections[hostname] = {
                    'ssh_conn': ssh_conn,
                    'details': connection
                }
                
                # Update connection status
                connection.is_connected = True
                connection.last_connected = datetime.utcnow()
                
                logger.info(f"Successfully connected to {hostname}")
            else:
                # Mark as disconnected
                connection.is_connected = False
                logger.warning(f"Failed to connect to {hostname}")
        
        except Exception as conn_error:
            logger.error(f"Error processing {connection.hostname}: {str(conn_error)}")

    def _cleanup_extra_connections(self, processed_hostnames):
        """
        Remove any connections that are not in the processed hostnames
        """
        # Create a copy of connections to safely modify during iteration
        for hostname in list(self.connections.keys()):
            if hostname not in processed_hostnames:
                logger.info(f"Removing extra connection: {hostname}")
                self._disconnect_device(hostname)

    def _disconnect_device(self, hostname):
        """
        Disconnect and remove a device from active connections
        """
        if hostname in self.connections:
            try:
                # Disconnect SSH session
                self.connections[hostname]['ssh_conn'].disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting {hostname}: {str(e)}")
            
            # Remove from active connections
            del self.connections[hostname]

    def _create_connection(self, connection):
        """
        Establish SSH connection to network device
        
        :param connection: NetworkConnection database model instance
        :return: SSH connection or None
        """
        try:
            # Validate hostname/IP
            if not self._validate_hostname(connection.hostname):
                logger.error(f"Invalid hostname/IP: {connection.hostname}")
                return None

            device = {
                'device_type': connection.device_type,
                'host': connection.hostname,  # Now using hostname directly
                # 'username': connection.username,
                # 'password': self._retrieve_password(connection),
                'username': "mo",
                'password': 'mo',
                'fast_cli': True
            }
            
            connection_handler = ConnectHandler(**device)
            return connection_handler
        except (NetMikoTimeoutException, NetMikoAuthenticationException) as e:
            logger.error(f"Connection failed for {connection.hostname}: {str(e)}")
            return None

    def _retrieve_password(self, connection):
        """
        Retrieve password for a given connection
        
        This is a secure placeholder method. In production, 
        implement a robust secret management solution.
        """
        # Option 1: Environment variable based on hostname
        env_var_name = f"{connection.hostname.upper().replace('-', '_')}_PASSWORD"
        env_password = os.environ.get(env_var_name)
        if env_password:
            return env_password
        
        # Option 2: Generic fallback (CAUTION: Not recommended for production)
        # In a real-world scenario, use a secure secrets management system
        logger.warning(f"No secure password found for {connection.hostname}")
        return None

    def periodic_connection_check(self):
        """
        Periodically synchronize connections to ensure database state is maintained
        """
        self.synchronize_connections()

    def add_connection(self, db: Session, connection_details):
        """
        Add a new network connection
        
        :param db: Database session
        :param connection_details: Connection details from the API request
        :return: NetworkConnection database model
        """
        try:
            # Prepare device connection details
            device = {
                'device_type': connection_details.device_type,
                'host': connection_details.hostname,
                'username': connection_details.username,
                'password': connection_details.password,
                'fast_cli': True
            }
            
            # Attempt to establish SSH connection
            try:
                ssh_conn = ConnectHandler(**device)
            except (NetMikoTimeoutException, NetMikoAuthenticationException) as e:
                logger.error(f"Connection failed for {connection_details.hostname}: {str(e)}")
                raise ConnectionError(f"Failed to establish SSH connection: {str(e)}")
            
            # Find existing connection in the database
            existing_connection = db.query(NetworkConnection).filter_by(hostname=connection_details.hostname).first()
            
            if existing_connection:
                # Update existing connection
                existing_connection.is_connected = True
                existing_connection.last_connected = datetime.utcnow()
                existing_connection.username = connection_details.username
                existing_connection.device_type = connection_details.device_type
                db.commit()
                db_connection = existing_connection
            else:
                # Create new database record
                db_connection = NetworkConnection(
                    hostname=connection_details.hostname,
                    username=connection_details.username,
                    device_type=connection_details.device_type,
                    is_connected=True,
                    last_connected=datetime.utcnow()
                )
                db.add(db_connection)
                db.commit()
                db.refresh(db_connection)
            
            # Store the SSH connection
            self.connections[connection_details.hostname] = {
                'ssh_conn': ssh_conn,
                'details': db_connection
            }
            
            return db_connection
        
        except Exception as e:
            logger.error(f"Error adding connection: {str(e)}")
            raise
    
    
    def remove_connection(self, db: Session, hostname):
        """
        Remove a network connection
        """
        # Remove from database
        conn = db.query(NetworkConnection).filter_by(hostname=hostname).first()
        if conn:
            db.delete(conn)
            db.commit()
        
        # Remove SSH connection
        if hostname in self.connections:
            try:
                self.connections[hostname]['ssh_conn'].disconnect()
            except:
                pass
            del self.connections[hostname]
        
        return True

# Global connection manager
connection_manager = NetworkConnectionManager()

# Background thread for periodic connection checks
def start_connection_checker():
    """
    Start a background thread to periodically check and sync connections
    """
    def job():
        connection_manager.periodic_connection_check()
    
    # Check connections every minute
    schedule.every(1).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

# Start background connection checker
checker_thread = threading.Thread(target=start_connection_checker, daemon=True)
checker_thread.start()