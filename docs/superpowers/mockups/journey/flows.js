/* global React, Icon, JOURNEY_DATA */

window.JOURNEY_FLOWS = [
  {
    id: "sales-full",
    title: "Sales: лид → одобрение КП",
    role: "sales",
    persona: "А. Петров · менеджер продаж",
    description: "Полный путь от первого контакта с клиентом до отправки КП на контроль.",
    estMinutes: 12,
    steps: [
      { nodeId: "app:/dashboard", action: "Открыть обзор", note: "Проверка входящих задач на день" },
      { nodeId: "app:/customers", action: "Найти клиента в реестре", note: "Фильтр по статусу «активный»" },
      { nodeId: "app:/customers/[id]", action: "Открыть карточку клиента", note: "Проверка истории заказов и лимита" },
      { nodeId: "app:/quotes", action: "Создать новое КП", note: "Кнопка «+ КП» в шапке реестра" },
      { nodeId: "app:/quotes/[id]", action: "Заполнить позиции", note: "Добавить SKU, указать количество" },
      { nodeId: "app:/quotes/[id]/cost-analysis", action: "Проверить себестоимость", note: "Только для head_of_sales" },
      { nodeId: "app:/quotes/[id]", action: "Отправить на контроль", note: "Статус → pending_quote_control" },
      { nodeId: "app:/tasks", action: "Вернуться к задачам", note: "Ожидание решения контроллёра" },
    ],
  },
  {
    id: "procurement-flow",
    title: "Procurement: распределение → закупка",
    role: "procurement",
    persona: "С. Голиков · закупщик",
    description: "Получение позиций после одобрения КП, работа с поставщиками.",
    estMinutes: 8,
    steps: [
      { nodeId: "app:/procurement/distribution", action: "Получить позиции", note: "Автораспределение по бренду" },
      { nodeId: "app:/procurement/kanban", action: "Открыть канбан", note: "Новые карточки в колонке «RFQ»" },
      { nodeId: "app:/suppliers/[id]", action: "Выбрать поставщика", note: "Сравнение цен и сроков" },
      { nodeId: "app:/quotes/[id]", action: "Внести цены закупки", note: "В валюте поставщика" },
    ],
  },
  {
    id: "qa-onboarding",
    title: "QA onboarding: 5 ключевых экранов",
    role: "spec_controller",
    persona: "Junior QA · первая неделя",
    description: "Минимальный набор для проверки основных потоков после онбординга.",
    estMinutes: 15,
    steps: [
      { nodeId: "app:/quotes", action: "Реестр КП", note: "6 пинов — фильтры, сортировка, действия" },
      { nodeId: "app:/quotes/[id]", action: "Карточка КП", note: "22 пина — весь workflow" },
      { nodeId: "app:/customers/[id]", action: "Карточка клиента", note: "14 пинов — вкладки, CRM" },
      { nodeId: "app:/procurement/distribution", action: "Распределение", note: "7 пинов" },
      { nodeId: "app:/finance", action: "Контроль платежей", note: "10 пинов" },
    ],
  },
  {
    id: "finance-monthly",
    title: "Finance: месячное закрытие",
    role: "finance",
    persona: "Н. Соколова · финансист",
    description: "Ежемесячный контроль платежей и календарь.",
    estMinutes: 6,
    steps: [
      { nodeId: "app:/finance", action: "Открыть контроль платежей", note: "" },
      { nodeId: "app:/payments/calendar", action: "Календарь на месяц", note: "Планирование cash-flow" },
      { nodeId: "app:/dashboard", action: "Сверить с обзором", note: "" },
    ],
  },
];
