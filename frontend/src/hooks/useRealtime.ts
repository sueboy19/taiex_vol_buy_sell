import { useEffect, useRef, useState } from "react";

import { getWsUrl } from "../api/client";
import type { RealtimeMessage } from "../types";

interface State {
  lastMessage: RealtimeMessage | null;
  connected: boolean;
}

export function useRealtime(enabled: boolean): State {
  const [lastMessage, setLastMessage] = useState<RealtimeMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let closed = false;

    const connect = () => {
      if (closed) return;
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) {
          reconnectRef.current = setTimeout(connect, 3000);
        }
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        try {
          setLastMessage(JSON.parse(event.data) as RealtimeMessage);
        } catch {
          /* ignore malformed */
        }
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [enabled]);

  return { lastMessage, connected };
}
