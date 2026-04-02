-- Add procurement_senior role (org-scoped, like other non-system roles)
INSERT INTO kvota.roles (organization_id, slug, name, description, is_system_role)
SELECT '69ff6eda-3fd6-4d24-88b7-a9977c7a08b0', 'procurement_senior', 'Старший закупщик',
       'Закупщик с доступом на просмотр всех этапов КП', false
WHERE NOT EXISTS (
  SELECT 1 FROM kvota.roles
  WHERE slug = 'procurement_senior'
    AND organization_id = '69ff6eda-3fd6-4d24-88b7-a9977c7a08b0'
);
