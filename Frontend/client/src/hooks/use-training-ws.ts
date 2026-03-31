import { useEffect, useRef, useCallback, useState } from "react";

export interface EpisodeData {
  episode: number;
  total_episodes: number;
  reward: number;
  best_reward: number;
  avg_reward_last_50: number;
  epsilon: number;
  best_eval_reward: number;
  sku?: string;  // Present in multi-SKU mode
}

export interface TrainingWsStatus {
  type: "status";
  status: "running" | "completed" | "success" | "failed" | "failure" | "stopped" | "cancelled";
  total_episodes?: number;
  best_reward?: number;
  avg_reward_last_50?: number;
  message?: string;
}

type WsMessage = (EpisodeData & { type: "episode" }) | TrainingWsStatus;

interface UseTrainingWsOptions {
  /** Called for every episode update */
  onEpisode?: (data: EpisodeData) => void;
  /** Called when training completes or fails */
  onStatusChange?: (data: TrainingWsStatus) => void;
}

const HOSTNAME = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
const WS_URL = `ws://${HOSTNAME}:8000/ws/train`;

export function useTrainingWs(
  enabled: boolean,
  options: UseTrainingWsOptions = {}
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [connected, setConnected] = useState(false);

  // Keep latest callbacks in refs so we don't re-open the socket on every render
  const onEpisodeRef = useRef(options.onEpisode);
  onEpisodeRef.current = options.onEpisode;
  const onStatusRef = useRef(options.onStatusChange);
  onStatusRef.current = options.onStatusChange;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        if (msg.type === "episode") {
          onEpisodeRef.current?.(msg);
        } else if (msg.type === "status") {
          onStatusRef.current?.(msg);
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // Auto-reconnect if still enabled
      if (enabled) {
        reconnectTimer.current = setTimeout(connect, 2000);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [enabled]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [enabled, connect]);

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { connected, disconnect };
}
