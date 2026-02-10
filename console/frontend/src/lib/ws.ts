/**
 * WebSocket manager with auto-reconnect.
 * Singleton per path — survives React StrictMode double-mounts.
 */

export type WSEventHandler = (event: Record<string, unknown>) => void;
export type WSStateHandler = (connected: boolean) => void;

const _instances = new Map<string, WebSocketManager>();

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: Set<WSEventHandler> = new Set();
  private stateHandlers: Set<WSStateHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private running = false;
  private _connected = false;

  static get(path: string): WebSocketManager {
    if (!_instances.has(path)) {
      _instances.set(path, new WebSocketManager(path));
    }
    return _instances.get(path)!;
  }

  private constructor(path: string) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.url = `${protocol}//${window.location.host}${path}`;
  }

  get connected(): boolean {
    return this._connected;
  }

  subscribe(handler: WSEventHandler, stateHandler?: WSStateHandler): () => void {
    this.handlers.add(handler);
    if (stateHandler) this.stateHandlers.add(stateHandler);

    // Start connection if not already running
    if (!this.running) this.connect();

    // Send current state immediately
    if (stateHandler) stateHandler(this._connected);

    return () => {
      this.handlers.delete(handler);
      if (stateHandler) this.stateHandlers.delete(stateHandler);
      // Don't disconnect on unsubscribe — keep alive for reconnects
    };
  }

  private setConnected(value: boolean) {
    this._connected = value;
    this.stateHandlers.forEach((h) => h(value));
  }

  private connect() {
    this.running = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.setConnected(true);
      };

      this.ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data);
          this.handlers.forEach((h) => h(event));
        } catch { /* ignore parse errors */ }
      };

      this.ws.onclose = () => {
        this.setConnected(false);
        if (this.running) {
          this.reconnectTimer = setTimeout(() => this.connect(), 3000);
        }
      };

      this.ws.onerror = () => {
        // onclose will fire after onerror
      };
    } catch {
      this.setConnected(false);
      if (this.running) {
        this.reconnectTimer = setTimeout(() => this.connect(), 3000);
      }
    }
  }
}
