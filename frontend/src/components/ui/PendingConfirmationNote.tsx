interface PendingConfirmationNoteProps {
  message: string;
  severity: 'info' | 'warning';
  compact?: boolean;
}

function toneClasses(severity: 'info' | 'warning'): string {
  if (severity === 'warning') {
    return 'border-warning/30 bg-warning/10 text-warning';
  }
  return 'border-info/30 bg-info/10 text-info';
}

export function PendingConfirmationNote({
  message,
  severity,
  compact = false,
}: PendingConfirmationNoteProps) {
  return (
    <div className={`rounded-2xl border p-3 ${toneClasses(severity)}`}>
      <p className={`${compact ? 'text-xs' : 'text-sm'} font-medium leading-relaxed`}>{message}</p>
    </div>
  );
}
