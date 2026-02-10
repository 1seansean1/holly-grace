import { useEffect, useState, useCallback } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson, postJson } from '@/lib/api';
import type { SchedulerJob } from '@/types/graph';

const TOOLS = [
  { name: 'stripe_create_product', service: 'Stripe', provider: 'stripe', desc: 'Create a new product in Stripe' },
  { name: 'stripe_create_payment_link', service: 'Stripe', provider: 'stripe', desc: 'Generate a payment link' },
  { name: 'stripe_revenue_query', service: 'Stripe', provider: 'stripe', desc: 'Query revenue data' },
  { name: 'stripe_list_products', service: 'Stripe', provider: 'stripe', desc: 'List all products' },
  { name: 'shopify_query_products', service: 'Shopify', provider: 'shopify', desc: 'Search products in store' },
  { name: 'shopify_create_product', service: 'Shopify', provider: 'shopify', desc: 'Create a new product' },
  { name: 'shopify_query_orders', service: 'Shopify', provider: 'shopify', desc: 'Query order history' },
  { name: 'printful_list_catalog', service: 'Printful', provider: 'printful', desc: 'Browse catalog items' },
  { name: 'printful_list_products', service: 'Printful', provider: 'printful', desc: 'List synced products' },
  { name: 'printful_get_store_products', service: 'Printful', provider: 'printful', desc: 'Get store product list' },
  { name: 'printful_order_status', service: 'Printful', provider: 'printful', desc: 'Check order fulfillment' },
  { name: 'instagram_publish_post', service: 'Instagram', provider: 'instagram', desc: 'Publish a social post' },
  { name: 'instagram_get_insights', service: 'Instagram', provider: 'instagram', desc: 'Get engagement metrics' },
  { name: 'memory_store_decision', service: 'ChromaDB', provider: 'chromadb', desc: 'Store decision in memory' },
  { name: 'memory_retrieve_similar', service: 'ChromaDB', provider: 'chromadb', desc: 'Retrieve similar decisions' },
];

const SERVICE_STYLES: Record<string, { border: string; bg: string; icon: string; accent: string }> = {
  stripe: { border: 'border-purple-500/40', bg: 'bg-purple-950/20', icon: '💳', accent: 'text-purple-400' },
  shopify: { border: 'border-green-500/40', bg: 'bg-green-950/20', icon: '🛍', accent: 'text-green-400' },
  printful: { border: 'border-blue-500/40', bg: 'bg-blue-950/20', icon: '👕', accent: 'text-blue-400' },
  instagram: { border: 'border-pink-500/40', bg: 'bg-pink-950/20', icon: '📸', accent: 'text-pink-400' },
  chromadb: { border: 'border-orange-500/40', bg: 'bg-orange-950/20', icon: '🧠', accent: 'text-orange-400' },
};

const JOB_ICONS: Record<string, string> = {
  order_check: '📦',
  instagram_morning: '🌅',
  instagram_afternoon: '🌇',
  weekly_campaign: '📣',
  daily_revenue: '📊',
  health_check: '💓',
};

export default function ToolsPage() {
  const [jobs, setJobs] = useState<SchedulerJob[]>([]);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [triggerResult, setTriggerResult] = useState<{ id: string; ok: boolean } | null>(null);
  const [loadingJobs, setLoadingJobs] = useState(true);

  const loadJobs = useCallback(() => {
    setLoadingJobs(true);
    fetchJson<{ jobs: SchedulerJob[] }>('/api/scheduler/jobs')
      .then((d) => setJobs(d.jobs ?? []))
      .catch(() => {})
      .finally(() => setLoadingJobs(false));
  }, []);

  useEffect(() => {
    loadJobs();
    const id = setInterval(loadJobs, 30000);
    return () => clearInterval(id);
  }, [loadJobs]);

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

  // Group tools by provider
  const grouped = TOOLS.reduce(
    (acc, t) => {
      if (!acc[t.provider]) acc[t.provider] = [];
      acc[t.provider].push(t);
      return acc;
    },
    {} as Record<string, typeof TOOLS>,
  );

  return (
    <div className="flex flex-col h-full">
      <Header title="Tools & Scheduler" subtitle="Registered tools and autonomous jobs" />
      <div className="flex-1 overflow-auto p-6 space-y-8">
        {/* Scheduler */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-lg font-semibold">Scheduled Jobs</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
              {loadingJobs ? '...' : `${jobs.length} active`}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {jobs.map((job) => {
              const icon = JOB_ICONS[job.id] || '⚙';
              const isTriggering = triggering === job.id;
              const result = triggerResult?.id === job.id ? triggerResult : null;
              return (
                <div
                  key={job.id}
                  className="p-4 rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border)] flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{icon}</span>
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

        {/* Tools by Service */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-lg font-semibold">Registered Tools</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
              {TOOLS.length} tools
            </span>
          </div>
          {Object.entries(grouped).map(([provider, tools]) => {
            const style = SERVICE_STYLES[provider] ?? { border: 'border-gray-500/40', bg: 'bg-gray-950/20', icon: '🔧', accent: 'text-gray-400' };
            return (
              <div key={provider} className="mb-6">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-base">{style.icon}</span>
                  <h3 className={`text-sm font-semibold ${style.accent}`}>
                    {tools[0].service}
                  </h3>
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    {tools.length} tools
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {tools.map((tool) => (
                    <div
                      key={tool.name}
                      className={`p-3 rounded-lg border ${style.border} ${style.bg}`}
                    >
                      <div className="text-xs font-semibold text-[var(--color-text)]">
                        {tool.name}
                      </div>
                      <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                        {tool.desc}
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
