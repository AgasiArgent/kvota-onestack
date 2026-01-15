-- Migration: 001_create_roles_table
-- Description: Create the roles reference table for the workflow system
-- Author: Claude (autonomous session)
-- Date: 2025-01-15

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create roles table
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on code for fast lookups
CREATE INDEX IF NOT EXISTS idx_roles_code ON roles(code);

-- Insert the 9 predefined roles
INSERT INTO roles (code, name, description) VALUES
    ('sales', 'Менеджер по продажам', 'Создание и ведение КП, работа с клиентами'),
    ('procurement', 'Менеджер по закупкам', 'Оценка закупочных цен по брендам'),
    ('logistics', 'Логист', 'Расчёт стоимости и сроков доставки'),
    ('customs', 'Менеджер ТО', 'Таможенное оформление, коды ТН ВЭД, пошлины'),
    ('quote_controller', 'Контроллер КП', 'Проверка КП перед отправкой клиенту'),
    ('spec_controller', 'Контроллер спецификаций', 'Подготовка и проверка спецификаций'),
    ('finance', 'Финансовый менеджер', 'Ведение план-факта по сделкам'),
    ('top_manager', 'Топ-менеджер', 'Согласование и отчётность'),
    ('admin', 'Администратор', 'Управление пользователями и настройками')
ON CONFLICT (code) DO NOTHING;

-- Enable Row Level Security
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;

-- Policy: Allow all authenticated users to read roles (reference data)
CREATE POLICY "roles_select_policy" ON roles
    FOR SELECT
    TO authenticated
    USING (true);

-- Policy: Only admins can modify roles (via service role or admin check)
-- For now, we'll just prevent direct modifications via RLS
-- Modifications should go through admin API with proper checks

-- Add comment to table
COMMENT ON TABLE roles IS 'Reference table for user roles in the workflow system';
COMMENT ON COLUMN roles.code IS 'Unique role identifier used in code';
COMMENT ON COLUMN roles.name IS 'Human-readable role name in Russian';
COMMENT ON COLUMN roles.description IS 'Role description and responsibilities';
