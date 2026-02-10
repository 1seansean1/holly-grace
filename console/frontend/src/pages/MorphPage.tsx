import { useState, useEffect, useCallback } from 'react';
import {
  Dna,
  RefreshCw,
  Play,
  Target,
  Zap,
  Brain,
  Layers,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  ArrowUpRight,
  Activity,
  Pencil,
  Plus,
  RotateCcw,
  Settings,
  ChevronDown,
  ChevronRight,
  Save,
  Trash2,
  X,
} from 'lucide-react';

interface Snapshot {
  snapshot_at: string;
  ai_proxy: number;
  clc_horizon: number;
  clc_dimensions: number;
  eta_mean: number;
  cp_profile: Record<string, number>;
  p_feasible_count: number;
  attractor_count: number;
  spec_gap_mean: number;
  competency_dist: Record<string, number>;
  tier_usage: Record<string, number>;
  total_reuse: number;
}

interface GoalStatus {
  goal_id: string;
  display_name: string;
  formalization_level: string;
  failure_predicate: string;
  g0_description: string;
  epsilon_g: number;
  horizon_t: number;
  observation_map: string[];
  primary_tier: number;
  priority: number;
  satisfied: boolean | null;
  channel_status: Record<string, { p_fail: number; within_tolerance: boolean }>;
}

interface CascadeEvent {
  cascade_id: string;
  goal_id: string;
  channel_id: string;
  trigger_p_fail: number;
  trigger_epsilon: number;
  tier_attempted: number;
  tier_succeeded: number | null;
  outcome: string;
  adaptation: Record<string, unknown>;
  created_at: string;
}

interface CompetencyData {
  competencies: Array<{
    competency_id: string;
    tier: number;
    competency_type: string;
    channel_id: string;
    reuse_count: number;
    success_rate: number;
    assembly_index: number;
  }>;
  distribution: Record<string, number>;
  count: number;
}

interface CascadeConfig {
  min_observations: number;
  delta: number;
  max_tier0_attempts: number;
  max_tier1_attempts: number;
  cascade_timeout_seconds: number;
  tier0_enabled: boolean;
  tier1_enabled: boolean;
  tier2_enabled: boolean;
  tier3_enabled: boolean;
  tier2_auto_approve: boolean;
  tier3_auto_approve: boolean;
}

interface GoalDraft {
  goal_id: string;
  display_name: string;
  failure_predicate: string;
  epsilon_g: number;
  horizon_t: number;
  observation_map: string[];
  primary_tier: number;
  priority: number;
  formalization_level: string;
  g0_description: string;
}

const CHANNELS = ['K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7'];
const TIERS = [
  { value: 0, label: 'T0: Parameter Tuning' },
  { value: 1, label: 'T1: Goal Retargeting' },
  { value: 2, label: 'T2: Boundary Expansion' },
  { value: 3, label: 'T3: Scale Reorganization' },
];
const LEVELS = [
  { value: 'g0_preference', label: 'G\u2070 Preference' },
  { value: 'g1_spec', label: 'G\u00B9 Specification' },
  { value: 'g2_implementation', label: 'G\u00B2 Implementation' },
];

function MetricCard({
  label,
  value,
  icon: Icon,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  sub?: string;
  accent?: 'green' | 'amber' | 'red' | 'blue';
}) {
  const accentColor = {
    green: 'text-green-400',
    amber: 'text-amber-400',
    red: 'text-red-400',
    blue: 'text-blue-400',
  }[accent || 'blue'];

  return (
    <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-[var(--color-text-muted)]" />
        <span className="text-xs text-[var(--color-text-muted)]">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${accentColor}`}>{value}</div>
      {sub && <div className="text-xs text-[var(--color-text-muted)] mt-1">{sub}</div>}
    </div>
  );
}

function TierBadge({ tier }: { tier: number }) {
  const colors = ['bg-blue-500/20 text-blue-400', 'bg-cyan-500/20 text-cyan-400', 'bg-amber-500/20 text-amber-400', 'bg-red-500/20 text-red-400'];
  const labels = ['T0: Param', 'T1: Retarget', 'T2: Expand', 'T3: Reorg'];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${colors[tier] || colors[0]}`}>
      {labels[tier] || `T${tier}`}
    </span>
  );
}

