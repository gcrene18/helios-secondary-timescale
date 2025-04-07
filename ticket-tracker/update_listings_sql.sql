-- SQL script to update existing listings with viagogo_listing_id extracted from listing_url
-- This will update all listings that have a URL like https://www.stubhub.com/listing/9097446855
-- but don't have a viagogo_listing_id set yet

-- First, let's see how many records need updating
SELECT COUNT(*) 
FROM ticket_listings 
WHERE 
    listing_url IS NOT NULL 
    AND listing_url LIKE '%/listing/%' 
    AND (viagogo_listing_id IS NULL OR viagogo_listing_id = 0);

-- Update the viagogo_listing_id by extracting it from the listing_url
UPDATE ticket_listings
SET viagogo_listing_id = 
    CAST(
        SUBSTRING(
            listing_url FROM '/listing/([0-9]+)'
        ) AS BIGINT
    )
WHERE 
    listing_url IS NOT NULL 
    AND listing_url LIKE '%/listing/%'
    AND (viagogo_listing_id IS NULL OR viagogo_listing_id = 0)
    AND SUBSTRING(listing_url FROM '/listing/([0-9]+)') IS NOT NULL;

-- Verify the update worked by checking how many records still need updating
SELECT COUNT(*) 
FROM ticket_listings 
WHERE 
    listing_url IS NOT NULL 
    AND listing_url LIKE '%/listing/%' 
    AND (viagogo_listing_id IS NULL OR viagogo_listing_id = 0);

-- Check a sample of updated records
SELECT 
    listing_id, 
    listing_url, 
    viagogo_listing_id
FROM 
    ticket_listings
WHERE 
    listing_url LIKE '%/listing/%'
    AND viagogo_listing_id IS NOT NULL
LIMIT 10;
