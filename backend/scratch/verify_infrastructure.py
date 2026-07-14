import asyncio
import sys
import os
import time

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock FastAPI config environment
os.environ["TSDB_TYPE"] = "duckdb"
os.environ["SQLITE_PATH"] = "telemetry.db"
os.environ["EDGE_API_KEY"] = "dev-key-001"

from app.ts_database import get_telemetry_store
from app.services.broker import get_message_broker
from app.models import TelemetryPacket
from app.services.ingestion import process_telemetry_core


async def test_duckdb():
    print("Testing DuckDB Telemetry Store...")
    store = get_telemetry_store()
    
    # Write test packet
    device_id = "test_device_1"
    device_type = "power"
    event = "reading"
    value = 2500.5
    unit = "W"
    timestamp = int(time.time())
    
    store.write_packet(
        device_id=device_id,
        device_type=device_type,
        event=event,
        value=value,
        unit=unit,
        timestamp=timestamp,
        battery_v=3.8,
        rssi_dbm=-60
    )
    print("✓ Successfully wrote telemetry packet to DuckDB.")
    
    # Read latest
    latest = store.get_latest(5)
    assert len(latest) >= 1, "Latest telemetry list should not be empty"
    found = False
    for item in latest:
        if item["device_id"] == device_id and item["value"] == value:
            found = True
            break
    assert found, "Could not retrieve the written telemetry packet from DuckDB"
    print("✓ Successfully retrieved packet from DuckDB.")
    
    # Test summary stats
    stats = store.get_summary_stats(timestamp - 3600)
    assert stats["avg_power_w"] is not None, "Summary stats avg power should be calculated"
    print(f"✓ Summary stats retrieved: {stats}")


async def test_message_broker():
    print("\nTesting Message Broker (with Virtual Fallback)...")
    broker = get_message_broker()
    await broker.start()
    
    received_msgs = []
    
    async def test_callback(topic, payload):
        print(f"  → Received message on topic '{topic}': {payload}")
        received_msgs.append(payload)
        
    await broker.subscribe("test/topic", test_callback)
    
    test_payload = {"hello": "world", "value": 42}
    await broker.publish("test/topic", test_payload)
    
    # Wait for dispatch queue
    await asyncio.sleep(0.5)
    
    assert len(received_msgs) == 1, "Should have received exactly 1 message"
    assert received_msgs[0]["value"] == 42, "Payload content mismatch"
    print("✓ Successfully published and subscribed via Message Broker.")
    await broker.stop()


async def main():
    print("=========================================")
    print("STARTING INFRASTRUCTURE VERIFICATION")
    print("=========================================")
    try:
        await test_duckdb()
        await test_message_broker()
        print("\n=========================================")
        print("ALL TESTS PASSED SUCCESSFULLY!")
        print("=========================================")
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
