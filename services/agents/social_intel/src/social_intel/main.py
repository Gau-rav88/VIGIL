import asyncio
from vigil_common.logging import get_logger, setup_logging

logger = get_logger("social_intel")


async def run() -> None:
    setup_logging()
    logger.info("Starting social_intel agent...")
    while True:
        await asyncio.sleep(3600)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
