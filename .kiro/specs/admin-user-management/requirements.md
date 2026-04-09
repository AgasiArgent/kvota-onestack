# Requirements: Управление пользователями в админке

## Introduction

Администратор системы OneStack должен иметь возможность создавать, редактировать и деактивировать пользователей через UI, без необходимости SSH-доступа и ручного SQL. Управление ролями должно быть атомарным и безопасным (защита от удаления последнего админа, IDOR). Все операции с мульти-таблицами — через Python API (API-first архитектура).

---

## Requirements

### Requirement 1: Создание пользователя

**Objective:** As an admin, I want to создать нового пользователя через форму в интерфейсе, so that я не завишу от разработчика и SSH-доступа для онбординга сотрудников.

#### Acceptance Criteria

1. When администратор нажимает кнопку "Добавить пользователя" на странице `/admin/users`, the Admin Users Page shall отобразить диалог создания пользователя.
2. The Create User Dialog shall содержать поля: email (обязательно), пароль (обязательно, с кнопкой автогенерации и копирования), ФИО (обязательно), роли (чекбоксы, минимум одна), должность (опционально), группа продаж (опционально, только если выбрана роль sales/head_of_sales).
3. When администратор отправляет заполненную форму, the Admin Users API shall создать пользователя в auth.users через `auth.admin.createUser()`, затем INSERT в `organization_members`, `user_profiles` и `user_roles` в рамках одной операции.
4. If email уже существует в системе, the Admin Users API shall вернуть ошибку с человекочитаемым сообщением "Пользователь с таким email уже существует".
5. If один из INSERT'ов после создания auth user завершается ошибкой, the Admin Users API shall удалить созданного auth user (cleanup) и вернуть ошибку.
6. When пользователь успешно создан, the Create User Dialog shall закрыться, а список пользователей обновится автоматически.
7. The Admin Users API endpoint `POST /api/admin/users` shall иметь structured docstring (Path, Params, Returns, Side Effects, Roles).

### Requirement 2: Редактирование профиля пользователя

**Objective:** As an admin, I want to изменять профиль пользователя (ФИО, должность, группа продаж), so that данные сотрудников актуальны без прямого доступа к базе.

#### Acceptance Criteria

1. When администратор кликает на строку пользователя в таблице, the Admin Users Page shall отобразить sheet (выдвижную панель) с данными пользователя.
2. The User Edit Sheet shall показывать: ФИО, email (только чтение), должность, группу продаж, текущие роли, статус (active/suspended).
3. When администратор изменяет ФИО, должность или группу продаж и нажимает "Сохранить", the User Edit Sheet shall обновить `user_profiles` через Supabase direct (простой CRUD, одна таблица).
4. When профиль успешно обновлён, the User Edit Sheet shall показать уведомление об успехе и обновить список пользователей.

### Requirement 3: Атомарное управление ролями

**Objective:** As an admin, I want to изменять роли пользователя атомарно и безопасно, so that не возникает ситуаций с нулевыми ролями или отсутствием админа в системе.

#### Acceptance Criteria

1. When администратор изменяет роли пользователя в User Edit Sheet и нажимает "Сохранить роли", the Admin Users API shall вызвать Postgres-функцию `update_user_roles(p_user_id, p_org_id, p_role_slugs[])`.
2. The Postgres-функция `update_user_roles` shall выполнить DELETE старых + INSERT новых ролей в одной транзакции.
3. If изменение приведёт к удалению роли `admin` у последнего администратора в организации, the Postgres-функция shall отклонить операцию и вернуть ошибку "Невозможно удалить роль admin у последнего администратора".
4. If список ролей пуст (ни одна роль не выбрана), the Admin Users API shall отклонить запрос с ошибкой "Пользователь должен иметь хотя бы одну роль".
5. The Admin Users API endpoint `PATCH /api/admin/users/{id}/roles` shall иметь structured docstring и проверять admin role из JWT.
6. The Admin Users API shall получать `organization_id` из сессии/JWT, а не из тела запроса (защита от IDOR).

### Requirement 4: Деактивация и активация пользователя

**Objective:** As an admin, I want to деактивировать уволенных сотрудников и активировать вернувшихся, so that доступ к системе управляется без удаления данных.

#### Acceptance Criteria

1. When администратор нажимает "Деактивировать" в User Edit Sheet, the Admin Users API shall заблокировать пользователя в Supabase Auth (`auth.admin.updateUserById(id, { ban_duration: 'forever' })`), обновить `organization_members.status` на `suspended` и завершить все активные сессии (`auth.admin.signOut(userId, 'global')`).
2. When администратор нажимает "Активировать" на деактивированном пользователе, the Admin Users API shall разблокировать пользователя в Supabase Auth, обновить `organization_members.status` на `active`.
3. While пользователь находится в статусе `suspended`, the User Edit Sheet shall отображать бейдж "Заблокирован" и кнопку "Активировать" вместо "Деактивировать".
4. The Admin Users API shall запретить деактивацию последнего активного администратора.
5. The Admin Users API endpoint `PATCH /api/admin/users/{id}` shall иметь structured docstring.

### Requirement 5: Отображение статуса в списке пользователей

**Objective:** As an admin, I want to видеть статус каждого пользователя в списке, so that я сразу вижу кто активен, а кто заблокирован.

#### Acceptance Criteria

1. The Users List Table shall отображать колонку "Статус" с бейджами: зелёный "Активен" для `active`, красный "Заблокирован" для `suspended`.
2. The Users List Table shall отображать кнопку "Добавить пользователя" в правом верхнем углу страницы.
3. While данные загружаются, the Users List Table shall показывать skeleton-loading состояние.

### Requirement 6: Безопасность и авторизация

**Objective:** As a system, I want to обеспечить доступ к управлению пользователями только для администраторов, so that нет возможности эскалации привилегий.

#### Acceptance Criteria

1. The Admin Users Page shall быть доступна только пользователям с ролью `admin`; все остальные роли получают redirect на `/quotes`.
2. The Admin Users API shall проверять роль `admin` из JWT на каждом endpoint перед выполнением операции.
3. The Admin Users API shall использовать `createAdminClient()` (service_role key) только на сервере; service_role key никогда не передаётся на клиент.
4. The Server Actions (thin wrappers) shall получать JWT через `apiServerClient` и передавать его в Python API; бизнес-логика в Server Actions отсутствует.
5. The Admin Users API shall логировать все операции создания, изменения ролей и деактивации в stdout (для будущего аудит-лога).

### Requirement 7: Миграция базы данных

**Objective:** As a system, I want to иметь Postgres-функцию для атомарного обновления ролей, so that целостность данных гарантирована на уровне БД.

#### Acceptance Criteria

1. The Migration shall создать функцию `kvota.update_user_roles(p_user_id UUID, p_org_id UUID, p_role_slugs TEXT[])` в схеме `kvota`.
2. The Postgres-функция shall выполнять: DELETE FROM user_roles WHERE user_id = p_user_id AND organization_id = p_org_id, затем INSERT INTO user_roles для каждого slug из массива, в одной транзакции.
3. The Postgres-функция shall проверять: если роль `admin` удаляется и это последний админ в организации, RAISE EXCEPTION с сообщением.
4. The Migration shall быть обратимой (DROP FUNCTION в down-миграции).
