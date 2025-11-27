"""WebSocket connection manager"""

from typing import Dict, Set, List, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections and message broadcasting"""

    def __init__(self):
        """Initialize connection manager"""
        # Active WebSocket connections
        self._connections: Dict[str, WebSocket] = {}

        # Subscription tracking
        self._subscriptions: Dict[str, Set[str]] = {}  # event -> connection_ids
        self._connection_subscriptions: Dict[str, Set[str]] = {}  # connection_id -> events

        # Connection metadata
        self._connection_info: Dict[str, Dict[str, Any]] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Accept a new WebSocket connection

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection identifier
            client_info: Optional client metadata
        """
        await websocket.accept()

        async with self._lock:
            self._connections[connection_id] = websocket
            self._connection_subscriptions[connection_id] = set()
            self._connection_info[connection_id] = {
                "connected_at": datetime.utcnow().isoformat(),
                "client_info": client_info or {}
            }

        logger.info(f"WebSocket connection established: {connection_id}")

        # Send welcome message
        await self.send_to_connection(connection_id, {
            "type": "connected",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def disconnect(self, connection_id: str) -> None:
        """Remove a WebSocket connection

        Args:
            connection_id: Connection identifier to remove
        """
        async with self._lock:
            # Remove from active connections
            if connection_id in self._connections:
                del self._connections[connection_id]

            # Remove all subscriptions for this connection
            if connection_id in self._connection_subscriptions:
                for event in self._connection_subscriptions[connection_id]:
                    if event in self._subscriptions:
                        self._subscriptions[event].discard(connection_id)
                        if not self._subscriptions[event]:
                            del self._subscriptions[event]

                del self._connection_subscriptions[connection_id]

            # Remove connection info
            if connection_id in self._connection_info:
                del self._connection_info[connection_id]

        logger.info(f"WebSocket connection closed: {connection_id}")

    async def subscribe(
        self,
        connection_id: str,
        event: str,
        filter_params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Subscribe a connection to an event

        Args:
            connection_id: Connection identifier
            event: Event name to subscribe to
            filter_params: Optional filtering parameters

        Returns:
            bool: True if subscription was successful
        """
        async with self._lock:
            if connection_id not in self._connections:
                logger.warning(f"Cannot subscribe: connection {connection_id} not found")
                return False

            # Track subscription
            if event not in self._subscriptions:
                self._subscriptions[event] = set()
            self._subscriptions[event].add(connection_id)
            self._connection_subscriptions[connection_id].add(event)

            # Store filter parameters if provided
            if filter_params:
                self._connection_info[connection_id].setdefault("filters", {})[event] = filter_params

        logger.debug(f"Connection {connection_id} subscribed to {event}")

        # Send confirmation
        await self.send_to_connection(connection_id, {
            "type": "subscribed",
            "event": event,
            "timestamp": datetime.utcnow().isoformat()
        })

        return True

    async def unsubscribe(self, connection_id: str, event: str) -> bool:
        """Unsubscribe a connection from an event

        Args:
            connection_id: Connection identifier
            event: Event name to unsubscribe from

        Returns:
            bool: True if unsubscription was successful
        """
        async with self._lock:
            if connection_id not in self._connections:
                return False

            # Remove subscription
            if event in self._subscriptions:
                self._subscriptions[event].discard(connection_id)
                if not self._subscriptions[event]:
                    del self._subscriptions[event]

            if connection_id in self._connection_subscriptions:
                self._connection_subscriptions[connection_id].discard(event)

            # Remove filter if exists
            if connection_id in self._connection_info:
                filters = self._connection_info[connection_id].get("filters", {})
                if event in filters:
                    del filters[event]

        logger.debug(f"Connection {connection_id} unsubscribed from {event}")

        # Send confirmation
        await self.send_to_connection(connection_id, {
            "type": "unsubscribed",
            "event": event,
            "timestamp": datetime.utcnow().isoformat()
        })

        return True

    async def broadcast(
        self,
        event: str,
        data: Any,
        filter_key: Optional[str] = None,
        filter_value: Optional[Any] = None
    ) -> int:
        """Broadcast a message to all subscribed connections

        Args:
            event: Event name
            data: Data to broadcast
            filter_key: Optional filter key for targeted broadcasting
            filter_value: Optional filter value

        Returns:
            int: Number of connections that received the message
        """
        message = {
            "event": event,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }

        sent_count = 0
        disconnected = []

        # Get subscribers for this event
        async with self._lock:
            subscribers = list(self._subscriptions.get(event, []))

        for connection_id in subscribers:
            # Check filters if provided
            if filter_key and filter_value:
                async with self._lock:
                    filters = self._connection_info.get(connection_id, {}).get("filters", {}).get(event, {})
                    if filter_key in filters and filters[filter_key] != filter_value:
                        continue

            # Send message
            success = await self.send_to_connection(connection_id, message)
            if success:
                sent_count += 1
            else:
                disconnected.append(connection_id)

        # Clean up disconnected connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)

        if sent_count > 0:
            logger.debug(f"Broadcasted {event} to {sent_count} connections")

        return sent_count

    async def send_to_connection(
        self,
        connection_id: str,
        data: Any
    ) -> bool:
        """Send a message to a specific connection

        Args:
            connection_id: Connection identifier
            data: Data to send

        Returns:
            bool: True if message was sent successfully
        """
        async with self._lock:
            websocket = self._connections.get(connection_id)

        if not websocket:
            logger.warning(f"Cannot send: connection {connection_id} not found")
            return False

        try:
            # Convert data to JSON if needed
            if isinstance(data, dict):
                message = json.dumps(data)
            else:
                message = str(data)

            await websocket.send_text(message)
            return True

        except WebSocketDisconnect:
            logger.info(f"Connection {connection_id} disconnected during send")
            await self.disconnect(connection_id)
            return False

        except Exception as e:
            logger.error(f"Error sending to connection {connection_id}: {e}")
            return False

    async def handle_message(
        self,
        connection_id: str,
        message: str
    ) -> None:
        """Handle an incoming message from a connection

        Args:
            connection_id: Connection identifier
            message: Incoming message
        """
        try:
            # Parse JSON message
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "subscribe":
                event = data.get("event")
                filters = data.get("filters")
                if event:
                    await self.subscribe(connection_id, event, filters)

            elif msg_type == "unsubscribe":
                event = data.get("event")
                if event:
                    await self.unsubscribe(connection_id, event)

            elif msg_type == "ping":
                # Respond to ping
                await self.send_to_connection(connection_id, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

            else:
                logger.debug(f"Unknown message type from {connection_id}: {msg_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {connection_id}: {message}")
        except Exception as e:
            logger.error(f"Error handling message from {connection_id}: {e}")

    def get_connection_count(self) -> int:
        """Get number of active connections

        Returns:
            int: Number of active connections
        """
        return len(self._connections)

    def get_subscription_info(self) -> Dict[str, Any]:
        """Get subscription statistics

        Returns:
            Dict[str, Any]: Subscription information
        """
        return {
            "total_connections": len(self._connections),
            "events": {
                event: len(subscribers)
                for event, subscribers in self._subscriptions.items()
            },
            "connections": {
                conn_id: {
                    "subscriptions": list(events),
                    "connected_at": self._connection_info.get(conn_id, {}).get("connected_at")
                }
                for conn_id, events in self._connection_subscriptions.items()
            }
        }

# Global connection manager instance
connection_manager = ConnectionManager()