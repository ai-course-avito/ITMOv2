-- Units are no longer tied to an IP address.
ALTER TABLE units DROP COLUMN IF EXISTS ip;
