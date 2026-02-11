import { useCallback, useEffect, useMemo, useState } from 'react';
import Header from '@/components/layout/Header';
import { deleteJson, fetchJson, patchJson, postJson } from '@/lib/api';

type McpServer = {
  server_id: string;
  display_name: string;
  description?: string;
  transport: 'stdio' | 'http';
  enabled: boolean;
  stdio_command?: string | null;
  stdio_args?: unknown;
  stdio_cwd?: string | null;
  env_allow?: string[] | null;
  env_overrides?: Record<string, unknown> | null;
  last_health_status?: string;
  last_health_error?: string;
  last_health_at?: string | null;
};

type McpTool = {
  tool_id: string;
  server_id: string;
  transport?: string | null;
  mcp_tool_name: string;
  display_name: string;
  description: string;
  category: string;
  enabled: boolean;
  risk_level: 'low' | 'medium' | 'high' | string;
  last_seen_at?: string | null;
};

export default function McpPage() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [loadingServers, setLoadingServers] = useState(true);
  const [selectedServerId, setSelectedServerId] = useState<string | null>(null);
  const [tools, setTools] = useState<McpTool[]>([]);
  const [loadingTools, setLoadingTools] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newServer, setNewServer] = useState({
    server_id: '',
    display_name: '',
    stdio_command: 'node',
    stdio_args_json: '[]',
    stdio_cwd: '',
    env_allow_csv: '',
    env_overrides_json: '{}',
  });

  const loadServers = useCallback(() => {
    setLoadingServers(true);
    setError(null);
    fetchJson<{ servers: McpServer[] }>('/api/mcp/servers')
      .then((d) => setServers(d.servers ?? []))
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingServers(false));
  }, []);

  const loadTools = useCallback((serverId: string) => {
    setLoadingTools(true);
    setError(null);
    fetchJson<{ tools: McpTool[] }>(`/api/mcp/servers/${serverId}/tools`)
      .then((d) => setTools(d.tools ?? []))
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingTools(false));
  }, []);

  useEffect(() => {
    loadServers();
  }, [loadServers]);

  useEffect(() => {
    if (selectedServerId) loadTools(selectedServerId);
  }, [selectedServerId, loadTools]);

  const selected = useMemo(
    () => servers.find((s) => s.server_id === selectedServerId) ?? null,
    [servers, selectedServerId],
  );

  const onCreateServer = async () => {
    setError(null);
    let args: string[] = [];
    try {
      const parsed = JSON.parse(newServer.stdio_args_json || '[]');
      if (!Array.isArray(parsed) || !parsed.every((x) => typeof x === 'string')) {
        throw new Error('stdio_args must be a JSON array of strings');
      }
      args = parsed;
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Invalid stdio_args_json');
      return;
    }

    const envAllow = (newServer.env_allow_csv || '')
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    let envOverrides: Record<string, unknown> = {};
    try {
      const raw = (newServer.env_overrides_json || '').trim();
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          envOverrides = parsed as Record<string, unknown>;
        } else {
          throw new Error('env_overrides must be a JSON object');
        }
      }
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Invalid env_overrides_json');
      return;
    }

    try {
      await postJson('/api/mcp/servers', {
        server_id: newServer.server_id.trim(),
        display_name: newServer.display_name.trim() || newServer.server_id.trim(),
        transport: 'stdio',
        enabled: true,
        stdio_command: newServer.stdio_command.trim(),
        stdio_args: args,
        stdio_cwd: newServer.stdio_cwd.trim() || null,
        env_allow: envAllow,
        env_overrides: envOverrides,
      });
      setNewServer({
        server_id: '',
        display_name: '',
        stdio_command: 'node',
        stdio_args_json: '[]',
        stdio_cwd: '',
        env_allow_csv: '',
        env_overrides_json: '{}',
      });
      loadServers();
    } catch (e: any) {
      setError(e?.message ? String(e.message) : String(e));
    }
  };

  const onSync = async (serverId: string) => {
    setError(null);
    try {
      await postJson(`/api/mcp/servers/${serverId}/sync`, {});
      loadServers();
      if (selectedServerId === serverId) loadTools(serverId);
    } catch (e: any) {
      setError(e?.message ? String(e.message) : String(e));
    }
  };

  const onDelete = async (serverId: string) => {
    setError(null);
    try {
      await deleteJson(`/api/mcp/servers/${serverId}`);
      if (selectedServerId === serverId) {
        setSelectedServerId(null);
        setTools([]);
      }
      loadServers();
    } catch (e: any) {
      setError(e?.message ? String(e.message) : String(e));
    }
  };

  const onRefreshHealth = async () => {
    setError(null);
    try {
      await fetchJson(`/api/mcp/health?refresh=true`);
      loadServers();
    } catch (e: any) {
      setError(e?.message ? String(e.message) : String(e));
    }
  };

  const patchTool = async (toolId: string, patch: Partial<McpTool>) => {
    setError(null);
    try {
      await patchJson(`/api/mcp/tools/${toolId}`, patch);
      if (selectedServerId) loadTools(selectedServerId);
    } catch (e: any) {
      setError(e?.message ? String(e.message) : String(e));
    }
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="MCP Airspace" subtitle="MCP server registry, discovery, and governance" />

      <div className="flex-1 overflow-auto p-6 space-y-6">
        {error && (
          <div className="p-3 rounded-lg border border-red-500/30 bg-red-950/20 text-red-200 text-sm">
            {error}
          </div>
        )}

        <section className="p-4 rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">Add Stdio MCP Server</div>
              <div className="text-xs text-[var(--color-text-muted)] mt-0.5">
                For Node MCP servers: command `node`, args like `["c:/.../dist/index.js"]`. Use env allowlist for keys needed by the server.
              </div>
            </div>
            <button
              onClick={onCreateServer}
              className="px-3 py-1.5 rounded bg-[var(--color-accent)] text-white text-xs font-semibold hover:opacity-90"
            >
              Create
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
            <label className="text-xs">
              <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
                server_id
              </div>
              <input
                value={newServer.server_id}
                onChange={(e) => setNewServer((s) => ({ ...s, server_id: e.target.value }))}
                className="w-full px-2 py-1.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs"
                placeholder="gmail"
              />
            </label>
            <label className="text-xs">
              <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
                display_name
              </div>
              <input
                value={newServer.display_name}
                onChange={(e) => setNewServer((s) => ({ ...s, display_name: e.target.value }))}
                className="w-full px-2 py-1.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs"
                placeholder="Gmail"
              />
            </label>
            <label className="text-xs">
              <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
                stdio_command
              </div>
              <input
                value={newServer.stdio_command}
                onChange={(e) => setNewServer((s) => ({ ...s, stdio_command: e.target.value }))}
                className="w-full px-2 py-1.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs"
                placeholder="node"
              />
            </label>
            <label className="text-xs md:col-span-2 lg:col-span-2">
              <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
                stdio_args (JSON)
              </div>
              <input
                value={newServer.stdio_args_json}
                onChange={(e) => setNewServer((s) => ({ ...s, stdio_args_json: e.target.value }))}
                className="w-full px-2 py-1.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs font-mono"
                placeholder='["c:/Users/seanp/Workspace/gmail-mcp-server/dist/index.js"]'
              />
            </label>
            <label className="text-xs">
              <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
                stdio_cwd (optional)
              </div>
              <input
                value={newServer.stdio_cwd}
                onChange={(e) => setNewServer((s) => ({ ...s, stdio_cwd: e.target.value }))}
                className="w-full px-2 py-1.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs"
                placeholder="c:/Users/seanp/Workspace/gmail-mcp-server"
              />
            </label>
            <label className="text-xs md:col-span-2 lg:col-span-2">
              <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
                env_allow (CSV, optional)
              </div>
              <input
                value={newServer.env_allow_csv}
                onChange={(e) => setNewServer((s) => ({ ...s, env_allow_csv: e.target.value }))}
                className="w-full px-2 py-1.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs font-mono"
                placeholder="OPENAI_API_KEY,STRIPE_SECRET_KEY"
              />
            </label>
            <label className="text-xs md:col-span-2 lg:col-span-2">
              <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] mb-1">
                env_overrides (JSON, optional)
              </div>
              <input
                value={newServer.env_overrides_json}
                onChange={(e) => setNewServer((s) => ({ ...s, env_overrides_json: e.target.value }))}
                className="w-full px-2 py-1.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs font-mono"
                placeholder='{"FOO":"bar"}'
              />
            </label>
          </div>
        </section>

        <section className="flex items-center justify-between">
          <div className="text-sm font-semibold">
            Servers
            <span className="text-[10px] text-[var(--color-text-muted)] ml-2">
              {loadingServers ? '...' : `${servers.length} total`}
            </span>
          </div>
          <button
            onClick={onRefreshHealth}
            className="px-2 py-1 text-[10px] font-semibold rounded bg-[var(--color-accent)]/15 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/25"
          >
            Refresh Health
          </button>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {servers.map((s) => {
            const isSelected = s.server_id === selectedServerId;
            const status = s.last_health_status ?? 'unknown';
            const statusColor =
              status === 'ok' ? 'text-emerald-300' : status === 'error' ? 'text-red-300' : 'text-[var(--color-text-muted)]';
            return (
              <button
                key={s.server_id}
                onClick={() => setSelectedServerId(s.server_id)}
                className={`text-left p-4 rounded-xl border transition-colors bg-[var(--color-bg-card)] ${
                  isSelected ? 'border-[var(--color-accent)]' : 'border-[var(--color-border)] hover:border-[var(--color-text-muted)]'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold">{s.display_name}</div>
                  <div className={`text-[10px] font-semibold ${statusColor}`}>{status}</div>
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                  {s.server_id} · {s.transport}
                </div>
                {s.last_health_error && (
                  <div className="text-[10px] text-red-200/80 mt-1 line-clamp-2">
                    {s.last_health_error}
                  </div>
                )}
                <div className="flex items-center gap-2 mt-3">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSync(s.server_id);
                    }}
                    className="px-2 py-1 text-[10px] font-semibold rounded bg-[var(--color-accent)]/15 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/25"
                  >
                    Sync Tools
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(s.server_id);
                    }}
                    className="px-2 py-1 text-[10px] font-semibold rounded bg-red-500/10 text-red-200 hover:bg-red-500/20 border border-red-500/20"
                  >
                    Delete
                  </button>
                </div>
              </button>
            );
          })}
          {!loadingServers && servers.length === 0 && (
            <div className="text-sm text-[var(--color-text-muted)] col-span-full p-8 text-center">
              No MCP servers registered
            </div>
          )}
        </section>

        <section className="p-4 rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">
                Tools {selected ? `for ${selected.display_name}` : ''}
              </div>
              <div className="text-xs text-[var(--color-text-muted)] mt-0.5">
                MCP tools default to `medium` risk until changed.
              </div>
            </div>
            {selectedServerId && (
              <button
                onClick={() => loadTools(selectedServerId)}
                className="px-2 py-1 text-[10px] font-semibold rounded bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] border border-[var(--color-border)]"
              >
                Reload
              </button>
            )}
          </div>

          {!selectedServerId && (
            <div className="text-sm text-[var(--color-text-muted)] mt-4">
              Select a server to view tools.
            </div>
          )}

          {selectedServerId && (
            <div className="mt-4">
              {loadingTools ? (
                <div className="text-sm text-[var(--color-text-muted)]">Loading tools...</div>
              ) : tools.length === 0 ? (
                <div className="text-sm text-[var(--color-text-muted)]">No tools discovered yet. Click Sync Tools.</div>
              ) : (
                <div className="overflow-auto">
                  <table className="w-full text-xs">
                    <thead className="text-[10px] text-[var(--color-text-muted)]">
                      <tr className="border-b border-[var(--color-border)]">
                        <th className="text-left py-2 pr-2">tool_id</th>
                        <th className="text-left py-2 pr-2">mcp_tool_name</th>
                        <th className="text-left py-2 pr-2">enabled</th>
                        <th className="text-left py-2 pr-2">risk</th>
                        <th className="text-left py-2 pr-2">category</th>
                        <th className="text-left py-2 pr-2">display</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tools.map((t) => (
                        <tr key={t.tool_id} className="border-b border-[var(--color-border)]/60">
                          <td className="py-2 pr-2 font-mono text-[11px]">{t.tool_id}</td>
                          <td className="py-2 pr-2 font-mono text-[11px]">{t.mcp_tool_name}</td>
                          <td className="py-2 pr-2">
                            <input
                              type="checkbox"
                              checked={!!t.enabled}
                              onChange={(e) => patchTool(t.tool_id, { enabled: e.target.checked })}
                            />
                          </td>
                          <td className="py-2 pr-2">
                            <select
                              value={t.risk_level}
                              onChange={(e) => patchTool(t.tool_id, { risk_level: e.target.value as any })}
                              className="px-2 py-1 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[11px]"
                            >
                              <option value="low">low</option>
                              <option value="medium">medium</option>
                              <option value="high">high</option>
                            </select>
                          </td>
                          <td className="py-2 pr-2">
                            <input
                              value={t.category ?? ''}
                              onChange={(e) => {
                                const v = e.target.value;
                                setTools((prev) => prev.map((x) => (x.tool_id === t.tool_id ? { ...x, category: v } : x)));
                              }}
                              onBlur={(e) => patchTool(t.tool_id, { category: e.target.value })}
                              className="w-28 px-2 py-1 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[11px]"
                            />
                          </td>
                          <td className="py-2 pr-2">
                            <input
                              value={t.display_name ?? ''}
                              onChange={(e) => {
                                const v = e.target.value;
                                setTools((prev) => prev.map((x) => (x.tool_id === t.tool_id ? { ...x, display_name: v } : x)));
                              }}
                              onBlur={(e) => patchTool(t.tool_id, { display_name: e.target.value })}
                              className="w-40 px-2 py-1 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[11px]"
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
