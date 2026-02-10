import { useEffect, useState } from 'react';
import Header from '@/components/layout/Header';
import { fetchJson } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GateLevel {
  level: number;
  is_open: boolean;
  failing_predicates: number[];
}

interface Predicate {
  index: number;
  name: string;
  level: number;
  block: string;
  epsilon_dmg: number;
  current_value: number | null;
  last_observed: string | null;
  module_id: string | null;
  agent_id: string;
}

interface EigenvalueEntry {
  index: number;
  value: number;
  layer: string;
  dominant_predicates: number[];
  interpretation: string;
}

interface Feasibility {
  overall: boolean;
  rank_coverage: boolean;
  coupling_coverage: boolean;
  epsilon_check: boolean;
  details: Record<string, unknown>;
}

interface Module {
  module_id: string;
  name: string;
  level: number;
  status: string;
  predicate_count: number;
  predicate_indices: number[];
  agent_id: string;
  upward_channels: string[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LEVEL_NAMES: Record<number, string> = {
  0: 'Transcendent',
  1: 'Conscience',
  2: 'Nonmaleficence',
  3: 'Legal Rights',
  4: 'Self-Preservation',
  5: 'Profit / Readiness',
  6: 'Personality',
};

const LEVEL_COLORS: Record<number, string> = {
  0: '#a855f7',
  1: '#8b5cf6',
  2: '#ef4444',
  3: '#f59e0b',
  4: '#3b82f6',
  5: '#22c55e',
  6: '#06b6d4',
};

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function GateBanner({ gates }: { gates: GateLevel[] }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {gates.map((g) => (
        <div
          key={g.level}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-mono ${
            g.is_open
              ? 'border-green-700/50 bg-green-950/30 text-green-400'
              : 'border-red-700/50 bg-red-950/30 text-red-400'
          }`}
          title={
            g.is_open
              ? `Level ${g.level} gate: OPEN`
              : `Level ${g.level} gate: CLOSED (failing: f${g.failing_predicates.join(', f')})`
          }
        >
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              g.is_open ? 'bg-green-400' : 'bg-red-400 animate-pulse'
            }`}
          />
          <span className="text-[var(--color-text-muted)] text-xs">L{g.level}</span>
          <span className="text-xs">{LEVEL_NAMES[g.level] ?? `Level ${g.level}`}</span>
          {!g.is_open && (
            <span className="text-xs text-red-300 ml-1">
              ({g.failing_predicates.length} failing)
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function PredicateTable({
  predicates,
  selectedLevel,
  onSelectLevel,
}: {
  predicates: Predicate[];
  selectedLevel: number | null;
  onSelectLevel: (l: number | null) => void;
}) {
  const filtered = selectedLevel !== null
    ? predicates.filter((p) => p.level === selectedLevel)
    : predicates;

  return (
    <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] overflow-hidden">
      <div className="p-3 border-b border-[var(--color-border)] flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          Predicates ({filtered.length})
        </h3>
        <div className="flex gap-1">
          <button
            className={`px-2 py-0.5 rounded text-xs ${
              selectedLevel === null
                ? 'bg-[var(--color-accent)] text-white'
                : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)]'
            }`}
            onClick={() => onSelectLevel(null)}
          >
            All
          </button>
          {[0, 1, 2, 3, 4, 5, 6].map((l) => (
            <button
              key={l}
              className={`px-2 py-0.5 rounded text-xs ${
                selectedLevel === l
                  ? 'bg-[var(--color-accent)] text-white'
                  : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)]'
              }`}
              onClick={() => onSelectLevel(l)}
            >
              L{l}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-auto max-h-[500px]">
        <table className="w-full text-xs">
          <thead className="bg-[var(--color-bg-hover)] sticky top-0">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-[var(--color-text-muted)]">f#</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--color-text-muted)]">Name</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--color-text-muted)]">Lvl</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--color-text-muted)]">Blk</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--color-text-muted)]">Value</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--color-text-muted)]">e_dmg</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--color-text-muted)]">Agent</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => {
              const threshold = 1.0 - p.epsilon_dmg;
              const passing =
                p.current_value === null || p.current_value >= threshold;
              return (
                <tr
                  key={p.index}
                  className="border-t border-[var(--color-border)] hover:bg-[var(--color-bg-hover)]"
                >
                  <td className="px-3 py-1.5 font-mono" style={{ color: LEVEL_COLORS[p.level] }}>
                    f{p.index}
                  </td>
                  <td className="px-3 py-1.5">{p.name}</td>
                  <td className="px-3 py-1.5 text-center">{p.level}</td>
                  <td className="px-3 py-1.5 text-center font-mono">{p.block}</td>
                  <td className="px-3 py-1.5 text-center">
                    {p.current_value !== null ? (
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs font-mono ${
                          passing
                            ? 'bg-green-900/40 text-green-400'
                            : 'bg-red-900/40 text-red-400'
                        }`}
                      >
                        {p.current_value.toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-[var(--color-text-muted)]">---</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-center font-mono text-[var(--color-text-muted)]">
                    {p.epsilon_dmg}
                  </td>
                  <td className="px-3 py-1.5 font-mono text-[var(--color-text-muted)]">
                    {p.agent_id}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EigenspectrumCard({ eigenvalues, codG }: { eigenvalues: EigenvalueEntry[]; codG: number }) {
  const maxVal = Math.max(...eigenvalues.map((e) => e.value), 0.01);
  return (
    <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] p-3">
      <h3 className="text-sm font-semibold mb-1">
        Eigenspectrum <span className="text-[var(--color-text-muted)] font-normal">cod(G) = {codG}</span>
      </h3>
      <div className="flex flex-col gap-1 mt-2">
        {eigenvalues.map((e) => (
          <div key={e.index} className="flex items-center gap-2 text-xs">
            <span className="font-mono w-6 text-[var(--color-text-muted)]">
              {'\u03BB'}{e.index}
            </span>
            <div className="flex-1 h-4 bg-[var(--color-bg-hover)] rounded overflow-hidden">
              <div
                className="h-full rounded transition-all"
                style={{
                  width: `${(e.value / maxVal) * 100}%`,
                  backgroundColor: e.layer === 'celestial' ? '#3b82f6' : '#22c55e',
                }}
              />
            </div>
            <span className="font-mono w-10 text-right">{e.value.toFixed(2)}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-3 mt-2 text-xs text-[var(--color-text-muted)]">
        <span className="flex items-center gap-1">
          <div className="w-2 h-2 rounded bg-blue-500" /> Celestial
        </span>
        <span className="flex items-center gap-1">
          <div className="w-2 h-2 rounded bg-green-500" /> Terrestrial
        </span>
      </div>
    </div>
  );
}

function FeasibilityCard({ feasibility }: { feasibility: Feasibility }) {
  const checks = [
    { label: 'Rank Coverage', pass: feasibility.rank_coverage },
    { label: 'Coupling Coverage', pass: feasibility.coupling_coverage },
    { label: 'Epsilon Check', pass: feasibility.epsilon_check },
  ];
  return (
    <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] p-3">
      <h3 className="text-sm font-semibold mb-2">
        Feasibility{' '}
        <span
          className={`ml-1 px-2 py-0.5 rounded text-xs font-mono ${
            feasibility.overall
              ? 'bg-green-900/40 text-green-400'
              : 'bg-red-900/40 text-red-400'
          }`}
        >
          {feasibility.overall ? 'PASS' : 'FAIL'}
        </span>
      </h3>
      <div className="flex flex-col gap-1.5">
        {checks.map((c) => (
          <div key={c.label} className="flex items-center gap-2 text-xs">
            <span className={c.pass ? 'text-green-400' : 'text-red-400'}>
              {c.pass ? '\u2713' : '\u2717'}
            </span>
            <span>{c.label}</span>
          </div>
        ))}
      </div>
      {feasibility.details?.rank && (
        <div className="mt-2 text-xs text-[var(--color-text-muted)] font-mono">
          {'\u03A3'}r = {(feasibility.details.rank as Record<string, number>).total} | cod(G) = {(feasibility.details.rank as Record<string, number>).cod_g} | margin = {(feasibility.details.rank as Record<string, number>).margin}
        </div>
      )}
    </div>
  );
}

function ModulesCard({ modules }: { modules: Module[] }) {
  return (
    <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] p-3">
      <h3 className="text-sm font-semibold mb-2">Terrestrial Modules ({modules.length})</h3>
      <div className="flex flex-col gap-2">
        {modules.map((m) => (
          <div
            key={m.module_id}
            className="flex items-center justify-between text-xs border border-[var(--color-border)] rounded-lg px-3 py-2"
          >
            <div>
              <span className="font-medium">{m.name}</span>
              <span className="text-[var(--color-text-muted)] ml-2">L{m.level}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[var(--color-text-muted)]">
                {m.predicate_count} preds
              </span>
              <span
                className={`px-1.5 py-0.5 rounded text-xs ${
                  m.status === 'Active'
                    ? 'bg-green-900/40 text-green-400'
                    : 'bg-gray-800 text-gray-400'
                }`}
              >
                {m.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HierarchyPage() {
  const [gates, setGates] = useState<GateLevel[]>([]);
  const [predicates, setPredicates] = useState<Predicate[]>([]);
  const [eigenvalues, setEigenvalues] = useState<EigenvalueEntry[]>([]);
  const [codG, setCodG] = useState(0);
  const [feasibility, setFeasibility] = useState<Feasibility | null>(null);
  const [modules, setModules] = useState<Module[]>([]);
  const [selectedLevel, setSelectedLevel] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => {
      fetchJson<GateLevel[]>('/api/hierarchy/gate')
        .then(setGates)
        .catch((e) => setError(e.message));
      fetchJson<Predicate[]>('/api/hierarchy/predicates')
        .then(setPredicates)
        .catch(() => {});
      fetchJson<{ cod_g: number; eigenvalues: EigenvalueEntry[] }>(
        '/api/hierarchy/eigenspectrum'
      )
        .then((d) => {
          setCodG(d.cod_g);
          setEigenvalues(d.eigenvalues);
        })
        .catch(() => {});
      fetchJson<Feasibility>('/api/hierarchy/feasibility')
        .then(setFeasibility)
        .catch(() => {});
      fetchJson<Module[]>('/api/hierarchy/modules')
        .then(setModules)
        .catch(() => {});
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <Header title="Goal Hierarchy" subtitle="Celestial/Terrestrial constraint architecture" />
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {error && (
          <div className="bg-red-900/30 border border-red-700/50 text-red-300 rounded-lg px-4 py-2 text-sm">
            {error}
          </div>
        )}

        {/* Gate Banner */}
        <div className="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] p-3">
          <h3 className="text-sm font-semibold mb-2">Lexicographic Gate</h3>
          <GateBanner gates={gates} />
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left: Predicate table (2 cols) */}
          <div className="lg:col-span-2">
            <PredicateTable
              predicates={predicates}
              selectedLevel={selectedLevel}
              onSelectLevel={setSelectedLevel}
            />
          </div>

          {/* Right: Eigenspectrum + Feasibility + Modules */}
          <div className="flex flex-col gap-4">
            <EigenspectrumCard eigenvalues={eigenvalues} codG={codG} />
            {feasibility && <FeasibilityCard feasibility={feasibility} />}
            <ModulesCard modules={modules} />
          </div>
        </div>
      </div>
    </div>
  );
}
