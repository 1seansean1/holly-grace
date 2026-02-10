import { useEffect, useState } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson } from '@/lib/api';
import type { HealthCheck } from '@/types/graph';

interface CircuitBreakerState {
  name: string;
  state: 'closed' | 'open' | 'half_open';
  failure_count: number;
  last_failure?: string;
}

function StatusDot({ healthy }: { healthy: boolean }) {
  return (
    <div
      className={`w-3 h-3 rounded-full ${
        healthy ? 'bg-[var(--color-success)]' : 'bg-[var(--color-error)]'
      } ${healthy ? 'animate-pulse' : ''}`}
    />
  );
}

const CB_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  closed: { bg: 'bg-green-900/40', text: 'text-green-400', label: 'CLOSED' },
  open: { bg: 'bg-red-900/40', text: 'text-red-400', label: 'OPEN' },
  half_open: { bg: 'bg-yellow-900/40', text: 'text-yellow-400', label: 'HALF OPEN' },
};

const SERVICE_ICONS: Record<string, string> = {
  ollama: '🤖',
  postgres: '🐘',
  redis: '⚡',
  chromadb: '🧠',
  api_keys_configured: '🔑',
};

export default function HealthPage() {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [breakers, setBreakers] = useState<CircuitBreakerState[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => {
      fetchJson<HealthCheck>('/api/health')
        .then(setHealth)
        .catch((e) => setError(e.message));
      fetchJson<{ breakers: CircuitBreakerState[] }>('/api/health/circuit-breakers')
        .then((d) => setBreakers(d.breakers ?? []))
        .catch(() => {});
    };
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  const allHealthy = health?.checks
    ? Object.values(health.checks).every(Boolean)
    : false;

  return (
    <div className="flex flex-col h-full">
      <Header title="Health" subtitle="Service status & circuit breakers" />
      <div className="flex-1 overflow-auto p-6 space-y-8">
        {error && (
          <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/40 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* System Status */}
        <section>
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-lg font-semibold">System Status</h2>
            {health && (
              <span
                className={`px-3 py-1 rounded-full text-xs font-bold ${
                  allHealthy
                    ? 'bg-green-900/60 text-green-400'
                    : 'bg-yellow-900/60 text-yellow-400'
                }`}
              >
                {allHealthy ? 'All Systems Healthy' : 'Degraded'}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {health?.checks &&
              Object.entries(health.checks).map(([name, ok]) => (
                <div
                  key={name}
                  className="p-4 rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border)] flex items-center gap-3"
                >
                  <span className="text-xl">{SERVICE_ICONS[name] ?? '🔧'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium capitalize">{name.replace(/_/g, ' ')}</div>
                    <div className="text-xs text-[var(--color-text-muted)]">
                      {ok ? 'Healthy' : 'Unhealthy'}
                    </div>
                  </div>
                  <StatusDot healthy={ok as boolean} />
                </div>
              ))}

            {health?.forge_console && (
              <div className="p-4 rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border)] flex items-center gap-3">
                <span className="text-xl">🖥</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">Forge Console</div>
                  <div className="text-xs text-[var(--color-text-muted)]">{health.forge_console}</div>
                </div>
                <StatusDot healthy={health.forge_console === 'connected'} />
              </div>
            )}
          </div>
        </section>

        {/* Circuit Breakers */}
        {breakers.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-4">Circuit Breakers</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {breakers.map((cb) => {
                const style = CB_STYLES[cb.state] ?? CB_STYLES.closed;
                return (
                  <div
                    key={cb.name}
                    className="p-4 rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border)]"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold">{cb.name}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${style.bg} ${style.text}`}
                      >
                        {style.label}
                      </span>
                    </div>
                    <div className="text-xs text-[var(--color-text-muted)]">
                      Failures: {cb.failure_count}
                    </div>
                    {cb.last_failure && (
                      <div className="text-xs text-[var(--color-text-muted)] mt-1">
                        Last: {new Date(cb.last_failure).toLocaleString()}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Architecture Info */}
        <section>
          <h2 className="text-lg font-semibold mb-4">Architecture</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'LLM Models', value: '4', detail: 'Qwen, GPT-4o, GPT-4o-mini, Opus' },
              { label: 'Scheduled Jobs', value: '6', detail: 'Orders, Instagram, Campaign, Revenue, Health' },
              { label: 'Registered Tools', value: '15', detail: 'Stripe, Shopify, Printful, Instagram, Memory' },
              { label: 'Docker Services', value: '4', detail: 'Postgres, Redis, ChromaDB, Ollama' },
            ].map((item) => (
              <div
                key={item.label}
                className="p-4 rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border)]"
              >
                <div className="text-2xl font-bold text-[var(--color-accent)]">{item.value}</div>
                <div className="text-sm font-medium mt-1">{item.label}</div>
                <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">{item.detail}</div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
