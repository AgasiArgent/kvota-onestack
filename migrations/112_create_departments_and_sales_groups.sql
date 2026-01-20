-- Migration: 112_create_departments_and_sales_groups
-- Description: Create departments and sales_groups reference tables for user profiles

-- Create departments table
CREATE TABLE IF NOT EXISTS kvota.departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Create index on department name
CREATE INDEX IF NOT EXISTS idx_departments_name ON kvota.departments(name);

-- Create sales_groups table (отделы продаж)
CREATE TABLE IF NOT EXISTS kvota.sales_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Create index on sales_group name
CREATE INDEX IF NOT EXISTS idx_sales_groups_name ON kvota.sales_groups(name);

-- Insert default departments
INSERT INTO kvota.departments (name, description) VALUES
    ('Продажи', 'Отдел продаж'),
    ('Финансы', 'Финансовый отдел'),
    ('Логистика', 'Отдел логистики'),
    ('Закупки', 'Отдел закупок'),
    ('Таможня', 'Отдел таможенного оформления')
ON CONFLICT DO NOTHING;

-- Insert default sales groups (примеры, можно изменить)
INSERT INTO kvota.sales_groups (name, description) VALUES
    ('Отдел продаж 1', 'Первый отдел продаж'),
    ('Отдел продаж 2', 'Второй отдел продаж'),
    ('Отдел продаж 3', 'Третий отдел продаж')
ON CONFLICT DO NOTHING;

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION kvota.update_departments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_departments_updated_at
    BEFORE UPDATE ON kvota.departments
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_departments_updated_at();

CREATE OR REPLACE FUNCTION kvota.update_sales_groups_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_sales_groups_updated_at
    BEFORE UPDATE ON kvota.sales_groups
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_sales_groups_updated_at();

-- RLS policies for departments
ALTER TABLE kvota.departments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view departments"
    ON kvota.departments FOR SELECT
    TO authenticated
    USING (true);

-- RLS policies for sales_groups
ALTER TABLE kvota.sales_groups ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view sales_groups"
    ON kvota.sales_groups FOR SELECT
    TO authenticated
    USING (true);
