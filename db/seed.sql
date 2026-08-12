-- `customer_id` is the ownership key the tools authorize against: A1001 belongs
-- to Alice (the dev-mode identity, see config.default_customer) and A1002 to
-- Bob — asking for A1002 as Alice must come back "not found", not "denied".
INSERT INTO orders (order_id, tenant_id, customer_id, customer, status, total) VALUES
  ('A1001', 'public', 'Alice', 'Alice', 'shipped', 129.00),
  ('A1002', 'public', 'Bob',   'Bob',   'processing', 59.90)
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO shipments (order_id, carrier, tracking_no, status, eta) VALUES
  ('A1001', 'SF Express', 'SF7788123', 'in_transit', CURRENT_DATE + 2)
ON CONFLICT (order_id) DO NOTHING;
