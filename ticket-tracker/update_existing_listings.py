#!/usr/bin/env python
"""
Script to update existing listings in the database to extract viagogo_listing_id from listing_url.
"""
import sys
import os
import logging
import re
from datetime import datetime

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.db import db

def update_existing_listings():
    """
    Update existing listings to extract viagogo_listing_id from listing_url.
    """
    logger.info("Starting update of existing listings")
    
    # Query to get all listings with a listing_url but no viagogo_listing_id
    select_sql = """
    SELECT 
        listing_id, 
        listing_url 
    FROM 
        ticket_listings 
    WHERE 
        listing_url IS NOT NULL 
        AND listing_url LIKE '%/listing/%' 
        AND (viagogo_listing_id IS NULL OR viagogo_listing_id = 0)
    LIMIT 10000;
    """
    
    try:
        # Get listings that need updating
        results = db.execute(select_sql, commit=False)
        
        if not results:
            logger.info("No listings found that need updating")
            return
        
        logger.info(f"Found {len(results)} listings to update")
        
        # Pattern to extract listing ID from URL
        pattern = r'/listing/(\d+)'
        
        # Keep track of successful and failed updates
        success_count = 0
        failed_count = 0
        
        # Process each listing
        for listing in results:
            listing_id = listing['listing_id']
            listing_url = listing['listing_url']
            
            try:
                # Extract the viagogo listing ID from the URL
                match = re.search(pattern, listing_url)
                
                if match:
                    viagogo_listing_id = int(match.group(1))
                    
                    # Update the listing with the extracted ID
                    update_sql = """
                    UPDATE ticket_listings
                    SET viagogo_listing_id = %s
                    WHERE listing_id = %s;
                    """
                    
                    db.execute(update_sql, (viagogo_listing_id, listing_id))
                    success_count += 1
                    
                    if success_count % 100 == 0:
                        logger.info(f"Updated {success_count} listings so far")
                else:
                    logger.warning(f"Could not extract listing ID from URL: {listing_url}")
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error updating listing {listing_id}: {str(e)}")
                failed_count += 1
        
        logger.info(f"Update completed. Successfully updated {success_count} listings. Failed to update {failed_count} listings.")
        
        # Check if there are more listings to update
        remaining_sql = """
        SELECT COUNT(*) as remaining
        FROM ticket_listings 
        WHERE 
            listing_url IS NOT NULL 
            AND listing_url LIKE '%/listing/%' 
            AND (viagogo_listing_id IS NULL OR viagogo_listing_id = 0);
        """
        
        remaining = db.execute(remaining_sql, commit=False)
        if remaining and remaining[0]['remaining'] > 0:
            logger.info(f"There are {remaining[0]['remaining']} more listings that could be updated. Run this script again to continue.")
        
    except Exception as e:
        logger.error(f"Error during update process: {str(e)}")
        raise

if __name__ == "__main__":
    update_existing_listings()
