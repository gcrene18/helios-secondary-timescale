-- Count how many records need updating
SELECT COUNT(*) AS records_to_update
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

-- Count how many records still need updating (should be fewer)
SELECT COUNT(*) AS records_still_needing_update
FROM ticket_listings 
WHERE 
    listing_url IS NOT NULL 
    AND listing_url LIKE '%/listing/%' 
    AND (viagogo_listing_id IS NULL OR viagogo_listing_id = 0);

-- Sample of updated records
SELECT 
    listing_id, 
    listing_url, 
    viagogo_listing_id
FROM 
    ticket_listings
WHERE 
    listing_url LIKE '%/listing/%'
    AND viagogo_listing_id IS NOT NULL
ORDER BY 
    listing_id DESC
LIMIT 10;
