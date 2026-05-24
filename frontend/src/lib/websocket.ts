// lib/websocket.ts
type MessageHandler = (data: any) => void;

export class LiveTimingClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 5000;
  private isIntentionalClose = false;
  
  private handlers: Set<MessageHandler> = new Set();

  constructor() {
    this.url = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/live/ws";
  }

  public getConnectedStatus(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  public connect() {
    if (typeof window === "undefined") return; // SSR check
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isIntentionalClose = false;
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log("[LiveTiming] WebSocket connected");
      this.reconnectAttempts = 0;
      this.handlers.forEach(handler => handler({ type: "ws_status", connected: true }));
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "ping") return; // Ignore keepalives
        
        // Broadcast to all registered React hooks
        this.handlers.forEach(handler => handler(data));
      } catch (e) {
        console.error("[LiveTiming] Failed to parse message", e);
      }
    };

    this.ws.onclose = () => {
      console.log("[LiveTiming] WebSocket disconnected");
      this.handlers.forEach(handler => handler({ type: "ws_status", connected: false }));
      if (!this.isIntentionalClose) {
        this.attemptReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error("[LiveTiming] WebSocket error", error);
      // onclose will trigger reconnect
    };
  }

  public disconnect() {
    this.isIntentionalClose = true;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn("[LiveTiming] Max reconnect attempts reached");
      return;
    }
    this.reconnectAttempts++;
    console.log(`[LiveTiming] Reconnecting... (Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    setTimeout(() => this.connect(), this.reconnectDelay);
  }

  // Pub/Sub for React components
  public subscribe(handler: MessageHandler) {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }
}

// Singleton instance
export const liveTimingClient = new LiveTimingClient();
