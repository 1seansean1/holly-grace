import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Archive,
  Download,
  Upload,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileJson,
  Clock,
  Shield,
  Trash2,
  Eye,
  ChevronDown,
  ChevronRight,
  X,
} from 'lucide-react';
import Header from '@/components/layout/Header';
import { fetchJson, postJson } from '@/lib/api';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface SystemImage {
  id: number;
  name: string;
  checksum: string;
  exported_at: string;
  image_data?: Record<string, unknown>;
}

interface ImportPreview {
  valid: boolean;
  format_version: string;
  exported_at: string;
  checksum_ok: boolean;
  summary: {
    agents: number;
    workflows: number;
    goals: number;
    cascade_config: boolean;
    assembly_entries: number;
  };
  changes: {
    agents_added: number;
    agents_updated: number;
    workflows_added: number;
    workflows_updated: number;
    goals_added: number;
    goals_updated: number;
    goals_removed: number;
  };
}

type ToastType = 'success' | 'error' | 'info';

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function SystemPage() {
  /* state -----------------------------------------------------------*/
  const [images, setImages] = useState<SystemImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileContent, setFileContent] = useState<Record<string, unknown> | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [toast, setToast] = useState<{ msg: string; type: ToastType } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  /* helpers ---------------------------------------------------------*/
  const showToast = (msg: string, type: ToastType = 'info') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchImages = useCallback(async () => {
    try {
      const data = await fetchJson<{ images: SystemImage[] }>('/api/system/images');
      setImages(data.images || []);
    } catch {
      setImages([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchImages(); }, [fetchImages]);

  /* export ----------------------------------------------------------*/
  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch('/api/system/export');
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.download = `system-image-${ts}.forge.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('System image exported', 'success');
      fetchImages();
    } catch (e: unknown) {
      showToast(`Export failed: ${e instanceof Error ? e.message : 'unknown error'}`, 'error');
    } finally {
      setExporting(false);
    }
  };

  /* file handling ---------------------------------------------------*/
  const processFile = async (file: File) => {
    if (!file.name.endsWith('.json') && !file.name.endsWith('.forge.json')) {
      showToast('Please select a .forge.json file', 'error');
      return;
    }
    try {
      const text = await file.text();
      const json = JSON.parse(text);
      if (json.format !== 'ecom-agents-system-image') {
        showToast('Invalid system image format', 'error');
        return;
      }
      setSelectedFile(file);
      setFileContent(json);
      setPreview(null);
      setPreviewOpen(false);
      showToast(`Loaded: ${file.name}`, 'info');
    } catch {
      showToast('Failed to parse JSON file', 'error');
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) processFile(e.dataTransfer.files[0]);
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setDragActive(true); };
  const handleDragLeave = () => setDragActive(false);
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) processFile(e.target.files[0]);
  };

  /* preview ---------------------------------------------------------*/
  const handlePreview = async () => {
    if (!fileContent) return;
    try {
      const data = await postJson<ImportPreview>('/api/system/import/preview', fileContent);
      setPreview(data);
      setPreviewOpen(true);
    } catch (e: unknown) {
      showToast(`Preview failed: ${e instanceof Error ? e.message : 'unknown'}`, 'error');
    }
  };

  /* import ----------------------------------------------------------*/
  const handleImport = async () => {
    if (!fileContent) return;
    setImporting(true);
    try {
      await postJson('/api/system/import', fileContent);
      showToast('System image imported successfully', 'success');
      setSelectedFile(null);
      setFileContent(null);
      setPreview(null);
      setPreviewOpen(false);
      fetchImages();
    } catch (e: unknown) {
      showToast(`Import failed: ${e instanceof Error ? e.message : 'unknown'}`, 'error');
    } finally {
      setImporting(false);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    setFileContent(null);
    setPreview(null);
    setPreviewOpen(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  /* download from history -------------------------------------------*/
  const handleDownloadImage = async (id: number) => {
    try {
      const data = await fetchJson<SystemImage>(`/api/system/images/${id}`);
      const blob = new Blob([JSON.stringify(data.image_data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `system-image-${id}.forge.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      showToast('Failed to download image', 'error');
    }
  };

  /* render ----------------------------------------------------------*/
  const fmtDate = (iso: string) => {
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="System" subtitle="Export, import, and manage system images" />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* ── Toast ─────────────────────────────────────────────── */}
        {toast && (
          <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg text-sm font-medium shadow-lg flex items-center gap-2 ${
            toast.type === 'success' ? 'bg-emerald-900/90 text-emerald-200 border border-emerald-700' :
            toast.type === 'error'   ? 'bg-red-900/90 text-red-200 border border-red-700' :
                                       'bg-blue-900/90 text-blue-200 border border-blue-700'
          }`}>
            {toast.type === 'success' && <CheckCircle size={14} />}
            {toast.type === 'error' && <XCircle size={14} />}
            {toast.type === 'info' && <AlertTriangle size={14} />}
            {toast.msg}
          </div>
        )}

        {/* ── Export Section ────────────────────────────────────── */}
        <section className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Download size={18} className="text-[var(--color-accent)]" />
              <h2 className="text-sm font-semibold">Export System Image</h2>
            </div>
            <button
              onClick={handleExport}
              disabled={exporting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {exporting ? <RefreshCw size={13} className="animate-spin" /> : <Archive size={13} />}
              {exporting ? 'Exporting…' : 'Download .forge.json'}
            </button>
          </div>
          <p className="text-xs text-[var(--color-text-muted)]">
            Captures agents, workflows, goals, cascade config, and assembly cache as a portable JSON file.
          </p>
        </section>

        {/* ── Import Section ───────────────────────────────────── */}
        <section className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Upload size={18} className="text-[var(--color-accent)]" />
            <h2 className="text-sm font-semibold">Import System Image</h2>
          </div>

          {/* Drop zone */}
          {!selectedFile ? (
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
                dragActive
                  ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10'
                  : 'border-[var(--color-border)] hover:border-[var(--color-text-muted)]'
              }`}
            >
              <FileJson size={36} className="mx-auto mb-3 text-[var(--color-text-muted)]" />
              <p className="text-sm text-[var(--color-text-muted)]">
                Drag & drop a <span className="font-mono text-[var(--color-accent)]">.forge.json</span> file here
              </p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">or click to browse</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>
          ) : (
            <div className="space-y-3">
              {/* File info bar */}
              <div className="flex items-center justify-between bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg px-4 py-3">
                <div className="flex items-center gap-2">
                  <FileJson size={16} className="text-[var(--color-accent)]" />
                  <span className="text-sm font-medium">{selectedFile.name}</span>
                  <span className="text-xs text-[var(--color-text-muted)]">
                    ({(selectedFile.size / 1024).toFixed(1)} KB)
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handlePreview}
                    className="flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-blue-950/30 text-blue-400 hover:bg-blue-950/50 transition-colors"
                  >
                    <Eye size={12} /> Preview
                  </button>
                  <button
                    onClick={handleImport}
                    disabled={importing}
                    className="flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
                  >
                    {importing ? <RefreshCw size={12} className="animate-spin" /> : <Upload size={12} />}
                    {importing ? 'Importing…' : 'Import'}
                  </button>
                  <button
                    onClick={clearFile}
                    className="p-1 rounded text-[var(--color-text-muted)] hover:text-red-400 transition-colors"
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>

              {/* Preview panel */}
              {preview && previewOpen && (
                <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">Import Preview</h3>
                    <div className="flex items-center gap-2">
                      {preview.checksum_ok ? (
                        <span className="flex items-center gap-1 text-xs text-emerald-400"><Shield size={12} /> Checksum valid</span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-red-400"><AlertTriangle size={12} /> Checksum mismatch</span>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: 'Agents', value: preview.summary.agents },
                      { label: 'Workflows', value: preview.summary.workflows },
                      { label: 'Goals', value: preview.summary.goals },
                      { label: 'Assembly', value: preview.summary.assembly_entries },
                    ].map(({ label, value }) => (
                      <div key={label} className="bg-[var(--color-bg-card)] rounded-lg px-3 py-2 text-center">
                        <div className="text-lg font-bold">{value}</div>
                        <div className="text-xs text-[var(--color-text-muted)]">{label}</div>
                      </div>
                    ))}
                  </div>

                  {/* Changes breakdown */}
                  {preview.changes && (
                    <div className="space-y-1">
                      <h4 className="text-xs font-semibold text-[var(--color-text-muted)]">Changes</h4>
                      <div className="flex flex-wrap gap-2 text-xs">
                        {preview.changes.agents_added > 0 && (
                          <span className="bg-emerald-950/30 text-emerald-400 px-2 py-0.5 rounded">+{preview.changes.agents_added} agents</span>
                        )}
                        {preview.changes.agents_updated > 0 && (
                          <span className="bg-amber-950/30 text-amber-400 px-2 py-0.5 rounded">~{preview.changes.agents_updated} agents</span>
                        )}
                        {preview.changes.workflows_added > 0 && (
                          <span className="bg-emerald-950/30 text-emerald-400 px-2 py-0.5 rounded">+{preview.changes.workflows_added} workflows</span>
                        )}
                        {preview.changes.workflows_updated > 0 && (
                          <span className="bg-amber-950/30 text-amber-400 px-2 py-0.5 rounded">~{preview.changes.workflows_updated} workflows</span>
                        )}
                        {preview.changes.goals_added > 0 && (
                          <span className="bg-emerald-950/30 text-emerald-400 px-2 py-0.5 rounded">+{preview.changes.goals_added} goals</span>
                        )}
                        {preview.changes.goals_updated > 0 && (
                          <span className="bg-amber-950/30 text-amber-400 px-2 py-0.5 rounded">~{preview.changes.goals_updated} goals</span>
                        )}
                        {preview.changes.goals_removed > 0 && (
                          <span className="bg-red-950/30 text-red-400 px-2 py-0.5 rounded">-{preview.changes.goals_removed} goals</span>
                        )}
                        {Object.values(preview.changes).every(v => v === 0) && (
                          <span className="text-[var(--color-text-muted)]">No changes detected — image matches current system</span>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="text-xs text-[var(--color-text-muted)]">
                    Format v{preview.format_version} · Exported {fmtDate(preview.exported_at)}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* ── Image History ────────────────────────────────────── */}
        <section className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl">
          <button
            onClick={() => setHistoryOpen(!historyOpen)}
            className="flex items-center gap-2 w-full px-5 py-4 text-left"
          >
            {historyOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <Clock size={16} className="text-[var(--color-accent)]" />
            <h2 className="text-sm font-semibold">Image History</h2>
            <span className="text-xs text-[var(--color-text-muted)] ml-auto">{images.length} images</span>
          </button>

          {historyOpen && (
            <div className="border-t border-[var(--color-border)]">
              {loading ? (
                <div className="flex items-center justify-center gap-2 py-8 text-xs text-[var(--color-text-muted)]">
                  <RefreshCw size={14} className="animate-spin" /> Loading…
                </div>
              ) : images.length === 0 ? (
                <div className="text-center py-8 text-xs text-[var(--color-text-muted)]">
                  No images yet. Export your first system image above.
                </div>
              ) : (
                <div className="divide-y divide-[var(--color-border)]">
                  {images.map((img) => (
                    <div key={img.id} className="flex items-center justify-between px-5 py-3 hover:bg-[var(--color-bg-hover)] transition-colors">
                      <div className="flex items-center gap-3">
                        <FileJson size={16} className="text-[var(--color-text-muted)]" />
                        <div>
                          <div className="text-sm font-medium">
                            {img.name || `Image #${img.id}`}
                          </div>
                          <div className="text-xs text-[var(--color-text-muted)]">
                            {fmtDate(img.exported_at)} · <span className="font-mono">{img.checksum?.slice(0, 16)}…</span>
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => handleDownloadImage(img.id)}
                        className="flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-bg)] transition-colors"
                      >
                        <Download size={12} /> Download
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>

      </div>
    </div>
  );
}
