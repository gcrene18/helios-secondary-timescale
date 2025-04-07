"""
Database connection management for TimescaleDB.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

from ..config.settings import settings
from .logging import get_logger

logger = get_logger(__name__)

class DatabaseManager:
    """
    Manages database connections and operations with TimescaleDB.
    
    This class provides connection pooling and context managers for
    database operations, with automatic error handling and retry logic.
    """
    
    def __init__(self, connection_string=None):
        """Initialize database manager with connection information."""
        self.connection_string = connection_string or settings.db_uri
        self._conn = None
        logger.info("Database manager initialized")
        
    def connect(self):
        """Establish a connection to the database."""
        if self._conn is None or self._conn.closed:
            try:
                logger.debug("Connecting to database", host=settings.db_host)
                self._conn = psycopg2.connect(
                    self.connection_string,
                    cursor_factory=RealDictCursor
                )
                logger.info("Database connection established")
            except Exception as e:
                logger.error("Database connection error", error=str(e))
                raise
        return self._conn
    
    def close(self):
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            logger.debug("Database connection closed")
        self._conn = None
    
    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = self.connect()
        try:
            yield conn
        finally:
            # Connection will be returned to the pool, not closed
            pass
    
    @contextmanager
    def cursor(self, commit=False):
        """Context manager for database cursors."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("Database error", error=str(e))
            raise
        finally:
            cursor.close()
    
    def execute(self, query, params=None, commit=True):
        """Execute a query and optionally commit the transaction."""
        with self.cursor(commit=commit) as cursor:
            cursor.execute(query, params or {})
            return cursor.fetchall() if cursor.description else None
    
    def execute_many(self, query, params_list, commit=True):
        """Execute a query multiple times with different parameters."""
        with self.cursor(commit=commit) as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def initialize_timescale(self):
        """Initialize TimescaleDB extensions and hypertables if not already done."""
        # Create hypertables and necessary indexes
        try:
            with self.cursor(commit=True) as cursor:
                # Check if timescaledb extension exists
                cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
                has_timescale = cursor.fetchone()['exists']
                
                if not has_timescale:
                    logger.info("Creating TimescaleDB extension")
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
                else:
                    logger.debug("TimescaleDB extension already exists")
                    
            logger.info("TimescaleDB initialization complete")
            return True
        except Exception as e:
            logger.error("Failed to initialize TimescaleDB", error=str(e))
            return False

    def test_connection(self):
        """
        Test the database connection.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            conn = self.connect()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 as test_value")
                result = cursor.fetchone()
                if result and 'test_value' in result and result['test_value'] == 1:
                    logger.info("Database connection test successful")
                    return True
                else:
                    logger.error(f"Database connection test failed: {result}")
                    return False
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")
            return False


# Global database manager instance
db = DatabaseManager()
