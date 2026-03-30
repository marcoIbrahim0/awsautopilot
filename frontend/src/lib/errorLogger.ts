type ErrorContext = Record<string, unknown>;

export function logError(error: Error, context: ErrorContext = {}): void {
  // Single integration point so a real SDK can replace console logging later.
  if (process.env.NODE_ENV === 'development') {
    console.error('[errorLogger]', error, context);
    return;
  }

  console.error('[errorLogger]', {
    name: error.name || 'Error',
    message: error.message || 'Unexpected client error',
    context,
  });
}
