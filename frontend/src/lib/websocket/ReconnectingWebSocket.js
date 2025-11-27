/**
 * ReconnectingWebSocket - Automatic reconnection for WebSocket
 * Provides automatic reconnection, exponential backoff, and event handling
 */

export class ReconnectingWebSocket extends EventTarget {
  /**
   * Create a new ReconnectingWebSocket
   * @param {string} url - WebSocket URL
   * @param {Object} options - Configuration options
   */
  constructor(url, options = {}) {
    super();

    this.url = url;
    this.options = {
      reconnectInterval: options.reconnectInterval || 1000,
      maxReconnectInterval: options.maxReconnectInterval || 30000,
      reconnectDecay: options.reconnectDecay || 1.5,
      maxReconnectAttempts: options.maxReconnectAttempts || null,
      timeoutInterval: options.timeoutInterval || 2000,
      automaticOpen: options.automaticOpen !== false,
      debug: options.debug || false,
      binaryType: options.binaryType || 'blob',
      protocols: options.protocols || []
    };

    // State
    this.ws = null;
    this.forcedClose = false;
    this.reconnectAttempts = 0;
    this.readyState = WebSocket.CONNECTING;
    this.messageQueue = [];

    // Timers
    this.reconnectTimer = null;
    this.timeoutTimer = null;

    // Bind methods
    this.open = this.open.bind(this);
    this.close = this.close.bind(this);
    this.send = this.send.bind(this);
    this.refresh = this.refresh.bind(this);

    if (this.options.automaticOpen) {
      this.open();
    }
  }

  /**
   * Open WebSocket connection
   * @param {boolean} reconnect - Whether this is a reconnection attempt
   */
  open(reconnect = false) {
    this.forcedClose = false;

    if (this.ws && (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.log('Connecting to ' + this.url);

    try {
      if (this.options.protocols.length > 0) {
        this.ws = new WebSocket(this.url, this.options.protocols);
      } else {
        this.ws = new WebSocket(this.url);
      }

      this.ws.binaryType = this.options.binaryType;

      // Set up event handlers
      this.ws.onopen = this.onOpen.bind(this);
      this.ws.onclose = this.onClose.bind(this);
      this.ws.onmessage = this.onMessage.bind(this);
      this.ws.onerror = this.onError.bind(this);

      // Set connection timeout
      this.timeoutTimer = setTimeout(() => {
        this.log('Connection timeout');
        this.timedOut = true;
        this.ws.close();
        this.timedOut = false;
      }, this.options.timeoutInterval);

    } catch (error) {
      this.log('Error creating WebSocket: ' + error);
      this.dispatchEvent(new CustomEvent('error', { detail: error }));
      this.reconnect();
    }
  }

  /**
   * Close WebSocket connection
   * @param {number} code - Close code
   * @param {string} reason - Close reason
   */
  close(code = 1000, reason = '') {
    this.forcedClose = true;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.timeoutTimer) {
      clearTimeout(this.timeoutTimer);
      this.timeoutTimer = null;
    }

    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.close(code, reason);
      } else {
        this.ws.onopen = null;
        this.ws.onclose = null;
        this.ws.onmessage = null;
        this.ws.onerror = null;
      }
    }

