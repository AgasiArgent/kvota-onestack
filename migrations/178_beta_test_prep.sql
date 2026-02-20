-- Migration 178: Beta test preparation
-- 1. Add head_of_finance role
-- 2. Cleanup duplicate departments, add Контроль
-- 3. Replace sales_groups with real team names

-- 1. Add head_of_finance role
INSERT INTO kvota.roles (slug, name, description, is_system_role)
VALUES ('head_of_finance', 'Руководитель финансов', 'Руководитель финансового отдела', false)
ON CONFLICT DO NOTHING;

-- 2. Cleanup departments: remove duplicates (keep one per name by MIN id)
DELETE FROM kvota.departments
WHERE id NOT IN (
    SELECT MIN(id) FROM kvota.departments GROUP BY name
);

-- 3. Add "Контроль" department
INSERT INTO kvota.departments (name, description)
VALUES ('Контроль', 'Отдел контроля КП и СП')
ON CONFLICT DO NOTHING;

-- 4. Clear sales_group references from user_profiles before deleting
UPDATE kvota.user_profiles SET sales_group_id = NULL WHERE sales_group_id IS NOT NULL;

-- 5. Delete all old sales_groups
DELETE FROM kvota.sales_groups;

-- 6. Insert real sales groups
INSERT INTO kvota.sales_groups (name, description) VALUES
    ('PHMB', 'Группа PHMB'),
    ('Группа Аруцева', 'Группа продаж Аруцева'),
    ('Группа Чугришина', 'Группа продаж Чугришина'),
    ('Группа Пономарева', 'Группа продаж Пономарева'),
    ('Закупки общий департамент', 'Общий департамент закупок');
