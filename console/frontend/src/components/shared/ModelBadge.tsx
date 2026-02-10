const PROVIDER_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  ollama: { bg: 'bg-green-900/60', text: 'text-green-400', label: 'Ollama' },
  openai: { bg: 'bg-blue-900/60', text: 'text-blue-400', label: 'OpenAI' },
  anthropic: { bg: 'bg-purple-900/60', text: 'text-purple-400', label: 'Anthropic' },
};

const MODEL_LABELS: Record<string, string> = {
  ollama_qwen: 'Qwen 2.5:3b',
  gpt4o: 'GPT-4o',
  gpt4o_mini: 'GPT-4o-mini',
  claude_opus: 'Opus 4.6',
};

interface ModelBadgeProps {
  modelId?: string;
  provider?: string;
}

export default function ModelBadge({ modelId, provider }: ModelBadgeProps) {
  if (!provider) return null;
  const style = PROVIDER_STYLES[provider] ?? { bg: 'bg-gray-800', text: 'text-gray-400', label: provider };
  const label = modelId ? MODEL_LABELS[modelId] ?? modelId : style.label;

  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold ${style.bg} ${style.text}`}>
      {label}
    </span>
  );
}
