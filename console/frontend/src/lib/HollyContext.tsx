/**
 * HollyContext — persistent chat state for Holly Grace.
 *
 * Wraps the Shell layout so chat state survives route changes.
 * The HollySidebar component consumes this context to render the UI.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { fetchJson, postJson } from '@/lib/api';
import type { ApprovalCardData, ChatEntry, HollyMessage } from '@/types/holly';

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface HollyContextValue {
  entries: ChatEntry[];
  input: string;
  setInput: (v: string) => void;
  sending: boolean;
  isStreaming: boolean;
  handleSend: () => Promise<void>;
  handleApprove: (ticketId: number) => Promise<void>;
  handleReject: (ticketId: number) => Promise<void>;
  handleClear: () => Promise<void>;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  chatEndRef: React.RefObject<HTMLDivElement | null>;
}

const HollyContext = createContext<HollyContextValue | null>(null);

export function useHolly() {
  const ctx = useContext(HollyContext);
  if (!ctx) throw new Error('useHolly must be used inside HollyProvider');
  return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function HollyProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // Sidebar open state — persisted in localStorage
  const [sidebarOpen, setSidebarOpenRaw] = useState(() => {
    const saved = localStorage.getItem('holly-sidebar-open');
    return saved !== 'false'; // default open
  });

  const setSidebarOpen = useCallback((open: boolean) => {
    setSidebarOpenRaw(open);
    localStorage.setItem('holly-sidebar-open', String(open));
  }, []);

  // Load session + greeting on mount
  useEffect(() => {
    loadSession();
    loadGreeting();
  }, []);

  const loadSession = async () => {
    try {
      const data = await fetchJson<{ messages: HollyMessage[] }>('/api/holly/session');
      if (data.messages?.length) {
        setEntries(data.messages.map((m) => ({ kind: 'message' as const, message: m })));
      }
    } catch {
      // fresh session
    }
  };

  const loadGreeting = async () => {
    try {
      const data = await fetchJson<{ greeting: string }>('/api/holly/greeting');
      if (data.greeting) {
        setEntries((prev) => {
          if (prev.length > 0) return prev; // don't overwrite existing
          return [{
            kind: 'message',
            message: { role: 'holly', content: data.greeting, ts: new Date().toISOString() },
          }];
        });
      }
    } catch {
      // use default
    }
  };

  // Poll pending tickets as approval cards
  useEffect(() => {
    const loadTickets = async () => {
      try {
        const data = await fetchJson<{ tickets: ApprovalCardData[] }>(
          '/api/tower/inbox?status=pending&limit=10'
        );
        if (data.tickets?.length) {
          setEntries((prev) => {
            const existingIds = new Set(
              prev
                .filter((e): e is { kind: 'approval'; card: ApprovalCardData } => e.kind === 'approval')
                .map((e) => e.card.ticket_id)
            );
            const newCards: ChatEntry[] = data.tickets
              .filter((t) => !existingIds.has(t.ticket_id ?? (t as any).id))
              .map((t) => ({
                kind: 'approval' as const,
                card: {
                  ticket_id: t.ticket_id ?? (t as any).id,
                  run_id: t.run_id,
                  ticket_type: t.ticket_type,
                  risk_level: t.risk_level,
                  status: t.status,
                  tldr: t.tldr || (t as any).context_pack?.tldr || '',
                  why_stopped: t.why_stopped || (t as any).context_pack?.why_stopped || '',
                  created_at: t.created_at,
                },
              }));
            if (newCards.length) return [...prev, ...newCards];
            return prev;
          });
        }
      } catch {
        // ignore
      }
    };
    loadTickets();
    const timer = setInterval(loadTickets, 10000);
    return () => clearInterval(timer);
  }, []);

  // Send message
  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;

    const humanMsg: HollyMessage = {
      role: 'human',
      content: text,
      ts: new Date().toISOString(),
    };
    setEntries((prev) => [...prev, { kind: 'message', message: humanMsg }]);
    setInput('');
    setSending(true);
    setIsStreaming(true);

    try {
      const data = await postJson<{ response: string }>('/api/holly/message', {
        message: text,
        session_id: 'default',
      });

      setIsStreaming(false);
      if (data.response) {
        const hollyMsg: HollyMessage = {
          role: 'holly',
          content: data.response,
          ts: new Date().toISOString(),
        };
        setEntries((prev) => [...prev, { kind: 'message', message: hollyMsg }]);
      }
    } catch {
      setIsStreaming(false);
      const errorMsg: HollyMessage = {
        role: 'holly',
        content: 'Sorry, I encountered an error processing your message. Please try again.',
        ts: new Date().toISOString(),
      };
      setEntries((prev) => [...prev, { kind: 'message', message: errorMsg }]);
    } finally {
      setSending(false);
    }
  }, [input, sending]);

  // Approve / reject tickets
  const handleApprove = useCallback(async (ticketId: number) => {
    try {
      await postJson('/api/holly/message', {
        message: `Approve ticket #${ticketId}`,
        session_id: 'default',
      });
      setEntries((prev) =>
        prev.map((e) =>
          e.kind === 'approval' && e.card.ticket_id === ticketId
            ? { ...e, card: { ...e.card, status: 'approved' } }
            : e
        )
      );
    } catch {
      // ignore
    }
  }, []);

  const handleReject = useCallback(async (ticketId: number) => {
    try {
      await postJson('/api/holly/message', {
        message: `Reject ticket #${ticketId}`,
        session_id: 'default',
      });
      setEntries((prev) =>
        prev.map((e) =>
          e.kind === 'approval' && e.card.ticket_id === ticketId
            ? { ...e, card: { ...e.card, status: 'rejected' } }
            : e
        )
      );
    } catch {
      // ignore
    }
  }, []);

  // Clear session
  const handleClear = useCallback(async () => {
    try {
      await postJson('/api/holly/clear', { session_id: 'default' });
      setEntries([]);
      loadGreeting();
    } catch {
      // ignore
    }
  }, []);

  return (
    <HollyContext.Provider
      value={{
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
      }}
    >
      {children}
    </HollyContext.Provider>
  );
}
