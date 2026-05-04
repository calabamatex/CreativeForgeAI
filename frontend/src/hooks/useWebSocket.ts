import { useEffect, useRef, useState, useCallback } from "react";

interface WSMessage {
  type: string;
  job_id: string;
  stage?: string;
  progress_percent?: number;
  message?: string;
}

export function useWebSocket(jobId: string | null) {
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    if (!jobId) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/generation/${jobId}`);

    ws.onopen = () => setIsConnected(true);
    ws.onmessage = (event) => setLastMessage(JSON.parse(event.data));
    ws.onclose = () => {
      setIsConnected(false);
      reconnectTimeout.current = setTimeout(connect, 3000);
    };
    ws.onerror = () => ws.close();

    wsRef.current = ws;
  }, [jobId]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { lastMessage, isConnected };
}
