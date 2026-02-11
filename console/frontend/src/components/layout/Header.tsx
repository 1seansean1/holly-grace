import type { ReactNode } from 'react';

interface HeaderProps {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}

export default function Header({ title, subtitle, right }: HeaderProps) {
  return (
    <header className="h-12 px-4 border-b border-[var(--color-border)] bg-[var(--color-bg-card)] flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-[var(--color-text)]">{title}</h1>
        {subtitle && (
          <span className="text-xs text-[var(--color-text-muted)]">{subtitle}</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {right}
      </div>
    </header>
  );
}
