"""
Listing repository for database operations.
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import json
import psycopg2

from ...core.db import db
from ...core.logging import get_logger
from ...domain.listing import Listing

logger = get_logger(__name__)

class ListingRepository:
    """
    Repository for ticket listing data operations.
    
    This class handles database operations for ticket listings,
    specifically designed for time-series data with TimescaleDB.
    """
    
    TABLE_NAME = "ticket_listings"
    
    @staticmethod
    def ensure_table_exists():
        """
        Ensure the ticket_listings hypertable exists in the database.
        
        This creates a TimescaleDB hypertable for efficient time-series data storage.
        """
        # First, create a regular table
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {ListingRepository.TABLE_NAME} (
            listing_id SERIAL,
            event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
            viagogo_id TEXT NOT NULL,
            viagogo_listing_id BIGINT,
            row_id BIGINT,
            section TEXT NOT NULL,
            row TEXT,
            quantity INTEGER NOT NULL,
            price_per_ticket NUMERIC(10, 2) NOT NULL,
            total_price NUMERIC(10, 2) NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            listing_url TEXT,
            listing_notes JSONB,
            provider TEXT NOT NULL DEFAULT 'StubHub',
            captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (listing_id, captured_at)
        );
        """
        
        # Then convert it to a hypertable
        create_hypertable_sql = f"""
        SELECT create_hypertable('{ListingRepository.TABLE_NAME}', 'captured_at', 
                                 if_not_exists => TRUE);
        """
        
        # Create indexes for efficient querying
        create_indexes_sql = f"""
        CREATE INDEX IF NOT EXISTS idx_listings_event_id ON {ListingRepository.TABLE_NAME} (event_id);
        CREATE INDEX IF NOT EXISTS idx_listings_viagogo_id ON {ListingRepository.TABLE_NAME} (viagogo_id);
        CREATE INDEX IF NOT EXISTS idx_listings_viagogo_listing_id ON {ListingRepository.TABLE_NAME} (viagogo_listing_id);
        CREATE INDEX IF NOT EXISTS idx_listings_section ON {ListingRepository.TABLE_NAME} (section);
        CREATE INDEX IF NOT EXISTS idx_listings_captured_at ON {ListingRepository.TABLE_NAME} (captured_at DESC);
        """
        
        try:
            # Create the regular table first
            db.execute(create_table_sql)
            logger.info(f"Ensured table {ListingRepository.TABLE_NAME} exists")
            
            # Convert to hypertable
            try:
                db.execute(create_hypertable_sql)
                logger.info(f"Converted {ListingRepository.TABLE_NAME} to TimescaleDB hypertable")
            except psycopg2.errors.DuplicateTable:
                logger.info(f"Table {ListingRepository.TABLE_NAME} is already a hypertable")
            except Exception as e:
                logger.error(f"Error creating hypertable: {str(e)}")
                
            # Create indexes
            db.execute(create_indexes_sql)
            logger.info(f"Created indexes for {ListingRepository.TABLE_NAME}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to setup {ListingRepository.TABLE_NAME} table", error=str(e))
            return False
    
    @staticmethod
    def insert(listing: Listing) -> Optional[int]:
        """
        Insert a single ticket listing into the database.
        
        Args:
            listing: The Listing object to insert
            
        Returns:
            The ID of the new listing, or None if insertion failed
        """
        insert_sql = f"""
        INSERT INTO {ListingRepository.TABLE_NAME} 
        (event_id, viagogo_id, viagogo_listing_id, row_id, section, row, quantity, price_per_ticket, 
         total_price, currency, listing_url, listing_notes, provider, captured_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING listing_id;
        """
        
        try:
            params = (
                listing.event_id,
                listing.viagogo_id,
                listing.viagogo_listing_id,
                listing.row_id,
                listing.section,
                listing.row,
                listing.quantity,
                listing.price_per_ticket,
                listing.total_price,
                listing.currency,
                listing.listing_url,
                listing.listing_notes,
                listing.provider,
                listing.captured_at or datetime.now()
            )
            
            result = db.execute(insert_sql, params)
            
            if result and len(result) > 0:
                listing_id = result[0]['listing_id']
                logger.debug(f"Inserted listing ID {listing_id} for event {listing.event_id}")
                return listing_id
            else:
                logger.warning(f"Failed to insert listing for event {listing.event_id}")
                return None
        except Exception as e:
            logger.error(f"Error inserting listing for event {listing.event_id}", error=str(e))
            return None
    
    @staticmethod
    def batch_insert(event_id: int, listings: List[Listing]) -> int:
        """
        Insert multiple ticket listings in batch.
        
        Args:
            event_id: The event ID to associate with these listings
            listings: List of Listing objects to insert
            
        Returns:
            Count of successfully inserted listings
        """
        if not listings:
            return 0
            
        # Set event_id for all listings
        for listing in listings:
            listing.event_id = event_id
        
        # Use a more efficient bulk insert with COPY
        # This is much faster than executemany for large batches
        insert_sql = f"""
        INSERT INTO {ListingRepository.TABLE_NAME} 
        (event_id, viagogo_id, viagogo_listing_id, row_id, section, row, quantity, price_per_ticket, 
         total_price, currency, listing_url, listing_notes, provider, captured_at)
        VALUES %s;
        """
        
        # Prepare data for psycopg2.extras.execute_values
        template = "(%(event_id)s, %(viagogo_id)s, %(viagogo_listing_id)s, %(row_id)s, %(section)s, %(row)s, %(quantity)s, %(price_per_ticket)s, %(total_price)s, %(currency)s, %(listing_url)s, %(listing_notes)s, %(provider)s, %(captured_at)s)"
        
        params_list = []
        now = datetime.now()
        
        for listing in listings:
            params_list.append({
                'event_id': event_id,
                'viagogo_id': listing.viagogo_id,
                'viagogo_listing_id': listing.viagogo_listing_id,
                'row_id': listing.row_id,
                'section': listing.section,
                'row': listing.row,
                'quantity': listing.quantity,
                'price_per_ticket': listing.price_per_ticket,
                'total_price': listing.total_price,
                'currency': listing.currency,
                'listing_url': listing.listing_url,
                'listing_notes': listing.listing_notes,
                'provider': listing.provider,
                'captured_at': listing.captured_at or now
            })
        
        try:
            # Use psycopg2.extras.execute_values for more efficient bulk insert
            from psycopg2.extras import execute_values
            import json
            
            # Ensure proper JSON serialization for any remaining dict/list values
            def adapt_params(params):
                adapted = params.copy()
                if adapted.get('listing_notes') and not isinstance(adapted['listing_notes'], str):
                    try:
                        adapted['listing_notes'] = json.dumps(adapted['listing_notes'])
                    except (TypeError, ValueError):
                        adapted['listing_notes'] = None
                return adapted
            
            adapted_params = [adapt_params(p) for p in params_list]
            
            with db.connection() as conn:
                with conn.cursor() as cursor:
                    execute_values(cursor, insert_sql, adapted_params, template=template, page_size=1000)
                    conn.commit()
                    row_count = cursor.rowcount
            
            logger.info(f"Batch inserted {row_count} listings for event {event_id}")
            return row_count
        except Exception as e:
            logger.error(f"Error batch inserting listings for event {event_id}", error=str(e))
            return 0
    
    @staticmethod
    def get_latest_listings(event_id: int, limit: int = 100) -> List[Listing]:
        """
        Get the most recent ticket listings for an event.
        
        Args:
            event_id: The event ID to get listings for
            limit: Maximum number of listings to return
            
        Returns:
            List of Listing objects
        """
        query = f"""
        SELECT * FROM {ListingRepository.TABLE_NAME}
        WHERE event_id = %s
        ORDER BY captured_at DESC
        LIMIT %s;
        """
        
        try:
            results = db.execute(query, (event_id, limit), commit=False)
            
            if not results:
                return []
                
            listings = [Listing.from_dict(dict(row)) for row in results]
            logger.info(f"Retrieved {len(listings)} latest listings for event {event_id}")
            return listings
        except Exception as e:
            logger.error(f"Error retrieving latest listings for event {event_id}", error=str(e))
            return []
    
    @staticmethod
    def get_listings_for_timerange(
        event_id: int, 
        start_time: datetime, 
        end_time: datetime = None
    ) -> List[Listing]:
        """
        Get ticket listings for an event within a specific time range.
        
        Args:
            event_id: The event ID to get listings for
            start_time: Start of the time range
            end_time: End of the time range (defaults to now)
            
        Returns:
            List of Listing objects
        """
        end_time = end_time or datetime.now()
        
        query = f"""
        SELECT * FROM {ListingRepository.TABLE_NAME}
        WHERE event_id = %s AND captured_at BETWEEN %s AND %s
        ORDER BY captured_at DESC;
        """
        
        try:
            results = db.execute(query, (event_id, start_time, end_time), commit=False)
            
            if not results:
                return []
                
            listings = [Listing.from_dict(dict(row)) for row in results]
            logger.info(
                f"Retrieved {len(listings)} listings for event {event_id} "
                f"between {start_time} and {end_time}"
            )
            return listings
        except Exception as e:
            logger.error(
                f"Error retrieving listings for event {event_id} in timerange", 
                error=str(e)
            )
            return []
    
    @staticmethod
    def get_price_history(
        event_id: int,
        time_bucket: str = '1 day',
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get ticket price history aggregated by time buckets.
        
        Uses TimescaleDB time_bucket function to aggregate price data.
        
        Args:
            event_id: The event ID to get price history for
            time_bucket: Time bucket size (e.g., '1 hour', '1 day')
            days_back: Number of days to look back
            
        Returns:
            List of price data points with min, max, and avg prices
        """
        start_time = datetime.now() - timedelta(days=days_back)
        
        query = f"""
        SELECT 
            time_bucket(%s, captured_at) AS bucket,
            MIN(price_per_ticket) AS min_price,
            MAX(price_per_ticket) AS max_price,
            AVG(price_per_ticket) AS avg_price,
            COUNT(*) AS listing_count
        FROM {ListingRepository.TABLE_NAME}
        WHERE event_id = %s AND captured_at > %s
        GROUP BY bucket
        ORDER BY bucket;
        """
        
        try:
            results = db.execute(query, (time_bucket, event_id, start_time), commit=False)
            
            if not results:
                return []
                
            # Convert results to list of dicts
            price_history = [dict(row) for row in results]
            logger.info(f"Retrieved price history for event {event_id} with {len(price_history)} data points")
            return price_history
        except Exception as e:
            logger.error(f"Error retrieving price history for event {event_id}", error=str(e))
            return []
    
    @staticmethod
    def get_price_by_section(
        event_id: int,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get average ticket prices by section.
        
        Args:
            event_id: The event ID to get section prices for
            days_back: Number of days to look back
            
        Returns:
            List of section price data
        """
        start_time = datetime.now() - timedelta(days=days_back)
        
        query = f"""
        SELECT 
            section,
            AVG(price_per_ticket) AS avg_price,
            MIN(price_per_ticket) AS min_price,
            MAX(price_per_ticket) AS max_price,
            COUNT(*) AS listing_count,
            MAX(captured_at) AS latest_capture
        FROM {ListingRepository.TABLE_NAME}
        WHERE event_id = %s AND captured_at > %s
        GROUP BY section
        ORDER BY avg_price;
        """
        
        try:
            results = db.execute(query, (event_id, start_time), commit=False)
            
            if not results:
                return []
                
            # Convert results to list of dicts
            section_prices = [dict(row) for row in results]
            logger.info(f"Retrieved section prices for event {event_id} with {len(section_prices)} sections")
            return section_prices
        except Exception as e:
            logger.error(f"Error retrieving section prices for event {event_id}", error=str(e))
            return []
