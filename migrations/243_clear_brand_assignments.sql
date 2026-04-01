-- Migration: 243_clear_brand_assignments.sql
-- Description: Clear all brand assignment rules to start fresh.
--   Table structure, RLS, and constraints are preserved.
--   Head of procurement will rebuild rules via "Pin brand" in distribution UI.

DELETE FROM kvota.brand_assignments;
