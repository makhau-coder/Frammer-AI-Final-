export function StatusBadge({ status }) {
  const statusClasses = {
    Published: 'bg-success/10 text-success',
    'Not Published': 'bg-muted/20 text-muted-foreground',
  };
  const className = statusClasses[status] || 'bg-muted/20 text-muted-foreground';

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>
      {status}
    </span>
  );
}