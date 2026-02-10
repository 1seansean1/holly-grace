import { useEffect, useState, useCallback } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson } from '@/lib/api';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

interface CostSummary {
  source?: string;
  source_detail?: string;
  total: number;
  today: number;
  week: number;
  month: number;
  by_model: Record<string, number>;
  by_agent: Record<string, number>;
  daily: Record<string, number>;
}

const CHART_COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444'];

function formatCost(cost: number): string {
  if (cost === 0) return '$0.00';
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

export default function CostsPage() {
  const [data, setData] = useState<CostSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const loadCosts = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchJson<CostSummary>(`/api/costs/summary?days=${days}`);
      setData(result);
    } catch {
      setData(null);
    }
    setLoading(false);
  }, [days]);

  useEffect(() => {
    loadCosts();
  }, [loadCosts]);

  const dailyChartData = data?.daily
    ? Object.entries(data.daily).map(([date, cost]) => ({
        date: date.slice(5), // "MM-DD"
        cost: Math.round(cost * 10000) / 10000,
      }))
    : [];

  const modelPieData = data?.by_model
    ? Object.entries(data.by_model)
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name, value: Math.round(value * 10000) / 10000 }))
    : [];

  const agentPieData = data?.by_agent
    ? Object.entries(data.by_agent)
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name, value: Math.round(value * 10000) / 10000 }))
    : [];

  return (
    <div className="flex flex-col h-full">
      <Header title="Costs" subtitle="LLM cost tracking and analysis" />
      <div className="flex items-center gap-3 px-4 py-2 bg-[var(--color-bg-card)] border-b border-[var(--color-border)]">
        <span className="text-xs text-[var(--color-text-muted)]">Period:</span>
        {[7, 30, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className="px-2 py-0.5 text-xs rounded"
            style={{
              background: days === d ? 'var(--color-accent)' : 'transparent',
              color: days === d ? '#fff' : 'var(--color-text-muted)',
              border: days === d ? 'none' : '1px solid var(--color-border)',
            }}
          >
            {d} days
          </button>
        ))}
        {data?.source && (
          <span
            className="ml-2 px-2 py-0.5 rounded text-[10px]"
            style={{
              background: data.source === 'providers' ? '#22c55e22' : '#f59e0b22',
              color: data.source === 'providers' ? '#22c55e' : '#f59e0b',
              border: `1px solid ${data.source === 'providers' ? '#22c55e44' : '#f59e0b44'}`,
            }}
            title={data.source_detail || ''}
          >
            {data.source === 'providers' ? 'Provider Billing' : 'LangSmith Token Data'}
          </span>
        )}
        <button
          onClick={loadCosts}
          className="ml-auto text-xs text-[var(--color-accent)] hover:underline"
        >
          Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-sm text-[var(--color-text-muted)]">
            Loading cost data...
          </div>
        ) : !data ? (
          <div className="flex items-center justify-center h-32 text-sm text-[var(--color-text-muted)]">
            Could not load cost data. Check LangSmith API key.
          </div>
        ) : (
          <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: 'Total', value: data.total, sub: `Last ${days} days` },
                { label: 'Today', value: data.today, sub: 'Current day' },
                { label: 'This Week', value: data.week, sub: 'Last 7 days' },
                { label: 'This Month', value: data.month, sub: `Last ${days} days` },
              ].map((card) => (
                <div
                  key={card.label}
                  className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4"
                >
                  <div className="text-xs text-[var(--color-text-muted)] mb-1">{card.label}</div>
                  <div className="text-xl font-bold text-[var(--color-text)]">
                    {formatCost(card.value)}
                  </div>
                  <div className="text-[10px] text-[var(--color-text-muted)] mt-1">{card.sub}</div>
                </div>
              ))}
            </div>

            {/* Daily Cost Chart */}
            {dailyChartData.length > 0 && (
              <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4">
                <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
                  Daily Cost Trend
                </h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={dailyChartData}>
                    <XAxis
                      dataKey="date"
                      tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }}
                      axisLine={{ stroke: 'var(--color-border)' }}
                    />
                    <YAxis
                      tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }}
                      axisLine={{ stroke: 'var(--color-border)' }}
                      tickFormatter={(v) => `$${v}`}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--color-bg-card)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 8,
                        fontSize: 12,
                        color: 'var(--color-text)',
                      }}
                      formatter={(value: number) => [`$${(value ?? 0).toFixed(4)}`, 'Cost']}
                    />
                    <Bar dataKey="cost" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Pie Charts Row */}
            <div className="grid grid-cols-2 gap-4">
              {/* By Model */}
              {modelPieData.length > 0 && (
                <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
                    Cost by Model
                  </h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={modelPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        dataKey="value"
                        label={({ name, percent }) =>
                          `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`
                        }
                        labelLine={false}
                      >
                        {modelPieData.map((_, i) => (
                          <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value: number) => [`$${value.toFixed(4)}`]} />
                      <Legend
                        wrapperStyle={{ fontSize: 10, color: 'var(--color-text-muted)' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* By Agent */}
              {agentPieData.length > 0 && (
                <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
                    Cost by Agent
                  </h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={agentPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        dataKey="value"
                        label={({ name, percent }) =>
                          `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`
                        }
                        labelLine={false}
                      >
                        {agentPieData.map((_, i) => (
                          <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value: number) => [`$${value.toFixed(4)}`]} />
                      <Legend
                        wrapperStyle={{ fontSize: 10, color: 'var(--color-text-muted)' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Model Cost Table */}
            {Object.keys(data.by_model).length > 0 && (
              <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-4">
                <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
                  Cost Breakdown
                </h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                      <th className="text-left py-2 px-2">Model</th>
                      <th className="text-right py-2 px-2">Cost</th>
                      <th className="text-right py-2 px-2">% of Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.by_model).map(([model, cost]) => (
                      <tr
                        key={model}
                        className="border-b border-[var(--color-border)] last:border-0"
                      >
                        <td className="py-2 px-2 text-[var(--color-text)]">{model}</td>
                        <td className="py-2 px-2 text-right text-[var(--color-text)]">
                          {formatCost(cost)}
                        </td>
                        <td className="py-2 px-2 text-right text-[var(--color-text-muted)]">
                          {data.total > 0
                            ? `${((cost / data.total) * 100).toFixed(1)}%`
                            : '0%'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
