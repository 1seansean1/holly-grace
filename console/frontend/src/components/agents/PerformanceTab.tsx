import { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import { fetchJson } from '@/lib/api';

interface EfficacyRow {
  agent_id: string;
  channel_id: string;
  version: number;
  period_start: string;
  period_end: string;
  invocations: number;
  successes: number;
  failures: number;
  avg_latency_ms: number;
  total_cost_usd: number;
  p_fail: number;
  capacity: number;
}

interface Props {
  agentId: string;
  currentVersion: number;
}

const CHART_HEIGHT = 180;

function formatTime(ts: string): string {
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:00`;
}

export default function PerformanceTab({ agentId, currentVersion }: Props) {
  const [data, setData] = useState<EfficacyRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchJson<{ history: EfficacyRow[] }>(`/api/agents/${agentId}/efficacy?days=30`)
      .then((res) => setData(res.history?.reverse() ?? []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [agentId]);

  if (loading) {
    return <div className="text-xs text-[var(--color-text-muted)] p-4">Loading efficacy data...</div>;
  }

  if (data.length === 0) {
    return (
      <div className="text-xs text-[var(--color-text-muted)] p-4">
        No efficacy data yet. Data is aggregated every 30 minutes from APS observations.
      </div>
    );
  }

  // Find version change points for reference lines
  const versionChanges: string[] = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i].version !== data[i - 1].version) {
      versionChanges.push(formatTime(data[i].period_start));
    }
  }

  const chartData = data.map((row) => ({
    time: formatTime(row.period_start),
    p_fail: row.p_fail,
    latency: Math.round(row.avg_latency_ms),
    cost: row.total_cost_usd,
    invocations: row.invocations,
    version: row.version,
  }));

  // Summary stats
  const totalInvocations = data.reduce((s, r) => s + r.invocations, 0);
  const totalFailures = data.reduce((s, r) => s + r.failures, 0);
  const avgPFail = totalInvocations > 0 ? totalFailures / totalInvocations : 0;
  const avgLatency = totalInvocations > 0
    ? data.reduce((s, r) => s + r.avg_latency_ms * r.invocations, 0) / totalInvocations
    : 0;
  const totalCost = data.reduce((s, r) => s + r.total_cost_usd, 0);

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total Invocations', value: totalInvocations.toLocaleString() },
          { label: 'Avg p(fail)', value: avgPFail.toFixed(4), color: avgPFail < 0.1 ? '#4ade80' : avgPFail < 0.3 ? '#facc15' : '#ef4444' },
          { label: 'Avg Latency', value: `${Math.round(avgLatency)}ms` },
          { label: 'Total Cost', value: `$${totalCost.toFixed(4)}` },
        ].map((stat) => (
          <div key={stat.label} className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
            <div className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">{stat.label}</div>
            <div className="text-lg font-semibold mt-0.5" style={{ color: stat.color ?? 'var(--color-text)' }}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* p(fail) over time */}
      <div>
        <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-2">Failure Rate (p_fail)</div>
        <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#222" />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#888' }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10, fill: '#888' }} domain={[0, 'auto']} />
            <Tooltip
              contentStyle={{ background: '#111', border: '1px solid #333', fontSize: 11 }}
              labelStyle={{ color: '#888' }}
            />
            {versionChanges.map((t, i) => (
              <ReferenceLine key={i} x={t} stroke="#666" strokeDasharray="4 4" label={{ value: 'v', fill: '#666', fontSize: 9 }} />
            ))}
            <Line type="monotone" dataKey="p_fail" stroke="#ef4444" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Latency over time */}
      <div>
        <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-2">Average Latency (ms)</div>
        <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#222" />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#888' }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10, fill: '#888' }} />
            <Tooltip
              contentStyle={{ background: '#111', border: '1px solid #333', fontSize: 11 }}
              labelStyle={{ color: '#888' }}
            />
            {versionChanges.map((t, i) => (
              <ReferenceLine key={i} x={t} stroke="#666" strokeDasharray="4 4" label={{ value: 'v', fill: '#666', fontSize: 9 }} />
            ))}
            <Line type="monotone" dataKey="latency" stroke="#3b82f6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Cost over time */}
      <div>
        <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-2">Cost per Period (USD)</div>
        <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#222" />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#888' }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10, fill: '#888' }} />
            <Tooltip
              contentStyle={{ background: '#111', border: '1px solid #333', fontSize: 11 }}
              labelStyle={{ color: '#888' }}
              formatter={(value: number) => [`$${value.toFixed(6)}`, 'Cost']}
            />
            {versionChanges.map((t, i) => (
              <ReferenceLine key={i} x={t} stroke="#666" strokeDasharray="4 4" label={{ value: 'v', fill: '#666', fontSize: 9 }} />
            ))}
            <Line type="monotone" dataKey="cost" stroke="#a78bfa" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="text-[10px] text-[var(--color-text-muted)]">
        Data from last 30 days. Dashed vertical lines indicate version changes. Aggregated hourly.
      </div>
    </div>
  );
}
