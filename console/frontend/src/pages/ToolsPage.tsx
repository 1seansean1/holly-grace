import { useEffect, useState, useCallback } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson, postJson } from '@/lib/api';
import type { SchedulerJob } from '@/types/graph';
import type { ToolDefinition } from '@/types/agents';

const CATEGORY_STYLES: Record<string, { border: string; bg: string; accent: string }> = {
  stripe: { border: 'border-violet-500/40', bg: 'bg-violet-950/20', accent: 'text-violet-400' },
  shopify: { border: 'border-green-500/40', bg: 'bg-green-950/20', accent: 'text-green-400' },
  printful: { border: 'border-blue-500/40', bg: 'bg-blue-950/20', accent: 'text-blue-400' },
  instagram: { border: 'border-pink-500/40', bg: 'bg-pink-950/20', accent: 'text-pink-400' },
  memory: { border: 'border-amber-500/40', bg: 'bg-amber-950/20', accent: 'text-amber-400' },
  hierarchy: { border: 'border-cyan-500/40', bg: 'bg-cyan-950/20', accent: 'text-cyan-400' },
  solana: { border: 'border-emerald-500/40', bg: 'bg-emerald-950/20', accent: 'text-emerald-400' },
  app_factory: { border: 'border-sky-500/40', bg: 'bg-sky-950/20', accent: 'text-sky-400' },
  mcp: { border: 'border-slate-500/40', bg: 'bg-slate-950/20', accent: 'text-slate-300' },
};

export default function ToolsPage() {
  const [jobs, setJobs] = useState<SchedulerJob[]>([]);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [triggerResult, setTriggerResult] = useState<{ id: string; ok: boolean } | null>(null);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingTools, setLoadingTools] = useState(true);

  const loadJobs = useCallback(() => {
    setLoadingJobs(true);
    fetchJson<{ jobs: SchedulerJob[] }>('/api/scheduler/jobs')
      .then((d) => setJobs(d.jobs ?? []))
      .catch(() => {})
      .finally(() => setLoadingJobs(false));
  }, []);

  const loadTools = useCallback(() => {
    setLoadingTools(true);
    fetchJson<{ tools: ToolDefinition[] }>('/api/tools')
      .then((d) => setTools(d.tools ?? []))
      .catch(() => setTools([]))
      .finally(() => setLoadingTools(false));
  }, []);

  useEffect(() => {
    loadJobs();
    loadTools();
    const id = setInterval(loadJobs, 30000);
    const id2 = setInterval(loadTools, 60000);
    return () => {
      clearInterval(id);
      clearInterval(id2);
    };
  }, [loadJobs, loadTools]);

  const triggerJob = async (jobId: string) => {
    setTriggering(jobId);
    setTriggerResult(null);
    try {
      await postJson(`/api/scheduler/trigger/${jobId}`, {});
      setTriggerResult({ id: jobId, ok: true });
      loadJobs();
    } catch {
      setTriggerResult({ id: jobId, ok: false });
    }
    setTriggering(null);
    setTimeout(() => setTriggerResult(null), 3000);
  };

  const grouped = tools.reduce(
    (acc, t) => {
      const cat = t.category || 'general';
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(t);
      return acc;
    },
    {} as Record<string, ToolDefinition[]>,
  );

  return (
    <div className="flex flex-col h-full">
      <Header title="Tools & Scheduler" subtitle="Registered tools and autonomous jobs" />
      <div className="flex-1 overflow-auto p-6 space-y-8">
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-lg font-semibold">Scheduled Jobs</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
              {loadingJobs ? '...' : `${jobs.length} active`}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {jobs.map((job) => {
              const isTriggering = triggering === job.id;
              const result = triggerResult?.id === job.id ? triggerResult : null;
              return (
                <div
                  key={job.id}
                  className="p-4 rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border)] flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold">{job.id.replace(/_/g, ' ')}</span>
                    </div>
                    <button
                      onClick={() => triggerJob(job.id)}
                      disabled={isTriggering}
                      className="px-2 py-1 text-[10px] font-semibold rounded bg-[var(--color-accent)]/20 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/30 disabled:opacity-50 transition-colors"
                    >
                      {isTriggering ? 'Running...' : result?.ok ? 'Triggered!' : result && !result.ok ? 'Failed' : 'Trigger'}
                    </button>
                  </div>
                  <div className="text-xs text-[var(--color-text-muted)]">{job.trigger}</div>
                  <div className="text-xs text-[var(--color-text-muted)]">
                    Next: {job.next_run === 'None' ? 'Not scheduled' : new Date(job.next_run).toLocaleString()}
                  </div>
                </div>
              );
            })}
            {!loadingJobs && jobs.length === 0 && (
              <div className="text-sm text-[var(--color-text-muted)] col-span-full p-8 text-center">
                No scheduler data found
              </div>
            )}
          </div>
        </section>

        <section>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-lg font-semibold">Registered Tools</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
              {loadingTools ? '...' : `${tools.length} tools`}
            </span>
          </div>

          {!loadingTools && tools.length === 0 && (
            <div className="text-sm text-[var(--color-text-muted)] p-8 text-center">
              No tools found
            </div>
          )}

          {Object.entries(grouped).map(([category, catTools]) => {
            const style = CATEGORY_STYLES[category] ?? { border: 'border-gray-500/40', bg: 'bg-gray-950/20', accent: 'text-gray-400' };
            return (
              <div key={category} className="mb-6">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className={`text-sm font-semibold ${style.accent}`}>
                    {category}
                  </h3>
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    {catTools.length} tools
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {catTools.map((tool) => (
                    <div
                      key={tool.tool_id}
                      className={`p-3 rounded-lg border ${style.border} ${style.bg}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-xs font-semibold text-[var(--color-text)]">
                          {tool.tool_id}
                        </div>
                        {tool.provider === 'mcp' && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] border border-[var(--color-border)]">
                            mcp
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                        {tool.description}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      </div>
    </div>
  );
}

