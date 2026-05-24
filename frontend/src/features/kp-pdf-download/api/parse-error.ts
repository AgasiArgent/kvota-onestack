/**
 * Maps backend error codes to the user-facing toast copy specified in
 * REQ-19. The mapping is deliberately small — three known codes plus an
 * unknown-code fallback — so adding a new error class on the backend
 * surfaces visibly here rather than silently rendering "Unknown error".
 */

export interface ParsedError {
  code: string;
  message: string;
  requestId?: string;
}

export function parseErrorMessage(err: ParsedError): string {
  switch (err.code) {
    case "UNAUTHORIZED":
      return "Сессия истекла, перезагрузите страницу";
    case "VALIDATION_ERROR":
      // REQ-19.2: surface the server's message verbatim so the user knows
      // which field tripped validation.
      return err.message || "Некорректные данные формы";
    case "RENDER_ERROR": {
      const tail = err.requestId ? ` (ID: ${err.requestId})` : "";
      return `Не удалось сгенерировать PDF, попробуйте ещё раз${tail}`;
    }
    default:
      return err.message || "Не удалось сгенерировать PDF";
  }
}
