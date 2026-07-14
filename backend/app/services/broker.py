import abc
import json
import logging
import asyncio
from typing import Any, Callable, Dict, List
import paho.mqtt.client as mqtt
from app.config import settings

logger = logging.getLogger("edge.broker")

class MessageBroker(abc.ABC):
    """Abstract interface for the digital twin message broker."""

    @abc.abstractmethod
    async def start(self) -> None:
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        pass

    @abc.abstractmethod
    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        pass

    @abc.abstractmethod
    async def subscribe(self, topic: str, callback: Callable[[str, Dict[str, Any]], Any]) -> None:
        pass


class MQTTMessageBroker(MessageBroker):
    """Real MQTT message broker wrapper using paho-mqtt client."""

    def __init__(self):
        self.host = settings.mqtt_broker_host
        self.port = settings.mqtt_broker_port
        self.client_id = settings.mqtt_client_id
        
        # Paho MQTT Client setup
        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._subscriptions: Dict[str, List[Callable[[str, Dict[str, Any]], Any]]] = {}
        self._loop_running = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Successfully connected to MQTT broker at {self.host}:{self.port}")
            # Re-subscribe to active subscriptions
            for topic in self._subscriptions:
                self.client.subscribe(topic)
                logger.info(f"MQTT re-subscribed to topic: {topic}")
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_str = msg.payload.decode("utf-8")
        try:
            payload = json.loads(payload_str)
        except Exception:
            payload = {"raw_payload": payload_str}
            
        # Match topic callbacks (simple exact matching for our topics)
        callbacks = self._subscriptions.get(topic, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(topic, payload))
                else:
                    callback(topic, payload)
            except Exception as e:
                logger.error(f"Error in MQTT topic callback for {topic}: {e}")

    async def start(self) -> None:
        # Connect in a non-blocking way
        logger.info(f"Connecting to MQTT Broker at {self.host}:{self.port}...")
        
        # We run the socket loop in an executor or use start_loop
        self.client.connect_async(self.host, self.port, keepalive=60)
        self.client.loop_start()
        self._loop_running = True
        
        # Give it a brief moment to connect
        await asyncio.sleep(0.5)

    async def stop(self) -> None:
        if self._loop_running:
            self.client.loop_stop()
            self._loop_running = False
        self.client.disconnect()
        logger.info("MQTT Broker client stopped.")

    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        try:
            self.client.publish(topic, json.dumps(payload))
            logger.debug(f"MQTT Published to {topic}: {payload}")
        except Exception as e:
            logger.error(f"MQTT Publish failed for topic {topic}: {e}")

    async def subscribe(self, topic: str, callback: Callable[[str, Dict[str, Any]], Any]) -> None:
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
            if self.client.is_connected():
                self.client.subscribe(topic)
                logger.info(f"MQTT Subscribed to topic: {topic}")
        self._subscriptions[topic].append(callback)


class VirtualMessageBroker(MessageBroker):
    """In-memory asyncio queue message broker fallback (for local demo runs without Docker/Mosquitto)."""

    def __init__(self):
        self._subscriptions: Dict[str, List[Callable[[str, Dict[str, Any]], Any]]] = {}
        self.queue: asyncio.Queue[tuple[str, Dict[str, Any]]] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.warning("Using Virtual Message Broker (In-Memory Fallback). Start Mosquitto to use real MQTT.")

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Virtual Message Broker stopped.")

    async def _process_queue(self):
        while self._running:
            try:
                topic, payload = await self.queue.get()
                
                # Simple wildcard mapping (supports exact matching and 'path/#' prefix matching)
                for registered_topic, callbacks in self._subscriptions.items():
                    matched = False
                    if registered_topic == topic:
                        matched = True
                    elif registered_topic.endswith("/#"):
                        prefix = registered_topic[:-2]
                        if topic.startswith(prefix):
                            matched = True
                            
                    if matched:
                        for callback in callbacks:
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(topic, payload)
                                else:
                                    callback(topic, payload)
                            except Exception as e:
                                logger.error(f"Error in Virtual Broker callback for topic {topic}: {e}")
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Virtual Broker dispatch loop: {e}")
                await asyncio.sleep(0.1)

    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        await self.queue.put((topic, payload))
        logger.debug(f"Virtual Broker Published to {topic}: {payload}")

    async def subscribe(self, topic: str, callback: Callable[[str, Dict[str, Any]], Any]) -> None:
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(callback)
        logger.info(f"Virtual Broker Subscribed to topic: {topic}")


# Singleton instances
_mqtt_broker = None
_virtual_broker = None
_active_broker = None

def get_message_broker() -> MessageBroker:
    global _mqtt_broker, _virtual_broker, _active_broker
    if _active_broker is not None:
        return _active_broker
        
    # Check if we can connect to real MQTT broker
    import socket
    mqtt_available = False
    try:
        # Quick socket check
        s = socket.create_connection((settings.mqtt_broker_host, settings.mqtt_broker_port), timeout=0.5)
        s.close()
        mqtt_available = True
    except Exception:
        pass
        
    if mqtt_available:
        try:
            _mqtt_broker = MQTTMessageBroker()
            _active_broker = _mqtt_broker
            logger.info("Initializing active real MQTT broker connection")
        except Exception as e:
            logger.error(f"Failed to create MQTT broker wrapper, using virtual fallback: {e}")
            _virtual_broker = VirtualMessageBroker()
            _active_broker = _virtual_broker
    else:
        _virtual_broker = VirtualMessageBroker()
        _active_broker = _virtual_broker
        
    return _active_broker
