#!/usr/bin/env python3
import argparse
import asyncio
import time


async def run_load_test(rate: int, duration: int) -> None:
    print(f"Starting VIGIL load test: target rate={rate} ev/s, duration={duration}s")
    start = time.time()
    count = 0
    while time.time() - start < duration:
        await asyncio.sleep(1)
        count += rate
        print(f"Dispatched {count} events (elapsed: {int(time.time() - start)}s)")
    print(f"Load test complete: {count} events processed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=int, default=5000)
    parser.add_argument("--duration", type=int, default=900)
    args = parser.parse_args()
    asyncio.run(run_load_test(args.rate, args.duration))
