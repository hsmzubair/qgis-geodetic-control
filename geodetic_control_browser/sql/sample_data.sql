-- FICTIONAL demo points around Krakow for testing the plugin. Not real control points.
INSERT INTO gc.control_point (point_no, point_class, height, height_system, status, last_surveyed, description, geom) VALUES
('6612-0001', 'I',   219.874, 'PL-EVRF2007-NH', 'active',    '2024-06-11', 'Demo: market square area',        ST_SetSRID(ST_MakePoint(566341.20, 244712.55), 2180)),
('6612-0002', 'I',   206.112, 'PL-EVRF2007-NH', 'active',    '2024-06-11', 'Demo: river embankment',          ST_SetSRID(ST_MakePoint(565120.88, 243015.10), 2180)),
('6612-0003', 'II',  231.455, 'PL-EVRF2007-NH', 'damaged',   '2023-09-02', 'Demo: monument tilted',           ST_SetSRID(ST_MakePoint(568902.40, 246330.72), 2180)),
('6612-0004', 'II',  245.030, 'PL-KRON86-NH',   'active',    '2019-04-18', 'Demo: legacy height to convert',  ST_SetSRID(ST_MakePoint(571455.15, 247880.03), 2180)),
('6612-0005', 'III', NULL,    NULL,             'active',    '2022-10-27', 'Demo: horizontal-only point',     ST_SetSRID(ST_MakePoint(563870.66, 241995.48), 2180)),
('6612-0006', 'III', 212.700, 'PL-EVRF2007-NH', 'not_found', '2021-05-30', 'Demo: not found at last visit',   ST_SetSRID(ST_MakePoint(569980.02, 240410.91), 2180)),
('6612-0007', 'II',  258.318, 'PL-EVRF2007-NH', 'destroyed', '2020-08-14', 'Demo: destroyed by road works',   ST_SetSRID(ST_MakePoint(574210.33, 245102.64), 2180)),
('6612-0008', 'I',   224.961, 'PL-EVRF2007-NH', 'active',    '2025-03-09', 'Demo: rooftop GNSS station mark', ST_SetSRID(ST_MakePoint(567750.47, 249310.28), 2180))
ON CONFLICT (point_no) DO NOTHING;
