"use client";

import styles from "./kp-form.module.css";

interface FormHeaderProps {
  onClear: () => void;
  onLoadExample: () => void;
}

export function FormHeader({ onClear, onLoadExample }: FormHeaderProps) {
  const handleClear = () => {
    if (window.confirm("Очистить все поля?")) {
      onClear();
    }
  };
  const handleLoadExample = () => {
    if (window.confirm("Сбросить все поля к примеру по умолчанию?")) {
      onLoadExample();
    }
  };

  return (
    <div className={styles.formHeader}>
      <div>
        <div className={styles.wordmark}>kvotaflow</div>
        <div className={styles.crumbs}>
          КП · Поставка спецтехники · Master Bearing
        </div>
      </div>
      <div className={styles.headerActions}>
        <button
          type="button"
          className={styles.btnOutline}
          onClick={handleClear}
        >
          Очистить
        </button>
        <button
          type="button"
          className={styles.btnOutline}
          onClick={handleLoadExample}
        >
          Пример
        </button>
      </div>
    </div>
  );
}
