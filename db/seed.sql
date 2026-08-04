INSERT INTO orders (order_id, customer, status, total) VALUES
  ('A1001', 'Alice', 'shipped', 129.00),
  ('A1002', 'Bob',   'processing', 59.90)
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO shipments (order_id, carrier, tracking_no, status, eta) VALUES
  ('A1001', 'SF Express', 'SF7788123', 'in_transit', CURRENT_DATE + 2)
ON CONFLICT (order_id) DO NOTHING;
