import { NavLink } from 'react-router-dom';
import {
  Workflow,
  ScrollText,
  GitBranch,
  DollarSign,
  Wrench,
  HeartPulse,
  Bot,
  Network,
  ShieldCheck,
  FlaskConical,
  Dna,
  Archive,
  MessageSquare,
  Radar,
  Layers,
  Sparkles,
} from 'lucide-react';

const NAV_ITEMS = [
  { to: '/', icon: Sparkles, label: 'Holly' },
  { to: '/canvas', icon: Workflow, label: 'Canvas' },
  { to: '/workflows', icon: Network, label: 'Workflows' },
  { to: '/agents', icon: Bot, label: 'Agents' },
  { to: '/tower', icon: Radar, label: 'Tower' },
  { to: '/hierarchy', icon: Layers, label: 'Hierarchy' },
  { to: '/approvals', icon: ShieldCheck, label: 'Approvals' },
  { to: '/eval', icon: FlaskConical, label: 'Eval' },
  { to: '/morph', icon: Dna, label: 'Morph' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
  { to: '/traces', icon: GitBranch, label: 'Traces' },
  { to: '/costs', icon: DollarSign, label: 'Costs' },
  { to: '/tools', icon: Wrench, label: 'Tools' },
  { to: '/health', icon: HeartPulse, label: 'Health' },
  { to: '/system', icon: Archive, label: 'System' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
];

export default function Sidebar() {
  return (
    <aside role="navigation" aria-label="Main navigation" className="w-16 h-full bg-[var(--color-bg-card)] border-r border-[var(--color-border)] flex flex-col items-center py-4 gap-1 shrink-0 overflow-y-auto">
      <div className="text-[var(--color-accent)] font-bold text-xs mb-4 tracking-widest">HG</div>
      {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 px-2 py-2 rounded-lg text-xs transition-colors w-14 ${
              isActive
                ? 'bg-[var(--color-accent)] text-white'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)]'
            }`
          }
        >
          <Icon size={18} />
          <span>{label}</span>
        </NavLink>
      ))}
    </aside>
  );
}
