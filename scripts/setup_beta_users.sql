-- Setup beta users: org membership, roles, profiles
-- Run via: cat scripts/setup_beta_users.sql | ssh beget-kvota "docker exec -i supabase-db psql -U postgres -d postgres"

BEGIN;

-- Helper: get role IDs
DO $$
DECLARE
    org_id uuid := '69ff6eda-3fd6-4d24-88b7-a9977c7a08b0';
    role_org uuid := '77b4c5cf-fcad-4f0d-bac7-4d3322ee44d0';
    r_sales uuid;
    r_procurement uuid;
    r_logistics uuid;
    r_customs uuid;
    r_quote_ctrl uuid;
    r_spec_ctrl uuid;
    r_finance uuid;
    r_head_sales uuid;
    r_head_proc uuid;
    r_head_finance uuid;
    -- department IDs
    d_sales uuid;
    d_procurement uuid;
    d_logistics uuid;
    d_customs uuid;
    d_finance uuid;
    d_control uuid;
    -- group IDs
    g_phmb uuid;
    g_arutsev uuid;
    g_chugrishin uuid;
    g_ponomarev uuid;
    g_procurement uuid;
    -- user IDs
    u_id uuid;
BEGIN
    -- Load role IDs
    SELECT id INTO r_sales FROM kvota.roles WHERE slug = 'sales' AND organization_id = role_org;
    SELECT id INTO r_procurement FROM kvota.roles WHERE slug = 'procurement' AND organization_id = role_org;
    SELECT id INTO r_logistics FROM kvota.roles WHERE slug = 'logistics' AND organization_id = role_org;
    SELECT id INTO r_customs FROM kvota.roles WHERE slug = 'customs' AND organization_id = role_org;
    SELECT id INTO r_quote_ctrl FROM kvota.roles WHERE slug = 'quote_controller' AND organization_id = role_org;
    SELECT id INTO r_spec_ctrl FROM kvota.roles WHERE slug = 'spec_controller' AND organization_id = role_org;
    SELECT id INTO r_finance FROM kvota.roles WHERE slug = 'finance' AND organization_id = role_org;
    SELECT id INTO r_head_sales FROM kvota.roles WHERE slug = 'head_of_sales' AND organization_id = role_org;
    SELECT id INTO r_head_proc FROM kvota.roles WHERE slug = 'head_of_procurement' AND organization_id = role_org;
    SELECT id INTO r_head_finance FROM kvota.roles WHERE slug = 'head_of_finance' AND organization_id = role_org;

    RAISE NOTICE 'Roles: sales=%, proc=%, fin=%, head_sales=%, head_proc=%, head_fin=%',
        r_sales, r_procurement, r_finance, r_head_sales, r_head_proc, r_head_finance;

    -- Load department IDs
    SELECT id INTO d_sales FROM kvota.departments WHERE name = 'Продажи' LIMIT 1;
    SELECT id INTO d_procurement FROM kvota.departments WHERE name = 'Закупки' LIMIT 1;
    SELECT id INTO d_logistics FROM kvota.departments WHERE name = 'Логистика' LIMIT 1;
    SELECT id INTO d_customs FROM kvota.departments WHERE name = 'Таможня' LIMIT 1;
    SELECT id INTO d_finance FROM kvota.departments WHERE name = 'Финансы' LIMIT 1;
    SELECT id INTO d_control FROM kvota.departments WHERE name = 'Контроль' LIMIT 1;

    -- Load group IDs
    SELECT id INTO g_phmb FROM kvota.sales_groups WHERE name = 'PHMB' LIMIT 1;
    SELECT id INTO g_arutsev FROM kvota.sales_groups WHERE name = 'Группа Аруцева' LIMIT 1;
    SELECT id INTO g_chugrishin FROM kvota.sales_groups WHERE name = 'Группа Чугришина' LIMIT 1;
    SELECT id INTO g_ponomarev FROM kvota.sales_groups WHERE name = 'Группа Пономарева' LIMIT 1;
    SELECT id INTO g_procurement FROM kvota.sales_groups WHERE name = 'Закупки общий департамент' LIMIT 1;

    -- ============================================================
    -- 1. Числова Екатерина - procurement + head_of_procurement
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'chislova.e@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_procurement, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_procurement;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_procurement);
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_head_proc);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Числова Екатерина', 'Руководитель отдела закупок', d_procurement, g_procurement)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Числова Екатерина', position = 'Руководитель отдела закупок', department_id = d_procurement, sales_group_id = g_procurement;
    RAISE NOTICE 'OK: Числова Екатерина';

    -- ============================================================
    -- 2. Нагуманова Юлия - procurement
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'nagumanova.u@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_procurement, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_procurement;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_procurement);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Нагуманова Юлия', 'МОЗ', d_procurement, g_procurement)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Нагуманова Юлия', position = 'МОЗ', department_id = d_procurement, sales_group_id = g_procurement;
    RAISE NOTICE 'OK: Нагуманова Юлия';

    -- ============================================================
    -- 3. Давыдова Любовь - sales + head_of_sales
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'lliubov.d@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_sales, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_sales;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_sales);
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_head_sales);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Давыдова Любовь', 'Руководитель группы продаж', d_sales, g_phmb)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Давыдова Любовь', position = 'Руководитель группы продаж', department_id = d_sales, sales_group_id = g_phmb;
    RAISE NOTICE 'OK: Давыдова Любовь';

    -- ============================================================
    -- 4. Рогачёв Денис - sales
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'denis.r@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_sales, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_sales;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_sales);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Рогачёв Денис', 'МОП', d_sales, g_phmb)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Рогачёв Денис', position = 'МОП', department_id = d_sales, sales_group_id = g_phmb;
    RAISE NOTICE 'OK: Рогачёв Денис';

    -- ============================================================
    -- 5. Бармина Анастасия - procurement (group: PHMB)
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'barmina.a@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_procurement, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_procurement;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_procurement);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Бармина Анастасия', 'МОЗ', d_procurement, g_phmb)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Бармина Анастасия', position = 'МОЗ', department_id = d_procurement, sales_group_id = g_phmb;
    RAISE NOTICE 'OK: Бармина Анастасия';

    -- ============================================================
    -- 6. Аруцев Георгий - sales + head_of_sales
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'arutsev.georgiy@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_sales, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_sales;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_sales);
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_head_sales);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Аруцев Георгий', 'Руководитель группы продаж', d_sales, g_arutsev)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Аруцев Георгий', position = 'Руководитель группы продаж', department_id = d_sales, sales_group_id = g_arutsev;
    RAISE NOTICE 'OK: Аруцев Георгий';

    -- ============================================================
    -- 7. Ершов Анатолий - sales
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'anatoliy.e@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_sales, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_sales;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_sales);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Ершов Анатолий', 'МОП', d_sales, g_arutsev)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Ершов Анатолий', position = 'МОП', department_id = d_sales, sales_group_id = g_arutsev;
    RAISE NOTICE 'OK: Ершов Анатолий';

    -- ============================================================
    -- 8. Чугришин Александр - sales + head_of_sales
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'a.chugrishin@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_sales, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_sales;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_sales);
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_head_sales);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Чугришин Александр', 'Руководитель группы продаж', d_sales, g_chugrishin)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Чугришин Александр', position = 'Руководитель группы продаж', department_id = d_sales, sales_group_id = g_chugrishin;
    RAISE NOTICE 'OK: Чугришин Александр';

    -- ============================================================
    -- 9. Гаптукаева Камилла - sales
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'camilla.g@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_sales, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_sales;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_sales);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Гаптукаева Камилла', 'МОП', d_sales, g_chugrishin)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Гаптукаева Камилла', position = 'МОП', department_id = d_sales, sales_group_id = g_chugrishin;
    RAISE NOTICE 'OK: Гаптукаева Камилла';

    -- ============================================================
    -- 10. Пономарев Антон - sales + head_of_sales
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'anton.p@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_sales, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_sales;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_sales);
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_head_sales);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Пономарев Антон', 'Руководитель группы продаж', d_sales, g_ponomarev)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Пономарев Антон', position = 'Руководитель группы продаж', department_id = d_sales, sales_group_id = g_ponomarev;
    RAISE NOTICE 'OK: Пономарев Антон';

    -- ============================================================
    -- 11. Марыныч Сергей - sales
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'sergey.m@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_sales, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_sales;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_sales);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Марыныч Сергей', 'МОП', d_sales, g_ponomarev)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Марыныч Сергей', position = 'МОП', department_id = d_sales, sales_group_id = g_ponomarev;
    RAISE NOTICE 'OK: Марыныч Сергей';

    -- ============================================================
    -- 12. Чариков Роман - sales
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'roman.c@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_sales, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_sales;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_sales);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Чариков Роман', 'МОП', d_sales, g_ponomarev)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Чариков Роман', position = 'МОП', department_id = d_sales, sales_group_id = g_ponomarev;
    RAISE NOTICE 'OK: Чариков Роман';

    -- ============================================================
    -- 13. Сергеева Анастасия - procurement (group: Пономарева)
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'anastasiia.sergeeva@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_procurement, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_procurement;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_procurement);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id, sales_group_id)
    VALUES (u_id, org_id, 'Сергеева Анастасия', 'МОЗ', d_procurement, g_ponomarev)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Сергеева Анастасия', position = 'МОЗ', department_id = d_procurement, sales_group_id = g_ponomarev;
    RAISE NOTICE 'OK: Сергеева Анастасия';

    -- ============================================================
    -- 14. Бисенова Жанна - quote_controller + spec_controller
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'bisenova.zhanna@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_quote_ctrl, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_quote_ctrl;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_quote_ctrl);
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_spec_ctrl);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id)
    VALUES (u_id, org_id, 'Бисенова Жанна', 'Контроль КП / Контроль СП', d_control)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Бисенова Жанна', position = 'Контроль КП / Контроль СП', department_id = d_control;
    RAISE NOTICE 'OK: Бисенова Жанна';

    -- ============================================================
    -- 15. Гук Иван - finance + head_of_finance
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'ivan.guk@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_finance, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_finance;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_finance);
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_head_finance);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id)
    VALUES (u_id, org_id, 'Гук Иван', 'Руководитель отдела финансов', d_finance)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Гук Иван', position = 'Руководитель отдела финансов', department_id = d_finance;
    RAISE NOTICE 'OK: Гук Иван';

    -- ============================================================
    -- 16. Шмелева Екатерина - finance
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'shmeleva.ekaterina@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_finance, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_finance;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_finance);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id)
    VALUES (u_id, org_id, 'Шмелева Екатерина', 'МОФ', d_finance)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Шмелева Екатерина', position = 'МОФ', department_id = d_finance;
    RAISE NOTICE 'OK: Шмелева Екатерина';

    -- ============================================================
    -- 17. Маркин Роман - customs
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'markin.r@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_customs, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_customs;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_customs);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id)
    VALUES (u_id, org_id, 'Маркин Роман', 'МОТ', d_customs)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Маркин Роман', position = 'МОТ', department_id = d_customs;
    RAISE NOTICE 'OK: Маркин Роман';

    -- ============================================================
    -- 18. Князев Олег - customs
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'oleg.k@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_customs, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_customs;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_customs);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id)
    VALUES (u_id, org_id, 'Князев Олег', 'МОТ', d_customs)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Князев Олег', position = 'МОТ', department_id = d_customs;
    RAISE NOTICE 'OK: Князев Олег';

    -- ============================================================
    -- 19. Далелова Милана - logistics
    -- ============================================================
    SELECT id INTO u_id FROM auth.users WHERE email = 'milana.d@masterbearing.ru';
    INSERT INTO kvota.organization_members (organization_id, user_id, role_id, status, is_owner)
    VALUES (org_id, u_id, r_logistics, 'active', false)
    ON CONFLICT (organization_id, user_id) DO UPDATE SET role_id = r_logistics;
    DELETE FROM kvota.user_roles WHERE user_id = u_id AND organization_id = org_id;
    INSERT INTO kvota.user_roles (user_id, organization_id, role_id) VALUES (u_id, org_id, r_logistics);
    INSERT INTO kvota.user_profiles (user_id, organization_id, full_name, position, department_id)
    VALUES (u_id, org_id, 'Далелова Милана', 'МОЛ', d_logistics)
    ON CONFLICT (user_id, organization_id) DO UPDATE SET full_name = 'Далелова Милана', position = 'МОЛ', department_id = d_logistics;
    RAISE NOTICE 'OK: Далелова Милана';

END $$;

COMMIT;
