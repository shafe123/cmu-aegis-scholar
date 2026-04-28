"""
Check Data Loader Status

Simple script to check the status of the vector database.
"""

import sys

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    print("Warning: httpx not installed. Install with: pip install httpx")


def check_vector_db(
    base_url: str = "http://localhost:8002", collection: str = "aegis_vectors"
):
    """Check the vector database status."""
    if not HAS_HTTPX:
        print("\nCannot check vector DB (httpx not installed)")
        print("Install with: pip install httpx")
        return False

    print("=" * 70)
    print("VECTOR DATABASE STATUS")
    print("=" * 70)

    try:
        client = httpx.Client(timeout=10)

        # Check health
        health_response = client.get(f"{base_url}/health")
        health_response.raise_for_status()
        health = health_response.json()

        print(f"Service: {health.get('status', 'unknown')}")
        print(f"Milvus Connected: {health.get('milvus_connected', False)}")

        # Check collection
        try:
            coll_response = client.get(f"{base_url}/collections/{collection}")
            if coll_response.status_code == 200:
                coll_info = coll_response.json()
                print(f"\nCollection: {coll_info.get('name', 'unknown')}")
                print(f"Entities: {coll_info.get('num_entities', 0):,}")
                print(f"Indexed: {coll_info.get('is_indexed', False)}")

                if coll_info.get("num_entities", 0) > 0:
                    print("\n✓ Vector database has data!")
                    return True
                else:
                    print("\n⚠ Collection exists but is empty")
                    return False
            else:
                print(f"\n⚠ Collection '{collection}' not found")
                return False
        except Exception as e:
            print(f"\n⚠ Could not get collection info: {e}")
            return False

    except httpx.ConnectError:
        print("⚠ Cannot connect to vector database")
        print("  Make sure services are running: docker compose up -d")
        return False
    except Exception as e:
        print(f"⚠ Error checking vector DB: {e}")
        return False
    finally:
        if "client" in locals():
            client.close()


def main():
    """Main entry point."""
    print("\nDTIC Data Pipeline Status Check\n")

    # Check vector DB
    db_ok = check_vector_db()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if db_ok:
        print("✓ Vector database has data and is healthy")
        return 0
    else:
        print("✗ Vector database is empty or has issues")
        print("\nNext steps:")
        print("  1. Start services: docker compose -f dev/docker-compose.yml up -d")
        print(
            "  2. Check logs: docker compose -f dev/docker-compose.yml logs vector-loader"
        )
        print("  3. Check docs: docs/QUICKSTART_DATA_PIPELINE.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
