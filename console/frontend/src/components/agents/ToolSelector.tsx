import type { ToolDefinition } from '@/types/agents';

const CATEGORY_STYLES: Record<string, { bg: string; text: string }> = {
  shopify: { bg: 'bg-green-950/30', text: 'text-green-400' },
  stripe: { bg: 'bg-violet-950/30', text: 'text-violet-400' },
  printful: { bg: 'bg-blue-950/30', text: 'text-blue-400' },
  instagram: { bg: 'bg-pink-950/30', text: 'text-pink-400' },
  memory: { bg: 'bg-amber-950/30', text: 'text-amber-400' },
};

interface Props {
  tools: ToolDefinition[];
  selectedIds: string[];
  onChange: (toolIds: string[]) => void;
}

export default function ToolSelector({ tools, selectedIds, onChange }: Props) {
  const categories = [...new Set(tools.map((t) => t.category))].sort();

  const toggle = (toolId: string) => {
    onChange(
      selectedIds.includes(toolId)
        ? selectedIds.filter((id) => id !== toolId)
        : [...selectedIds, toolId],
    );
  };

  return (
    <div className="space-y-3">
      {categories.map((cat) => {
        const style = CATEGORY_STYLES[cat] ?? { bg: 'bg-gray-950/30', text: 'text-gray-400' };
        const catTools = tools.filter((t) => t.category === cat);
        const selectedCount = catTools.filter((t) => selectedIds.includes(t.tool_id)).length;

        return (
          <div key={cat}>
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`text-[10px] font-semibold uppercase tracking-wider ${style.text}`}>
                {cat}
              </span>
              {selectedCount > 0 && (
                <span className={`text-[9px] px-1.5 py-0.5 rounded ${style.bg} ${style.text}`}>
                  {selectedCount}/{catTools.length}
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {catTools.map((t) => {
                const isSelected = selectedIds.includes(t.tool_id);
                return (
                  <button
                    key={t.tool_id}
                    onClick={() => toggle(t.tool_id)}
                    title={t.description}
                    className={`px-2 py-1 text-[10px] rounded border transition-colors ${
                      isSelected
                        ? `border-[var(--color-accent)] ${style.bg} ${style.text}`
                        : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-text-muted)]'
                    }`}
                  >
                    {t.display_name}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
      {tools.length === 0 && (
        <div className="text-xs text-[var(--color-text-muted)]">No tools available</div>
      )}
    </div>
  );
}
