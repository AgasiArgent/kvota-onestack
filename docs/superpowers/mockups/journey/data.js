/* Mock journey manifest + annotation data for /journey mockups */

window.JOURNEY_DATA = (function () {
  const clusters = [
    { id: "main", label: "Главное", color: "#57534E" },
    { id: "customers", label: "Клиенты", color: "#0F766E" },
    { id: "quotes", label: "Коммерческие предложения", color: "#C2410C" },
    { id: "procurement", label: "Закупки", color: "#9A3412" },
    { id: "finance", label: "Финансы", color: "#059669" },
    { id: "admin", label: "Администрирование", color: "#6D28D9" },
  ];

  const roles = [
    "admin", "top_manager",
    "sales", "sales_manager", "head_of_sales",
    "procurement", "procurement_senior", "head_of_procurement",
    "logistics", "head_of_logistics",
    "customs", "finance",
    "quote_controller", "spec_controller", "currency_controller",
  ];

  // 16 nodes — a representative slice of the 34-route set
  const nodes = [
    // main
    { id: "app:/dashboard", route: "/dashboard", title: "Обзор", cluster: "main", roles: ["top_manager", "sales", "head_of_sales", "procurement", "logistics", "finance"], stories: 4, impl: "done", qa: "verified", qaCount: [6, 6], feedback: 2, training: 3, parent: null },
    { id: "app:/tasks", route: "/tasks", title: "Мои задачи", cluster: "main", roles: ["sales", "procurement", "logistics", "customs", "finance"], stories: 7, impl: "done", qa: "verified", qaCount: [8, 8], feedback: 0, training: 5, parent: null },
    { id: "app:/messages", route: "/messages", title: "Сообщения", cluster: "main", roles: ["admin", "top_manager", "sales", "procurement"], stories: 2, impl: "partial", qa: "untested", qaCount: [0, 3], feedback: 1, training: 0, parent: null },

    // customers
    { id: "app:/customers", route: "/customers", title: "Клиенты", cluster: "customers", roles: ["sales", "sales_manager", "top_manager", "head_of_sales"], stories: 5, impl: "done", qa: "verified", qaCount: [9, 9], feedback: 3, training: 2, parent: null },
    { id: "app:/customers/[id]", route: "/customers/[id]", title: "Карточка клиента", cluster: "customers", roles: ["sales", "sales_manager", "head_of_sales", "top_manager"], stories: 12, impl: "done", qa: "broken", qaCount: [11, 14], feedback: 6, training: 8, parent: "app:/customers" },

    // quotes
    { id: "app:/quotes", route: "/quotes", title: "Коммерческие предложения", cluster: "quotes", roles: ["sales", "sales_manager", "head_of_sales", "top_manager", "procurement", "logistics", "customs", "finance"], stories: 8, impl: "done", qa: "verified", qaCount: [12, 12], feedback: 5, training: 4, parent: null },
    { id: "app:/quotes/[id]", route: "/quotes/[id]", title: "Карточка предложения", cluster: "quotes", roles: ["admin", "sales", "head_of_sales", "procurement", "head_of_procurement", "logistics", "customs", "quote_controller"], stories: 21, impl: "done", qa: "broken", qaCount: [17, 22], feedback: 9, training: 11, parent: "app:/quotes" },
    { id: "app:/quotes/[id]/cost-analysis", route: "/quotes/[id]/cost-analysis", title: "Анализ себестоимости", cluster: "quotes", roles: ["admin", "head_of_sales", "top_manager", "finance"], stories: 3, impl: "partial", qa: "untested", qaCount: [1, 5], feedback: 0, training: 0, parent: "app:/quotes/[id]" },
    { id: "app:/quotes/trash", route: "/quotes/trash", title: "Корзина", cluster: "quotes", roles: ["admin"], stories: 1, impl: "done", qa: "verified", qaCount: [2, 2], feedback: 0, training: 0, parent: "app:/quotes" },

    // procurement
    { id: "app:/procurement/distribution", route: "/procurement/distribution", title: "Распределение позиций", cluster: "procurement", roles: ["head_of_procurement", "procurement_senior"], stories: 6, impl: "partial", qa: "broken", qaCount: [4, 7], feedback: 4, training: 3, parent: null },
    { id: "app:/procurement/kanban", route: "/procurement/kanban", title: "Канбан закупок", cluster: "procurement", roles: ["procurement", "procurement_senior", "head_of_procurement"], stories: 4, impl: "done", qa: "verified", qaCount: [5, 5], feedback: 1, training: 2, parent: null },
    { id: "app:/suppliers/[id]", route: "/suppliers/[id]", title: "Карточка поставщика", cluster: "procurement", roles: ["procurement", "procurement_senior", "head_of_procurement"], stories: 5, impl: "done", qa: "untested", qaCount: [0, 6], feedback: 0, training: 0, parent: null },

    // finance
    { id: "app:/finance", route: "/finance", title: "Контроль платежей", cluster: "finance", roles: ["finance", "top_manager", "currency_controller"], stories: 9, impl: "done", qa: "verified", qaCount: [10, 10], feedback: 2, training: 5, parent: null },
    { id: "app:/payments/calendar", route: "/payments/calendar", title: "Календарь платежей", cluster: "finance", roles: ["finance", "top_manager"], stories: 3, impl: "done", qa: "verified", qaCount: [4, 4], feedback: 1, training: 1, parent: null },

    // admin
    { id: "app:/admin/users", route: "/admin/users", title: "Пользователи", cluster: "admin", roles: ["admin"], stories: 4, impl: "done", qa: "verified", qaCount: [5, 5], feedback: 0, training: 1, parent: null },
    { id: "app:/admin/feedback", route: "/admin/feedback", title: "Обращения", cluster: "admin", roles: ["admin"], stories: 3, impl: "done", qa: "verified", qaCount: [4, 4], feedback: 0, training: 0, parent: null },

    // ghosts
    { id: "ghost:revision-history", route: "/quotes/[id]/revisions", title: "История ревизий КП", cluster: "quotes", roles: ["admin", "quote_controller", "head_of_sales"], stories: 3, impl: "missing", qa: "untested", qaCount: [0, 0], feedback: 0, training: 0, parent: "app:/quotes/[id]", ghost: true, plannedIn: "phase-7a#revisions", assignee: "Илья Б." },
    { id: "ghost:customer-deals-dashboard", route: "/customers/[id]/deals", title: "Сделки клиента — дашборд", cluster: "customers", roles: ["sales", "head_of_sales"], stories: 2, impl: "missing", qa: "untested", qaCount: [0, 0], feedback: 0, training: 0, parent: "app:/customers/[id]", ghost: true, plannedIn: "phase-7b#deals-dash" },
    { id: "ghost:bulk-export", route: "/quotes/export", title: "Массовый экспорт в Excel", cluster: "quotes", roles: ["admin", "top_manager", "finance"], stories: 1, impl: "missing", qa: "untested", qaCount: [0, 0], feedback: 0, training: 0, parent: "app:/quotes", ghost: true, plannedIn: "backlog" },
  ];

  const edges = [
    { from: "app:/customers", to: "app:/customers/[id]" },
    { from: "app:/quotes", to: "app:/quotes/[id]" },
    { from: "app:/quotes", to: "app:/quotes/trash" },
    { from: "app:/quotes/[id]", to: "app:/quotes/[id]/cost-analysis" },
    { from: "app:/quotes/[id]", to: "ghost:revision-history", ghost: true },
    { from: "app:/customers/[id]", to: "ghost:customer-deals-dashboard", ghost: true },
    { from: "app:/quotes", to: "ghost:bulk-export", ghost: true },
  ];

  // Detail for the focused node (quotes/[id]) — drawer + annotated mode
  const focusNodeId = "app:/quotes/[id]";

  const stories = [
    { ref: "phase-5b#3", actor: "sales", goal: "вижу полную разбивку себестоимости по позициям", spec: "phase-5b-quote-composition/stories.md" },
    { ref: "phase-5b#7", actor: "procurement", goal: "заполняю цены закупки в валюте поставщика", spec: "phase-5b-quote-composition/stories.md" },
    { ref: "phase-5b#12", actor: "quote_controller", goal: "валидирую расчёт и одобряю КП", spec: "phase-5b-quote-composition/stories.md" },
    { ref: "phase-6b#4", actor: "logistics", goal: "вношу ставки фрахта и срок доставки", spec: "phase-6b-logistics/stories.md" },
    { ref: "phase-6c#2", actor: "customs", goal: "подбираю ТН ВЭД и рассчитываю пошлины", spec: "phase-6c-customs/stories.md" },
  ];

  const pins = [
    { n: 1, selector: "[data-testid='quote-status-rail']", x: 0.06, y: 0.18, mode: "qa", expected: "Активный шаг подсвечен копером; завершённые — галочкой; недоступные по роли — приглушены", verified: true, story: "phase-5b#3", history: [{ when: "2026-04-21 14:22", who: "qa-spec_controller@", result: "verified" }] },
    { n: 2, selector: "[data-testid='stage-deadline-banner']", x: 0.40, y: 0.10, mode: "qa", expected: "Показывает дедлайн текущего этапа; красный если просрочен > 24ч", verified: false, broken: false, story: "phase-5b#12", history: [{ when: "2026-04-18 09:10", who: "qa-quote_controller@", result: "broken", note: "не реагирует на просрочку" }] },
    { n: 3, selector: "[data-testid='item-price-input']", x: 0.38, y: 0.46, mode: "qa", expected: "Цена вводится в валюте поставщика; пересчёт в валюту КП — в подсказке", verified: true, story: "phase-5b#7" },
    { n: 4, selector: ".context-panel__customer-link", x: 0.80, y: 0.22, mode: "qa", expected: "Клик по имени клиента открывает карточку в новой вкладке", broken: true, story: "phase-5b#3", history: [{ when: "2026-04-19 11:02", who: "qa-quote_controller@", result: "broken", note: "селектор пустой" }] },
    { n: 5, selector: "[data-action='approve-quote']", x: 0.88, y: 0.76, mode: "training", stepOrder: 3, expected: "Кнопка 'Одобрить' — только при статусе pending_quote_control, требует подтверждение", story: "phase-5b#12" },
    { n: 6, selector: "[data-testid='chat-panel-toggle']", x: 0.94, y: 0.10, mode: "qa", expected: "Открывает правую панель чата; состояние сохраняется в URL ?chat=1", verified: true },
  ];

  const feedback = [
    { id: "fb-1247", author: "А. Петров", role: "sales", when: "2 дня назад", body: "На высоких разрешениях статус-рейл налезает на хлебные крошки" },
    { id: "fb-1251", author: "М. Иванова", role: "quote_controller", when: "вчера", body: "После одобрения КП кнопка 'Одобрить' иногда остаётся активной 1-2 сек" },
    { id: "fb-1259", author: "С. Голиков", role: "procurement", when: "3 часа назад", body: "При вводе цены с 6-ю знаками после запятой появляется горизонтальный скролл" },
    { id: "fb-1260", author: "И. Новикова", role: "logistics", when: "1 час назад", body: "Не хватает фильтра по инкотермс в шапке карточки" },
  ];

  const training = [
    { n: 1, title: "Откройте карточку КП из реестра", body: "Перейдите в _Коммерческие предложения_, найдите нужный КП и кликните по номеру." },
    { n: 2, title: "Переключитесь на шаг 'Закупки'", body: "В левом статус-рейле нажмите шаг **Закупки**. Доступен, если у вас роль `procurement` или выше." },
    { n: 3, title: "Заполните цены закупки", body: "В таблице позиций введите цену в валюте поставщика. Пересчёт в рубли появится в подсказке." },
    { n: 4, title: "Отправьте на контроль", body: "По готовности — кнопка **Отправить на контроль КП** внизу. Статус сменится на `pending_quote_control`." },
  ];

  return { clusters, roles, nodes, edges, focusNodeId, stories, pins, feedback, training };
})();