function OutcomeBadge({ outcome }: { outcome: string }) {
  const map: Record<string, { color: string; label: string }> = {
    success: { color: 'bg-green-500/20 text-green-400', label: 'Success' },
    cache_hit: { color: 'bg-blue-500/20 text-blue-400', label: 'Cache Hit' },
    failure: { color: 'bg-red-500/20 text-red-400', label: 'Failed' },
    approval_pending: { color: 'bg-amber-500/20 text-amber-400', label: 'Pending' },
  };
  const d = map[outcome] || { color: 'bg-gray-500/20 text-gray-400', label: outcome };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${d.color}`}>
      {d.label}
    </span>
  );
}

function ToggleSwitch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center justify-between cursor-pointer">
      <span className="text-xs text-[var(--color-text)]">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors ${
          checked ? 'bg-[var(--color-accent)]' : 'bg-[var(--color-bg-hover)]'
        }`}
      >
        <span className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-4' : 'translate-x-0'
        }`} />
      </button>
    </label>
  );
}

// ========================================================================
// Goal Edit Modal
// ========================================================================

function GoalEditModal({
  draft,
  isNew,
  onSave,
  onDelete,
  onClose,
}: {
  draft: GoalDraft;
  isNew: boolean;
  onSave: (goal: GoalDraft) => void;
  onDelete?: () => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<GoalDraft>({ ...draft });

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);
  const [channelInput, setChannelInput] = useState<Record<string, boolean>>(
    Object.fromEntries(CHANNELS.map(c => [c, draft.observation_map.includes(c)]))
  );

  const handleChannelToggle = (ch: string) => {
    const next = { ...channelInput, [ch]: !channelInput[ch] };
    setChannelInput(next);
    setForm({ ...form, observation_map: CHANNELS.filter(c => next[c]) });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold">{isNew ? 'Create Goal' : `Edit: ${draft.display_name}`}</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-[var(--color-bg-hover)]"><X size={16} /></button>
        </div>

        <div className="space-y-3">
          {isNew && (
            <div>
              <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Goal ID</label>
              <input
                value={form.goal_id}
                onChange={e => setForm({ ...form, goal_id: e.target.value })}
                className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg"
                placeholder="e.g. my_custom_goal"
              />
            </div>
          )}

          <div>
            <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Display Name</label>
            <input
              value={form.display_name}
              onChange={e => setForm({ ...form, display_name: e.target.value })}
              className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Epsilon (Failure Tolerance)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={form.epsilon_g}
                onChange={e => setForm({ ...form, epsilon_g: parseFloat(e.target.value) || 0 })}
                className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg"
              />
            </div>
            <div>
              <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Horizon T (seconds)</label>
              <input
                type="number"
                min="60"
                value={form.horizon_t}
                onChange={e => setForm({ ...form, horizon_t: parseInt(e.target.value) || 3600 })}
                className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Primary Tier</label>
              <select
                value={form.primary_tier}
                onChange={e => setForm({ ...form, primary_tier: parseInt(e.target.value) })}
                className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg"
              >
                {TIERS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Priority (1-10)</label>
              <input
                type="number"
                min="1"
                max="10"
                value={form.priority}
                onChange={e => setForm({ ...form, priority: parseInt(e.target.value) || 5 })}
                className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg"
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Failure Predicate</label>
            <input
              value={form.failure_predicate}
              onChange={e => setForm({ ...form, failure_predicate: e.target.value })}
              className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg"
              placeholder="e.g. p_fail, latency_exceed, cost_exceed"
            />
          </div>

          <div>
            <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Formalization Level</label>
            <select
              value={form.formalization_level}
              onChange={e => setForm({ ...form, formalization_level: e.target.value })}
              className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg"
            >
              {LEVELS.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Observation Channels</label>
            <div className="flex flex-wrap gap-2">
              {CHANNELS.map(ch => (
                <button
                  key={ch}
                  type="button"
                  onClick={() => handleChannelToggle(ch)}
                  className={`px-2.5 py-1 text-xs rounded-lg border transition-colors ${
                    channelInput[ch]
                      ? 'bg-[var(--color-accent)] text-white border-[var(--color-accent)]'
                      : 'bg-[var(--color-bg-card)] text-[var(--color-text-muted)] border-[var(--color-border)] hover:border-[var(--color-accent)]'
                  }`}
                >
                  {ch}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">G0 Description</label>
            <textarea
              value={form.g0_description}
              onChange={e => setForm({ ...form, g0_description: e.target.value })}
              rows={2}
              className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg resize-none"
              placeholder="Informal intent description..."
            />
          </div>
        </div>

        <div className="flex items-center justify-between mt-5 pt-4 border-t border-[var(--color-border)]">
          <div>
            {!isNew && onDelete && (
              <button
                onClick={onDelete}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
              >
                <Trash2 size={12} /> Delete
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="px-4 py-1.5 text-xs border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-bg-hover)]">
              Cancel
            </button>
            <button
              onClick={() => onSave(form)}
              className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium bg-[var(--color-accent)] text-white rounded-lg hover:bg-[var(--color-accent-hover)]"
            >
              <Save size={12} /> {isNew ? 'Create' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ========================================================================
// Main Page
// ========================================================================

export default function MorphPage() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [goals, setGoals] = useState<GoalStatus[]>([]);
  const [cascades, setCascades] = useState<CascadeEvent[]>([]);
  const [assembly, setAssembly] = useState<CompetencyData | null>(null);
  const [cascadeConfig, setCascadeConfig] = useState<CascadeConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // Goal editing state
  const [editingGoal, setEditingGoal] = useState<GoalDraft | null>(null);
  const [isNewGoal, setIsNewGoal] = useState(false);

  // Cascade settings state
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [configDraft, setConfigDraft] = useState<CascadeConfig | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const fetchAll = useCallback(async () => {
    try {
      const [snapResp, goalsResp, cascResp, asmResp, cfgResp] = await Promise.all([
        fetch('/api/morphogenetic/snapshot'),
        fetch('/api/morphogenetic/goals'),
        fetch('/api/morphogenetic/cascade'),
        fetch('/api/morphogenetic/assembly'),
        fetch('/api/morphogenetic/cascade/config'),
      ]);

      const snapData = await snapResp.json();
      const goalsData = await goalsResp.json();
      const cascData = await cascResp.json();
      const asmData = await asmResp.json();
      const cfgData = await cfgResp.json();

      setSnapshot(snapData);
      setGoals(goalsData.goals || []);
      setCascades(cascData.events || []);
      setAssembly(asmData);
      setCascadeConfig(cfgData);
      setConfigDraft(cfgData);
    } catch {
      // Endpoints may not be available yet
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const runEvaluation = async () => {
    setEvaluating(true);
    try {
      const resp = await fetch('/api/morphogenetic/evaluate', { method: 'POST' });
      const data = await resp.json();
      if (data.snapshot) {
        setSnapshot(data.snapshot);
      }
      await fetchAll();
    } catch (err) {
      console.error('Failed to run morphogenetic evaluation:', err);
    } finally {
      setEvaluating(false);
    }
  };

  // ----- Goal CRUD handlers -----

  const handleEditGoal = (goal: GoalStatus) => {
    setEditingGoal({
      goal_id: goal.goal_id,
      display_name: goal.display_name,
      failure_predicate: goal.failure_predicate || 'p_fail',
      epsilon_g: goal.epsilon_g,
      horizon_t: goal.horizon_t,
      observation_map: goal.observation_map,
      primary_tier: goal.primary_tier,
      priority: goal.priority,
      formalization_level: goal.formalization_level,
      g0_description: goal.g0_description || '',
    });
    setIsNewGoal(false);
  };

  const handleNewGoal = () => {
    setEditingGoal({
      goal_id: '',
      display_name: '',
      failure_predicate: 'p_fail',
      epsilon_g: 0.1,
      horizon_t: 3600,
      observation_map: ['K1'],
      primary_tier: 0,
      priority: 5,
      formalization_level: 'g1_spec',
      g0_description: '',
    });
    setIsNewGoal(true);
  };

  const handleSaveGoal = async (goal: GoalDraft) => {
    try {
      const url = isNewGoal ? '/api/morphogenetic/goals' : `/api/morphogenetic/goals/${goal.goal_id}`;
      const method = isNewGoal ? 'POST' : 'PUT';
      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(goal),
      });
      if (resp.ok) {
        showToast(isNewGoal ? `Goal "${goal.display_name}" created` : `Goal "${goal.display_name}" updated`);
        setEditingGoal(null);
        await fetchAll();
      } else {
        const err = await resp.json();
        showToast(`Error: ${err.error || 'Unknown'}`);
      }
    } catch {
      showToast('Failed to save goal');
    }
  };

  const handleDeleteGoal = async () => {
    if (!editingGoal) return;
    if (!window.confirm(`Delete goal "${editingGoal.display_name}"? This cannot be undone.`)) return;
    try {
      const resp = await fetch(`/api/morphogenetic/goals/${editingGoal.goal_id}`, { method: 'DELETE' });
      if (resp.ok) {
        showToast(`Goal "${editingGoal.display_name}" deleted`);
        setEditingGoal(null);
        await fetchAll();
      }
    } catch {
      showToast('Failed to delete goal');
    }
  };

  const handleResetGoals = async () => {
    if (!window.confirm('Reset all goals to defaults? Custom goals will be deleted.')) return;
    try {
      const resp = await fetch('/api/morphogenetic/goals/reset', { method: 'POST' });
      if (resp.ok) {
        showToast('Goals reset to defaults');
        await fetchAll();
      }
    } catch {
      showToast('Failed to reset goals');
    }
  };

  // ----- Cascade config handlers -----

  const handleSaveConfig = async () => {
    if (!configDraft) return;
    try {
      const resp = await fetch('/api/morphogenetic/cascade/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configDraft),
      });
      if (resp.ok) {
        const data = await resp.json();
        setCascadeConfig(data);
        setConfigDraft(data);
        showToast('Cascade settings saved');
      }
    } catch {
      showToast('Failed to save cascade config');
    }
  };

  const handleResetConfig = async () => {
    if (!window.confirm('Reset cascade settings to defaults?')) return;
    try {
      const resp = await fetch('/api/morphogenetic/cascade/config/reset', { method: 'POST' });
      if (resp.ok) {
        const data = await resp.json();
        setCascadeConfig(data);
        setConfigDraft(data);
        showToast('Cascade settings reset to defaults');
      }
    } catch {
      showToast('Failed to reset cascade config');
    }
  };

  const satisfiedGoals = goals.filter(g => g.satisfied === true).length;
  const formalizedGoals = goals.filter(g => g.formalization_level !== 'G0').length;
  const totalCompetencies = assembly?.count || 0;

  return (
    <div className="flex flex-col h-full">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 px-4 py-2 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl shadow-lg text-sm" role="alert">
          {toast}
        </div>
      )}

      {/* Goal Edit Modal */}
      {editingGoal && (
        <GoalEditModal
          draft={editingGoal}
          isNew={isNewGoal}
          onSave={handleSaveGoal}
          onDelete={!isNewGoal ? handleDeleteGoal : undefined}
          onClose={() => setEditingGoal(null)}
        />
      )}

      {/* Header — pinned */}
      <div className="shrink-0 px-6 pt-6 pb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Dna size={24} className="text-[var(--color-accent)]" />
          <div>
            <h1 className="text-xl font-semibold">Morphogenetic Agency</h1>
            <p className="text-xs text-[var(--color-text-muted)]">
              Developmental state &middot; Agents grow by failing
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={runEvaluation}
            disabled={evaluating}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] disabled:opacity-50 transition-colors"
          >
            {evaluating ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
            {evaluating ? 'Evaluating...' : 'Evaluate Now'}
          </button>
          <button
            onClick={fetchAll}
            className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-6">
      {loading ? (
        <div className="text-center text-[var(--color-text-muted)] py-16">Loading developmental state...</div>
      ) : (
        <>
          {/* Developmental Observables */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <MetricCard label="AI-proxy" value={snapshot?.ai_proxy?.toFixed(1) || '0'} icon={Brain} sub="Structural complexity" accent="blue" />
            <MetricCard label="CLC" value={`${snapshot?.clc_horizon || 0}s \u00D7 ${snapshot?.clc_dimensions || 0}d`} icon={Target} sub="Cognitive light cone" accent="blue" />
            <MetricCard label="\u03B7 (eta)" value={snapshot?.eta_mean?.toFixed(4) || '0'} icon={Zap} sub="Informational efficiency" accent={snapshot && snapshot.eta_mean > 0 ? 'green' : 'amber'} />
            <MetricCard label="Attractors" value={`${snapshot?.attractor_count || 0}/${goals.length}`} icon={CheckCircle} sub="Goals in basin" accent={snapshot && snapshot.attractor_count === goals.length ? 'green' : 'amber'} />
            <MetricCard label="Spec Gap" value={snapshot?.spec_gap_mean?.toFixed(4) || '0'} icon={AlertTriangle} sub="Mean failure beyond \u03B5" accent={snapshot && snapshot.spec_gap_mean === 0 ? 'green' : 'red'} />
            <MetricCard label="Assembly" value={totalCompetencies} icon={Layers} sub={`${snapshot?.total_reuse || 0} total reuse`} accent="blue" />
          </div>

          {/* Cascade Settings (collapsible) */}
          <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl">
            <button
              onClick={() => setSettingsOpen(!settingsOpen)}
              className="flex items-center justify-between w-full p-4 text-left"
            >
              <div className="flex items-center gap-2">
                <Settings size={14} className="text-[var(--color-text-muted)]" />
                <span className="text-sm font-medium">Cascade Settings</span>
                {cascadeConfig && (
                  <span className="text-[10px] text-[var(--color-text-muted)] px-1.5 py-0.5 bg-[var(--color-bg-hover)] rounded">
                    \u03B4={cascadeConfig.delta} \u00B7 min_obs={cascadeConfig.min_observations}
                  </span>
                )}
              </div>
              {settingsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>

            {settingsOpen && configDraft && (
              <div className="px-4 pb-4 border-t border-[var(--color-border)] pt-4 space-y-4">
                <div>
                  <h4 className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Trigger Parameters</h4>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Min Observations</label>
                      <input type="number" min="1" value={configDraft.min_observations} onChange={e => setConfigDraft({ ...configDraft, min_observations: parseInt(e.target.value) || 20 })} className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                    </div>
                    <div>
                      <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Confidence \u03B4 (Hoeffding)</label>
                      <input type="number" step="0.005" min="0.001" max="0.5" value={configDraft.delta} onChange={e => setConfigDraft({ ...configDraft, delta: parseFloat(e.target.value) || 0.05 })} className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Cascade Limits</h4>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Max T0 Attempts</label>
                      <input type="number" min="1" max="10" value={configDraft.max_tier0_attempts} onChange={e => setConfigDraft({ ...configDraft, max_tier0_attempts: parseInt(e.target.value) || 3 })} className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                    </div>
                    <div>
                      <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Max T1 Attempts</label>
                      <input type="number" min="1" max="10" value={configDraft.max_tier1_attempts} onChange={e => setConfigDraft({ ...configDraft, max_tier1_attempts: parseInt(e.target.value) || 2 })} className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                    </div>
                    <div>
                      <label className="block text-[10px] text-[var(--color-text-muted)] mb-1">Timeout (seconds)</label>
                      <input type="number" min="10" max="300" value={configDraft.cascade_timeout_seconds} onChange={e => setConfigDraft({ ...configDraft, cascade_timeout_seconds: parseInt(e.target.value) || 60 })} className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Tier Controls</h4>
                  <div className="space-y-2">
                    <ToggleSwitch checked={configDraft.tier0_enabled} onChange={v => setConfigDraft({ ...configDraft, tier0_enabled: v })} label="Tier 0: Parameter Tuning" />
                    <ToggleSwitch checked={configDraft.tier1_enabled} onChange={v => setConfigDraft({ ...configDraft, tier1_enabled: v })} label="Tier 1: Goal Retargeting" />
                    <div className="flex items-center gap-4">
                      <div className="flex-1"><ToggleSwitch checked={configDraft.tier2_enabled} onChange={v => setConfigDraft({ ...configDraft, tier2_enabled: v })} label="Tier 2: Boundary Expansion" /></div>
                      {configDraft.tier2_enabled && (
                        <div className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-muted)]">
                          <span>Auto-approve</span>
                          <button type="button" onClick={() => setConfigDraft({ ...configDraft, tier2_auto_approve: !configDraft.tier2_auto_approve })} className={`relative inline-flex h-4 w-7 shrink-0 rounded-full border-2 border-transparent transition-colors ${configDraft.tier2_auto_approve ? 'bg-amber-500' : 'bg-[var(--color-bg-hover)]'}`}>
                            <span className={`pointer-events-none inline-block h-3 w-3 rounded-full bg-white shadow transition-transform ${configDraft.tier2_auto_approve ? 'translate-x-3' : 'translate-x-0'}`} />
                          </button>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="flex-1"><ToggleSwitch checked={configDraft.tier3_enabled} onChange={v => setConfigDraft({ ...configDraft, tier3_enabled: v })} label="Tier 3: Scale Reorganization" /></div>
                      {configDraft.tier3_enabled && (
                        <div className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-muted)]">
                          <span>Auto-approve</span>
                          <button type="button" onClick={() => setConfigDraft({ ...configDraft, tier3_auto_approve: !configDraft.tier3_auto_approve })} className={`relative inline-flex h-4 w-7 shrink-0 rounded-full border-2 border-transparent transition-colors ${configDraft.tier3_auto_approve ? 'bg-amber-500' : 'bg-[var(--color-bg-hover)]'}`}>
                            <span className={`pointer-events-none inline-block h-3 w-3 rounded-full bg-white shadow transition-transform ${configDraft.tier3_auto_approve ? 'translate-x-3' : 'translate-x-0'}`} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--color-border)]">
                  <button onClick={handleResetConfig} className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-bg-hover)]">
                    <RotateCcw size={12} /> Reset
                  </button>
                  <button onClick={handleSaveConfig} className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium bg-[var(--color-accent)] text-white rounded-lg hover:bg-[var(--color-accent-hover)]">
                    <Save size={12} /> Save Settings
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Goals + Cascade side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Goal Specs */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-[var(--color-text-muted)]">
                  Goal Specs ({satisfiedGoals}/{formalizedGoals} satisfied)
                </h2>
                <div className="flex items-center gap-1.5">
                  <button onClick={handleResetGoals} className="flex items-center gap-1 px-2 py-1 text-[10px] border border-[var(--color-border)] rounded-lg text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)]" title="Reset to defaults">
                    <RotateCcw size={10} /> Reset
                  </button>
                  <button onClick={handleNewGoal} className="flex items-center gap-1 px-2 py-1 text-[10px] bg-[var(--color-accent)] text-white rounded-lg hover:bg-[var(--color-accent-hover)]">
                    <Plus size={10} /> New Goal
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                {goals.map(goal => (
                  <div key={goal.goal_id} className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-3 group">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        {goal.satisfied === true ? (
                          <CheckCircle size={14} className="text-green-400" />
                        ) : goal.satisfied === false ? (
                          <XCircle size={14} className="text-red-400" />
                        ) : (
                          <Clock size={14} className="text-[var(--color-text-muted)]" />
                        )}
                        <span className="text-sm font-medium">{goal.display_name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleEditGoal(goal)} className="opacity-40 group-hover:opacity-100 p-1 rounded hover:bg-[var(--color-bg-hover)] transition-all" title="Edit goal">
                          <Pencil size={12} className="text-[var(--color-text-muted)]" />
                        </button>
                        <TierBadge tier={goal.primary_tier} />
                        <span className="text-[10px] text-[var(--color-text-muted)] px-1.5 py-0.5 bg-[var(--color-bg-hover)] rounded">{goal.formalization_level}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
                      <span>\u03B5={goal.epsilon_g}</span>
                      <span>T={goal.horizon_t}s</span>
                      <span>P{goal.priority}</span>
                    </div>
                    {goal.channel_status && Object.keys(goal.channel_status).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {Object.entries(goal.channel_status).map(([ch, st]) => (
                          <span key={ch} className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${st.within_tolerance ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                            {ch}: {st.p_fail.toFixed(3)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Cascade History + Competencies */}
            <div className="space-y-6">
              {assembly && Object.keys(assembly.distribution).length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-sm font-medium text-[var(--color-text-muted)]">Competency Distribution</h2>
                  <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-4">
                    <div className="flex items-center gap-4">
                      {Object.entries(assembly.distribution).map(([type, count]) => (
                        <div key={type} className="text-center">
                          <div className="text-lg font-bold text-[var(--color-text)]">{count}</div>
                          <div className="text-[10px] text-[var(--color-text-muted)] capitalize">{type}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {snapshot && Object.keys(snapshot.tier_usage).length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-sm font-medium text-[var(--color-text-muted)]">Cascade Tier Usage</h2>
                  <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-4">
                    <div className="flex items-center gap-4">
                      {Object.entries(snapshot.tier_usage).map(([tier, count]) => (
                        <div key={tier} className="text-center">
                          <div className="text-lg font-bold text-[var(--color-text)]">{count}</div>
                          <div className="text-[10px] text-[var(--color-text-muted)]">Tier {tier}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {snapshot && Object.keys(snapshot.cp_profile).length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-sm font-medium text-[var(--color-text-muted)]">Causal Power Profile CP(l)</h2>
                  <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-4">
                    <div className="space-y-2">
                      {Object.entries(snapshot.cp_profile).sort(([, a], [, b]) => b - a).map(([channel, capacity]) => (
                        <div key={channel} className="flex items-center gap-3">
                          <code className="text-xs text-[var(--color-text-muted)] w-8">{channel}</code>
                          <div className="flex-1 h-2 bg-[var(--color-bg-hover)] rounded-full overflow-hidden">
                            <div className="h-full bg-[var(--color-accent)] rounded-full transition-all" style={{ width: `${Math.min(capacity * 100, 100)}%` }} />
                          </div>
                          <span className="text-xs font-mono text-[var(--color-text-muted)] w-12 text-right">{capacity.toFixed(3)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              <div className="space-y-3">
                <h2 className="text-sm font-medium text-[var(--color-text-muted)]">Recent Cascades ({cascades.length})</h2>
                {cascades.length === 0 ? (
                  <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-6 text-center">
                    <Activity size={32} className="mx-auto mb-2 text-[var(--color-text-muted)] opacity-30" />
                    <p className="text-xs text-[var(--color-text-muted)]">No cascade events yet. The system will adapt when goals are triggered.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {cascades.slice(0, 10).map(ev => (
                      <div key={ev.cascade_id} className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-3">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <ArrowUpRight size={12} className="text-[var(--color-text-muted)]" />
                            <code className="text-[10px] text-[var(--color-text-muted)]">{ev.cascade_id}</code>
                          </div>
                          <OutcomeBadge outcome={ev.outcome} />
                        </div>
                        <div className="flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
                          <span>Goal: {ev.goal_id}</span>
                          <span>Ch: {ev.channel_id}</span>
                          <span>p_fail: {ev.trigger_p_fail?.toFixed(3)}</span>
                          {ev.tier_succeeded !== null && <TierBadge tier={ev.tier_succeeded} />}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
      </div>
    </div>
  );
}
