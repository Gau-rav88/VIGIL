import asyncio
from pathlib import Path

from neo4j import AsyncGraphDatabase

from vigil_common.config import get_settings
from vigil_common.logging import get_logger, setup_logging

logger = get_logger("neo4j_migrate")


async def run_migrations() -> None:
    setup_logging()
    settings = get_settings()
    logger.info("Connecting to Neo4j for schema migration", uri=settings.NEO4J_URI)

    async with AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    ) as driver:
        # Check connection
        await driver.verify_connectivity()

        migrations_dir = Path("migrations/neo4j")
        cypher_files = sorted(migrations_dir.glob("*.cypher"))

        async with driver.session() as session:
            for c_file in cypher_files:
                logger.info("Applying Cypher migration", file=c_file.name)
                content = c_file.read_text(encoding="utf-8")
                statements = [stmt.strip() for stmt in content.split(";") if stmt.strip()]
                for stmt in statements:
                    try:
                        await session.run(stmt)
                    except Exception as e:
                        logger.warning("Statement warning/error (may already exist)", error=str(e), stmt=stmt[:50])

    logger.info("Neo4j migrations completed successfully")


if __name__ == "__main__":
    asyncio.run(run_migrations())
