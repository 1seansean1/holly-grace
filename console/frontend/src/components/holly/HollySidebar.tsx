/**
 * HollySidebar — persistent right-side chat panel.
 *
 * Always visible (unless collapsed) regardless of which page is active.
 * Consumes chat state from HollyContext.
 */

import { useEffect, useRef } from 'react';
import {
  Send,
  Loader2,
  Sparkles,
  Wrench,
  RefreshCw,
  PanelRightClose,
} from 'lucide-react';
import { useHolly } from '@/lib/HollyContext';
import ChatBubble from '@/components/holly/ChatBubble';
import ApprovalCard from '@/components/holly/ApprovalCard';

export default function HollySidebar() {
  const {
    entries,
    input,
    setInput,
    sending,
    isStreaming,
    handleSend,
    handleApprove,
    handleReject,
    handleClear,
    sidebarOpen,
    setSidebarOpen,
    chatEndRef,
  } = useHolly();

  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new entries
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries, isStreaming, chatEndRef]);

  // Keyboard: Enter to send, Shift+Enter for newline
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 100)}px`;
  };

  return (
    <>
      {/* Floating toggle when closed */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed right-0 top-1/2 -translate-y-1/2 z-50 bg-[var(--color-accent)] text-white p-2 rounded-l-lg shadow-lg hover:bg-[var(--color-accent-hover)] transition-colors"
          title="Open Holly Grace"
        >
          <Sparkles size={18} />
        </button>
      )}

      {/* Sidebar panel */}
      <aside
        className={`${
          sidebarOpen ? 'w-80' : 'w-0'
        } h-full flex flex-col bg-[var(--color-bg)] border-l border-[var(--color-border)] shrink-0 overflow-hidden transition-all duration-200`}
      >
        {/* Header */}
        <div className="h-10 px-3 flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-card)] shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-[var(--color-accent)]" />
            <span className="text-sm font-semibold text-[var(--color-text)]">Holly Grace</span>
          </div>
          <div className="flex items-center gap-0.5">
            <button
              onClick={handleClear}
              className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
              title="Clear conversation"
            >
              <RefreshCw size={13} />
            </button>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
              title="Collapse sidebar"
            >
              <PanelRightClose size={13} />
            </button>
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto px-3 py-3 min-h-0">
          {entries.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-[var(--color-text-muted)]">
              <Sparkles size={32} className="mb-3 opacity-20" />
              <p className="text-xs">Chat with Holly Grace</p>
            </div>
          )}

          {entries.map((entry, i) => {
            if (entry.kind === 'message') {
              return <ChatBubble key={i} message={entry.message} />;
            }
            if (entry.kind === 'approval') {
              return (
                <ApprovalCard
                  key={`ticket-${entry.card.ticket_id}`}
                  card={entry.card}
                  onApprove={handleApprove}
                  onReject={handleReject}
                />
              );
            }
            if (entry.kind === 'tool_activity') {
              return (
                <div key={i} className="flex justify-start mb-2">
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-muted)] bg-[var(--color-bg-hover)] px-2 py-1 rounded-full">
                    <Wrench size={10} />
                    <span>{entry.name}</span>
                    {entry.status === 'calling' && <Loader2 size={10} className="animate-spin" />}
                  </div>
                </div>
              );
            }
            return null;
          })}

          {/* Streaming indicator */}
          {isStreaming && (
            <div className="flex justify-start mb-3">
              <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-2xl rounded-bl-md px-3 py-2">
                <div className="text-[10px] font-semibold text-[var(--color-accent)] mb-1">Holly Grace</div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-[var(--color-accent)] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-[var(--color-accent)] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-[var(--color-accent)] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Input bar */}
        <div className="shrink-0 border-t border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 py-2">
          <div className="flex items-end gap-1.5">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Message Holly..."
              rows={1}
              className="flex-1 resize-none bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-[var(--color-text)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors"
              style={{ maxHeight: '100px' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="shrink-0 w-8 h-8 flex items-center justify-center rounded-lg bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] disabled:opacity-40 transition-colors"
            >
              {sending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Send size={14} />
              )}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
