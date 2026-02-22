# test_razorpay_orders.py

"""
Test script for Razorpay Orders connector.

Usage:
    python test_razorpay_orders.py
"""

import logging
import sys
from datetime import datetime, timedelta

# Import our connector
from data_connectors.sources.razorpay.orders_connector import RazorpayOrdersConnector

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # Show all logs including DEBUG
)


def test_fetch_orders() -> bool:
    """Test fetching orders from Razorpay."""

    print("\n" + "=" * 60)
    print("Testing Razorpay Orders Connector")
    print("=" * 60 + "\n")

    # Configuration with your credentials
    config = {
        "source_config": {
            "api_key": "rzp_test_SIscntO0Xjha9C",  # ← Replace this
            "api_secret": "C9hIN19xyMusQlalMBLfUMzj",  # ← Replace this
            "base_url": "https://api.razorpay.com/v1",
        },
    }

    # Create connector
    print("1. Initializing connector...")
    connector = RazorpayOrdersConnector(config)
    print("   ✓ Connector initialized\n")

    # Test 1: Fetch all orders (no time filter)
    print("2. Fetching ALL orders...")
    print("-" * 60)

    order_count = 0
    try:
        for order in connector.extract():
            order_count += 1
            print(f"\nOrder {order_count}:")
            print(f"  ID:          {order['id']}")
            print(f"  Amount:      ₹{order['amount']}")
            print(f"  Status:      {order['status']}")
            print(f"  Created:     {order['created_at']}")
            print(f"  Receipt:     {order['receipt']}")

            # Only show first 5 orders to avoid spam
            if order_count >= 5:
                print("\n  ... (showing only first 5)")
                break

        print(f"\n✓ Successfully fetched {order_count} orders")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 2: Fetch recent orders only (last 7 days)
    print("\n" + "=" * 60)
    print("3. Fetching orders from last 7 days...")
    print("-" * 60)

    start_time = datetime.utcnow() - timedelta(days=7)
    end_time = datetime.utcnow()

    recent_count = 0
    try:
        for order in connector.extract(start_time=start_time, end_time=end_time):
            recent_count += 1
            print(f"  Order {recent_count}: {order['id']} - ₹{order['amount']}")

        print(f"\n✓ Found {recent_count} orders in last 7 days")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

    # Test 3: Validate schema
    print("\n" + "=" * 60)
    print("4. Testing schema...")
    print("-" * 60)

    schema = connector.get_schema()
    print(f"  Table name: {schema.table_name}")
    print(f"  Columns ({len(schema.columns)}):")
    for col in schema.columns:
        required = "REQUIRED" if col.required else "optional"
        print(f"    - {col.name:20s} {col.type:10s} {required}")

    print("\n✓ Schema looks good")

    # Test 4: Validate a record
    if order_count > 0:
        print("\n" + "=" * 60)
        print("5. Testing validation...")
        print("-" * 60)

        # Fetch one order
        test_order = next(connector.extract())

        # Validate it
        is_valid = connector.validate(test_order)

        if is_valid:
            print("  ✓ Record validation passed")
        else:
            print("  ✗ Record validation failed")
            return False

    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60 + "\n")

    return True


if __name__ == "__main__":
    # Uncomment this to create test orders first
    # create_test_order("rzp_test_xxx", "xxx")

    # Run tests
    success = test_fetch_orders()

    sys.exit(0 if success else 1)
