"""
Unit / manual test script for the Razorpay Customers connector.

Credentials are loaded exclusively from environment variables — never hardcoded.

Required env vars (set in .env or export in your shell):
    RAZORPAY_API_KEY
    RAZORPAY_API_SECRET

Optional:
    RAZORPAY_BASE_URL   (defaults to https://api.razorpay.com/v1)

Usage:
    RAZORPAY_API_KEY=rzp_test_xxx RAZORPAY_API_SECRET=yyy python -m pytest tests/unit/test_razorpay_customers.py -s
"""

import logging
import sys
from datetime import datetime, timedelta

from data_connectors.sources.razorpay.config import RazorpaySourceConfig
from data_connectors.sources.razorpay.customers_connector import RazorpayCustomersConnector

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def test_fetch_customers() -> bool:
    """Test fetching orders from Razorpay."""

    print("\n" + "=" * 60)
    print("Testing Razorpay Customers Connector")
    print("=" * 60 + "\n")

    # Config is loaded from RAZORPAY_* environment variables.
    # Raises ValidationError immediately if required vars are missing.
    config = RazorpaySourceConfig()
    print(f"   api_key  : {config.api_key}")
    print(f"   api_secret: {config.api_secret}")  # prints SecretStr('**********')
    print(f"   base_url : {config.base_url}\n")

    print("1. Initializing connector...")
    connector = RazorpayCustomersConnector(config)
    print("   ✓ Connector initialized\n")

    print("2. Fetching ALL ...")
    print("-" * 60)

    customer_count = 0
    try:
        for customer in connector.extract():
            customer_count += 1
            print(f"\nCustomer {customer_count}:")
            print(f"  ID:          {customer['id']}")
            print(f"  Name:        {customer['name']}")
            print(f"  Email:       {customer['email']}")
            print(f"  Contact:     {customer['contact']}")
            print(f"  Created:     {customer['created_at']}")
            print(f"  Extracted:   {customer['_extracted_at']}")

            if customer_count >= 5:
                print("\n  ... (showing only first 5)")
                break

        print(f"\n✓ Successfully fetched {customer_count} customers")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 2: Fetch recent orders (last 7 days)
    print("\n" + "=" * 60)
    print("3. Fetching customers from last 7 days...")
    print("-" * 60)

    start_time = datetime.utcnow() - timedelta(days=7)
    end_time = datetime.utcnow()

    recent_count = 0
    try:
        for customer in connector.extract(start_time=start_time, end_time=end_time):
            recent_count += 1
            print(f"  Customer {recent_count}: {customer['id']} - {customer['_extracted_at']}")

        print(f"\n✓ Found {recent_count} customers in last 7 days")

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
    if customer_count > 0:
        print("\n" + "=" * 60)
        print("5. Testing validation...")
        print("-" * 60)

        test_customer = next(connector.extract())
        is_valid = connector.validate(test_customer)

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
    success = test_fetch_customers()
    sys.exit(0 if success else 1)
