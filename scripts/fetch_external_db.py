"""
Script to connect to external PostgreSQL database and fetch all data.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import text

# External database connection details
EXTERNAL_DB_CONFIG = {
    "host": "ai-employee-agent.ibhc.ai",
    "port": 5432,
    "database": "gmail_outlook_db",
    "username": "postgres",
    "password": "tiquaequoSie3Ied",
}

DATABASE_URL = (
    f"postgresql+asyncpg://{EXTERNAL_DB_CONFIG['username']}:{EXTERNAL_DB_CONFIG['password']}"
    f"@{EXTERNAL_DB_CONFIG['host']}:{EXTERNAL_DB_CONFIG['port']}/{EXTERNAL_DB_CONFIG['database']}"
)


async def get_all_tables(session: AsyncSession) -> list[str]:
    """Get all table names from the database."""
    query = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    result = await session.execute(query)
    return [row[0] for row in result.fetchall()]


async def get_table_columns(session: AsyncSession, table_name: str) -> list[str]:
    """Get column names for a table."""
    query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = :table_name
        ORDER BY ordinal_position
    """)
    result = await session.execute(query, {"table_name": table_name})
    return [row[0] for row in result.fetchall()]


async def fetch_table_data(session: AsyncSession, table_name: str, limit: int = 1000) -> list[dict]:
    """Fetch all data from a table."""
    # Use parameterized table name safely (table names from information_schema are safe)
    query = text(f'SELECT * FROM "{table_name}" LIMIT :limit')
    result = await session.execute(query, {"limit": limit})
    columns = result.keys()
    rows = result.fetchall()
    return [dict(zip(columns, row)) for row in rows]


async def get_table_count(session: AsyncSession, table_name: str) -> int:
    """Get total row count for a table."""
    query = text(f'SELECT COUNT(*) FROM "{table_name}"')
    result = await session.execute(query)
    return result.scalar()


async def main():
    """Main function to connect and fetch all data."""
    print("=" * 60)
    print("Connecting to External Database")
    print("=" * 60)
    print(f"Host: {EXTERNAL_DB_CONFIG['host']}")
    print(f"Database: {EXTERNAL_DB_CONFIG['database']}")
    print()

    # Create async engine
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # Create session factory
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with async_session_factory() as session:
            # Get all tables
            tables = await get_all_tables(session)
            print(f"Found {len(tables)} tables:")
            for table in tables:
                print(f"  - {table}")
            print()

            # Fetch data from each table
            all_data = {}
            for table_name in tables:
                print(f"\n{'=' * 60}")
                print(f"Table: {table_name}")
                print("=" * 60)

                # Get column info
                columns = await get_table_columns(session, table_name)
                print(f"Columns: {', '.join(columns)}")

                # Get row count
                count = await get_table_count(session, table_name)
                print(f"Total rows: {count}")

                # Fetch data
                data = await fetch_table_data(session, table_name)
                all_data[table_name] = data

                # Display sample data
                if data:
                    print(f"\nSample data (first {min(5, len(data))} rows):")
                    for i, row in enumerate(data[:5]):
                        print(f"\n  Row {i + 1}:")
                        for key, value in row.items():
                            # Truncate long values for display
                            str_value = str(value)
                            if len(str_value) > 100:
                                str_value = str_value[:100] + "..."
                            print(f"    {key}: {str_value}")
                else:
                    print("\n  (No data in table)")

            print("\n" + "=" * 60)
            print("Summary")
            print("=" * 60)
            for table_name, data in all_data.items():
                print(f"  {table_name}: {len(data)} rows fetched")

            return all_data

    except Exception as e:
        print(f"\nError connecting to database: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    data = asyncio.run(main())
