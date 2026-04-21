import { Card, CardContent } from "@/components/ui/card";

/**
 * Empty state shown when a quote has no calculation results yet.
 * Instructs the user to return to the Calculation tab and recalculate.
 */
export function NotCalculated() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
        <h2 className="text-lg font-semibold">Кост-анализ</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          Расчёт ещё не выполнен. Вернитесь на вкладку «Расчёт» и нажмите
          «Рассчитать», чтобы сформировать данные для анализа.
        </p>
      </CardContent>
    </Card>
  );
}
