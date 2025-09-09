#!/usr/bin/env python
"""
Test script to verify atomic operations in organization_usage_client.py
This simulates concurrent access from multiple processes.
"""

import asyncio
import os
from concurrent.futures import ProcessPoolExecutor

# Set up environment
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.db.organization_usage_client import OrganizationUsageClient


async def reserve_quota_process(org_id: int, tokens: int, process_id: int):
    """Simulate a process trying to reserve quota."""
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    client = OrganizationUsageClient(async_session)

    results = []
    for i in range(5):
        result = await client.check_and_reserve_quota(org_id, tokens)
        results.append((process_id, i, result))
        await asyncio.sleep(0.01)  # Small delay to increase contention

    await engine.dispose()
    return results


async def update_usage_process(org_id: int, tokens: int, process_id: int):
    """Simulate a process updating usage after runs."""
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    client = OrganizationUsageClient(async_session)

    for i in range(5):
        await client.update_usage_after_run(org_id, tokens, duration_seconds=10)
        await asyncio.sleep(0.01)

    await engine.dispose()
    return f"Process {process_id} completed updates"


def run_reserve_quota(args):
    """Wrapper to run async function in process."""
    org_id, tokens, process_id = args
    return asyncio.run(reserve_quota_process(org_id, tokens, process_id))


def run_update_usage(args):
    """Wrapper to run async function in process."""
    org_id, tokens, process_id = args
    return asyncio.run(update_usage_process(org_id, tokens, process_id))


async def test_concurrent_quota_reservation():
    """Test that concurrent quota reservations are handled atomically."""
    print("Testing concurrent quota reservations...")

    # Assuming org_id 1 exists with quota enabled
    org_id = 1
    tokens_per_request = 100

    # Run multiple processes trying to reserve quota simultaneously
    with ProcessPoolExecutor(max_workers=3) as executor:
        futures = []
        for i in range(3):
            futures.append(
                executor.submit(run_reserve_quota, (org_id, tokens_per_request, i))
            )

        results = []
        for future in futures:
            results.extend(future.result())

    print(f"Reservation results: {results}")

    # Check that reservations were handled atomically
    successful_reservations = sum(1 for _, _, success in results if success)
    print(f"Successful reservations: {successful_reservations}")


async def test_concurrent_usage_updates():
    """Test that concurrent usage updates are handled atomically."""
    print("\nTesting concurrent usage updates...")

    org_id = 1
    tokens_per_update = 50

    # Get initial usage
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = OrganizationUsageClient(async_session)

    initial_usage = await client.get_current_usage(org_id)
    initial_tokens = initial_usage["used_dograh_tokens"]
    print(f"Initial tokens: {initial_tokens}")

    # Run multiple processes updating usage simultaneously
    with ProcessPoolExecutor(max_workers=3) as executor:
        futures = []
        for i in range(3):
            futures.append(
                executor.submit(run_update_usage, (org_id, tokens_per_update, i))
            )

        for future in futures:
            print(future.result())

    # Check final usage
    final_usage = await client.get_current_usage(org_id)
    final_tokens = final_usage["used_dograh_tokens"]
    expected_tokens = initial_tokens + (
        3 * 5 * tokens_per_update
    )  # 3 processes * 5 updates * 50 tokens

    print(f"Final tokens: {final_tokens}")
    print(f"Expected tokens: {expected_tokens}")
    print(f"Difference: {final_tokens - expected_tokens}")

    await engine.dispose()

    if final_tokens == expected_tokens:
        print("✅ All updates were applied atomically!")
    else:
        print("❌ Some updates were lost due to race conditions!")


async def main():
    """Run all concurrency tests."""
    try:
        await test_concurrent_quota_reservation()
        await test_concurrent_usage_updates()
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("Starting organization usage concurrency tests...")
    print(f"Using DATABASE_URL: {os.environ.get('DATABASE_URL', 'NOT SET')}")
    asyncio.run(main())
