BROWSER TEST
timestamp: 2026-02-24T17:00:00+03:00
session: 2026-02-24 #1
base_url: https://kvotaflow.ru

PRE-REQUISITE: Apply migration 180 before testing:
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -f -" < migrations/180_create_training_videos.sql

TASK: [86afphxzd] Training videos page (/training)
URL: /training

TEST 1: Page accessibility (all roles)
STEPS:
1. Login as admin user
2. Check sidebar — "Обучение" link with play-circle icon should be visible
3. Click "Обучение" in sidebar
4. Page should load with header "База знаний" and "+ Добавить видео" button
5. Check console for errors
EXPECT: Page loads without errors, header visible, admin sees add button

TEST 2: Add video (admin only)
STEPS:
1. On /training page as admin, click "+ Добавить видео"
2. Modal should open with form: Название, YouTube URL, Категория, Описание, Порядок
3. Fill in:
   - Название: "Тестовое видео — создание КП"
   - YouTube URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
   - Категория: "Продажи"
   - Описание: "Демонстрация создания коммерческого предложения"
4. Click "Сохранить"
5. Modal should close, video card should appear in grid
EXPECT: Video card with YouTube embed, "Продажи" badge, title and description

TEST 3: Add second video (different category)
STEPS:
1. Click "+ Добавить видео" again
2. Fill in:
   - Название: "Работа с поставщиками"
   - YouTube URL: dQw4w9WgXcQ (raw ID, not full URL)
   - Категория: "Закупки"
3. Save
EXPECT: Two video cards visible, two category tabs appear ("Продажи", "Закупки")

TEST 4: Category filtering
STEPS:
1. Click "Продажи" tab
2. Only "Тестовое видео — создание КП" card should be visible
3. Click "Закупки" tab
4. Only "Работа с поставщиками" card should be visible
5. Click "Все" tab
6. Both cards visible
EXPECT: HTMX filtering works without page reload

TEST 5: Edit video
STEPS:
1. On any video card, click "Изменить"
2. Modal opens with pre-filled form
3. Change title to "Обновленное название"
4. Save
EXPECT: Card updates with new title, no page reload

TEST 6: Delete video
STEPS:
1. On the edited video card, click "Удалить"
2. Confirm browser dialog
3. Card should disappear from grid
EXPECT: Video removed, grid updates

TEST 7: Non-admin access
STEPS:
1. Login as sales user (non-admin)
2. Navigate to /training
3. Page should load, videos visible
4. NO "+ Добавить видео" button
5. NO "Изменить" / "Удалить" buttons on cards
EXPECT: Read-only view for non-admin users

REPORT_TO: .claude/test-ui-reports/report-20260224-1700-training.md
