const accountsDateFormatter = new Intl.DateTimeFormat('en-US', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'UTC',
});

export function formatUtcDateTime(dateString: string | null): string {
  if (!dateString) return 'Never';
  return `${accountsDateFormatter.format(new Date(dateString))} UTC`;
}
