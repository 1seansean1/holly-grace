import { useState, useEffect, useCallback } from 'react';
import { FlaskConical, Play, CheckCircle, XCircle, RefreshCw, Clock, TrendingUp } from 'lucide-react';

interface EvalSummary {
  suite_id: string;
  total: number;
  passed: number;
  failed: number;
  avg_score: number;
  avg_latency_ms: number;
  total_cost_usd: number;
  run_at: string;
}

interface EvalResult {
  task_id: string;
  passed: boolean;
  score: number;
  latency_ms: number;
  cost_usd: number;
  output_preview: string;
  error: string;
  run_at: string;
}

export default function EvalPage() {
  const [history, setHistory] = useState<EvalSummary[]>([]);
  const [selectedSuite, setSelectedSuite] = useState<string | null>(null);
  const [results, setResults] = useState<EvalResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const fetchHistory = useCallback(async () => {
    try {
      const resp = await fetch('/api/eval/results');
      const data = await resp.json();
      setHistory(data.history || []);
    } catch {
      setHistory([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const fetchResults = async (suiteId: string) => {
    setSelectedSuite(suiteId);
    try {
      const resp = await fetch(`/api/eval/results/${suiteId}`);
      const data = await resp.json();
      setResults(data.results || []);
    } catch {
      setResults([]);
    }
  };

  const runSuite = async () => {
    setRunning(true);
    try {
      const resp = await fetch('/api/eval/run', { method: 'POST' });
      const data = await resp.json();
      if (data.suite_id) {
        await fetchHistory();
        await fetchResults(data.suite_id);
      }
    } catch (err) {
      console.error('Failed to run eval suite:', err);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="shrink-0 px-6 pt-6 pb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FlaskConical size={24} className="text-[var(--color-accent)]" />
          <h1 className="text-xl font-semibold">Golden Evaluation</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={runSuite}
            disabled={running}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] disabled:opacity-50 transition-colors"
          >
            {running ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
            {running ? 'Running...' : 'Run Suite'}
          </button>
          <button
            onClick={fetchHistory}
            className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-6">
      {/* Suite History */}
      <div className="space-y-3">
        <h2 className="text-sm font-medium text-[var(--color-text-muted)]">Suite Runs</h2>
        {loading ? (
          <div className="text-center text-[var(--color-text-muted)] py-8">Loading...</div>
        ) : history.length === 0 ? (
          <div className="text-center py-12">
            <FlaskConical size={48} className="mx-auto mb-4 text-[var(--color-text-muted)] opacity-30" />
            <p className="text-[var(--color-text-muted)]">No evaluation runs yet. Click "Run Suite" to start.</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {history.map(suite => {
              const passRate = suite.total > 0 ? (suite.passed / suite.total) * 100 : 0;
              const isSelected = selectedSuite === suite.suite_id;
              return (
                <button
                  key={suite.suite_id}
                  onClick={() => fetchResults(suite.suite_id)}
                  className={`text-left bg-[var(--color-bg-card)] border rounded-xl p-4 transition-colors ${
                    isSelected
                      ? 'border-[var(--color-accent)] ring-1 ring-[var(--color-accent)]'
                      : 'border-[var(--color-border)] hover:border-[var(--color-text-muted)]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <code className="text-xs text-[var(--color-text-muted)]">{suite.suite_id}</code>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {new Date(suite.run_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                      <div className={`text-lg font-bold ${passRate >= 80 ? 'text-green-400' : passRate >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
                        {passRate.toFixed(0)}%
                      </div>
                      <div className="text-xs text-[var(--color-text-muted)]">pass rate</div>
                    </div>
                    <div className="flex items-center gap-1 text-xs">
                      <CheckCircle size={12} className="text-green-400" /> {suite.passed}
                    </div>
                    <div className="flex items-center gap-1 text-xs">
                      <XCircle size={12} className="text-red-400" /> {suite.failed}
                    </div>
                    <div className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
                      <Clock size={12} /> {suite.avg_latency_ms.toFixed(0)}ms
                    </div>
                    <div className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
                      <TrendingUp size={12} /> ${suite.total_cost_usd.toFixed(4)}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Detail View */}
      {selectedSuite && results.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-[var(--color-text-muted)]">
            Results: <code>{selectedSuite}</code>
          </h2>
          <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-xs text-[var(--color-text-muted)]">
                  <th className="px-4 py-3">Task</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-right">Score</th>
                  <th className="px-4 py-3 text-right">Latency</th>
                  <th className="px-4 py-3">Output / Error</th>
                </tr>
              </thead>
              <tbody>
                {results.map(r => (
                  <tr key={r.task_id} className="border-b border-[var(--color-border)] last:border-b-0 hover:bg-[var(--color-bg-hover)]">
                    <td className="px-4 py-2.5">
                      <code className="text-xs">{r.task_id}</code>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {r.passed
                        ? <CheckCircle size={16} className="inline text-green-400" />
                        : <XCircle size={16} className="inline text-red-400" />
                      }
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs">
                      {((r.score ?? 0) * 100).toFixed(0)}%
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs text-[var(--color-text-muted)]">
                      {(r.latency_ms ?? 0).toFixed(0)}ms
                    </td>
                    <td className="px-4 py-2.5 text-xs text-[var(--color-text-muted)] max-w-xs truncate">
                      {r.error ? (
                        <span className="text-red-400">{r.error}</span>
                      ) : (
                        (r.output_preview ?? '').slice(0, 80)
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
