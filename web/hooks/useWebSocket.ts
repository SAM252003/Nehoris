import { useState, useEffect, useRef, useCallback } from 'react';

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

interface UseWebSocketOptions {
  onMessage?: (data: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [readyState, setReadyState] = useState<number>(WebSocket.CLOSED);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const {
    onMessage,
    onError,
    onOpen,
    onClose,
    reconnectAttempts = 3,
    reconnectInterval = 3000
  } = options;

  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const reconnectCountRef = useRef(0);
  const shouldConnectRef = useRef(true);

  const connect = useCallback(() => {
    if (!shouldConnectRef.current) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('🔗 WebSocket connecté:', url);
        setReadyState(WebSocket.OPEN);
        setConnectionError(null);
        reconnectCountRef.current = 0;
        onOpen?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          onMessage?.(data);
        } catch (error) {
          console.error('❌ Erreur parsing WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ Erreur WebSocket:', error);
        setConnectionError('Erreur de connexion WebSocket');
        onError?.(error);
      };

      ws.onclose = (event) => {
        console.log('🔌 WebSocket fermé:', event.code, event.reason);
        setReadyState(WebSocket.CLOSED);
        setSocket(null);
        onClose?.();

        // Auto-reconnexion si nécessaire
        if (shouldConnectRef.current &&
            reconnectCountRef.current < reconnectAttempts &&
            event.code !== 1000) { // 1000 = fermeture normale

          reconnectCountRef.current++;
          console.log(`🔄 Tentative de reconnexion ${reconnectCountRef.current}/${reconnectAttempts} dans ${reconnectInterval}ms...`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      setSocket(ws);
      setReadyState(WebSocket.CONNECTING);

    } catch (error) {
      console.error('❌ Erreur création WebSocket:', error);
      setConnectionError('Impossible de créer la connexion WebSocket');
    }
  }, [url, onMessage, onError, onOpen, onClose, reconnectAttempts, reconnectInterval]);

  const disconnect = useCallback(() => {
    shouldConnectRef.current = false;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close(1000, 'Fermeture volontaire');
    }
  }, [socket]);

  const sendMessage = useCallback((data: any) => {
    if (socket && readyState === WebSocket.OPEN) {
      try {
        const message = typeof data === 'string' ? data : JSON.stringify(data);
        socket.send(message);
        return true;
      } catch (error) {
        console.error('❌ Erreur envoi message WebSocket:', error);
        return false;
      }
    }
    return false;
  }, [socket, readyState]);

  const reconnect = useCallback(() => {
    disconnect();
    setTimeout(() => {
      shouldConnectRef.current = true;
      reconnectCountRef.current = 0;
      connect();
    }, 100);
  }, [disconnect, connect]);

  // Connexion initiale
  useEffect(() => {
    connect();

    return () => {
      shouldConnectRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  // Nettoyage au démontage
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    socket,
    lastMessage,
    readyState,
    connectionError,
    sendMessage,
    reconnect,
    disconnect,
    // États de connexion helpers
    isConnecting: readyState === WebSocket.CONNECTING,
    isOpen: readyState === WebSocket.OPEN,
    isClosing: readyState === WebSocket.CLOSING,
    isClosed: readyState === WebSocket.CLOSED,
  };
}