    this.readyState = WebSocket.CLOSED;
  }

  /**
   * Send data through WebSocket
   * @param {string|ArrayBuffer|Blob} data - Data to send
   */
  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.log('Sending: ' + data);
      this.ws.send(data);
    } else {
      // Queue message if not connected
      this.messageQueue.push(data);
      this.log('Queued message: ' + data);

      // Try to reconnect if not already trying
      if (this.readyState !== WebSocket.CONNECTING) {
        this.open();
      }
    }
  }

  /**
   * Refresh connection (close and reopen)
   */
  refresh() {
    this.close();
    this.open();
  }

  /**
   * Handle connection open
   * @private
   */
  onOpen(event) {
    clearTimeout(this.timeoutTimer);
    this.log('Connected');

    this.readyState = WebSocket.OPEN;
    this.reconnectAttempts = 0;

    // Send queued messages
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      this.send(message);
    }

    // Dispatch open event
    this.dispatchEvent(new CustomEvent('open', { detail: event }));
  }

  /**
   * Handle connection close
   * @private
   */
  onClose(event) {
    clearTimeout(this.timeoutTimer);

    this.ws = null;
    this.readyState = WebSocket.CLOSED;

    if (this.forcedClose) {
      this.log('Connection closed by user');
      this.dispatchEvent(new CustomEvent('close', { detail: event }));
    } else {
      this.log('Connection lost, will reconnect');
      this.dispatchEvent(new CustomEvent('disconnect', { detail: event }));
      this.reconnect();
    }
  }

  /**
   * Handle incoming message
   * @private
   */
  onMessage(event) {
    this.log('Received: ' + event.data);

    // Try to parse JSON if possible
    let data = event.data;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      // Not JSON, use raw data
    }

    // Dispatch message event
    this.dispatchEvent(new CustomEvent('message', {
      detail: {
        data: data,
        raw: event.data,
        event: event
      }
    }));
  }

  /**
   * Handle connection error
   * @private
   */
  onError(event) {
    this.log('Error: ' + event);
    this.dispatchEvent(new CustomEvent('error', { detail: event }));
  }

  /**
   * Attempt to reconnect
   * @private
   */
  reconnect() {
    if (this.forcedClose) {
      return;
    }

    // Check max attempts
    if (this.options.maxReconnectAttempts !== null &&
        this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      this.log('Max reconnection attempts reached');
      this.dispatchEvent(new CustomEvent('maxreconnect'));
      return;
    }

    this.reconnectAttempts++;

    // Calculate delay with exponential backoff
    const delay = Math.min(
      this.options.reconnectInterval * Math.pow(
        this.options.reconnectDecay,
        this.reconnectAttempts - 1
      ),
      this.options.maxReconnectInterval
    );

    this.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    this.dispatchEvent(new CustomEvent('reconnecting', {
      detail: {
        attempt: this.reconnectAttempts,
        delay: delay
      }
    }));

    this.reconnectTimer = setTimeout(() => {
      this.open(true);
    }, delay);
  }

  /**
   * Log message if debug is enabled
   * @private
   */
  log(message) {
    if (this.options.debug) {
      console.log('[ReconnectingWebSocket]', message);
    }
  }

  /**
   * Get current state as string
   */
  get state() {
    switch (this.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'open';
      case WebSocket.CLOSING:
        return 'closing';
      case WebSocket.CLOSED:
        return 'closed';
      default:
        return 'unknown';
    }
  }

  /**
   * Check if connected
   */
  get connected() {
    return this.readyState === WebSocket.OPEN;
  }
}

/**
 * Create a WebSocket store for Svelte
 * @param {string} url - WebSocket URL
 * @param {Object} options - Connection options
 */
export function createWebSocketStore(url, options = {}) {
  let ws = null;
  const subscribers = new Set();

  const state = {
    connected: false,
    connecting: false,
    messages: [],
    lastError: null,
    reconnectAttempts: 0
  };

  function notify() {
    const currentState = { ...state };
    subscribers.forEach(callback => callback(currentState));
  }

  function connect() {
    if (ws && ws.connected) {
      return;
    }

    state.connecting = true;
    notify();

    ws = new ReconnectingWebSocket(url, {
      ...options,
      debug: options.debug || false
    });

    ws.addEventListener('open', () => {
      state.connected = true;
      state.connecting = false;
      state.reconnectAttempts = 0;
      state.lastError = null;
      notify();
    });

    ws.addEventListener('close', () => {
      state.connected = false;
      state.connecting = false;
      notify();
    });

    ws.addEventListener('message', (event) => {
      state.messages.push(event.detail.data);
      // Keep only last 100 messages
      if (state.messages.length > 100) {
        state.messages.shift();
      }
      notify();
    });

    ws.addEventListener('error', (event) => {
      state.lastError = event.detail;
      notify();
    });

    ws.addEventListener('reconnecting', (event) => {
      state.connecting = true;
      state.reconnectAttempts = event.detail.attempt;
      notify();
    });
  }

  function disconnect() {
    if (ws) {
      ws.close();
      ws = null;
    }
    state.connected = false;
    state.connecting = false;
    notify();
  }

  function send(data) {
    if (ws) {
      ws.send(typeof data === 'object' ? JSON.stringify(data) : data);
    }
  }

  // Auto-connect on first subscription
  function subscribe(callback) {
    if (subscribers.size === 0) {
      connect();
    }

    subscribers.add(callback);
    callback({ ...state });

    return () => {
      subscribers.delete(callback);
      if (subscribers.size === 0) {
        disconnect();
      }
    };
  }

  return {
    subscribe,
    send,
    connect,
    disconnect
  };
}

export default ReconnectingWebSocket;