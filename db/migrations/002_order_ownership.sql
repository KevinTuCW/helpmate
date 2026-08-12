-- 002 — order ownership columns (non-destructive).
--
-- Before this migration `query_order` / `query_logistics` looked up any
-- order_id with no notion of who was asking: reciting a stranger's order
-- number returned that stranger's status and name. Ownership now lives in the
-- table and is enforced in SQL (see db.get_order / db.get_shipment).
--
-- Apply with:  psql "$DATABASE_URL" -f db/migrations/002_order_ownership.sql

ALTER TABLE orders ADD COLUMN IF NOT EXISTS tenant_id   TEXT NOT NULL DEFAULT 'public';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_id TEXT;

-- Backfill: existing rows are owned by the customer named on them.
UPDATE orders SET customer_id = customer WHERE customer_id IS NULL;

ALTER TABLE orders ALTER COLUMN customer_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS orders_owner_idx ON orders (tenant_id, customer_id);
