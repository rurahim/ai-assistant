"""
Setup script for the external data database.
Creates the local database and runs the initial sync.
"""

import asyncio
import subprocess
import sys

from external_db.config import get_external_db_settings


def create_database():
    """Create the local database if it doesn't exist."""
    settings = get_external_db_settings()

    print("Creating local database...")
    print(f"  Host: {settings.local_db_host}")
    print(f"  Database: {settings.local_db_name}")

    # Create database using psql
    create_db_cmd = f"""
    psql -h {settings.local_db_host} -p {settings.local_db_port} -U {settings.local_db_user} -c "CREATE DATABASE {settings.local_db_name};" 2>/dev/null || echo "Database may already exist"
    """

    try:
        result = subprocess.run(
            create_db_cmd,
            shell=True,
            capture_output=True,
            text=True,
            env={**dict(__import__('os').environ), 'PGPASSWORD': settings.local_db_password}
        )
        if result.returncode == 0:
            print("  Database created or already exists.")
        else:
            print(f"  Note: {result.stderr.strip() or 'Database may already exist'}")
    except Exception as e:
        print(f"  Warning: Could not create database automatically: {e}")
        print(f"  Please create the database manually:")
        print(f"    CREATE DATABASE {settings.local_db_name};")


async def run_sync():
    """Run the database sync."""
    from external_db.sync import sync_all, close_all_connections

    try:
        await sync_all()
    finally:
        await close_all_connections()


def main():
    """Main entry point."""
    print("=" * 60)
    print("External Data Database Setup")
    print("=" * 60)
    print()

    # Step 1: Create the database
    create_database()
    print()

    # Step 2: Run the sync
    print("Running initial data sync...")
    asyncio.run(run_sync())

    print()
    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print()
    print("The external data has been synced to your local database.")
    print("You can run the sync again anytime with:")
    print("  python -m external_db.sync")
    print()


if __name__ == "__main__":
    main()
