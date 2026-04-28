"""
Script to convert individual JSON files into gzipped JSONL chunks.

Reads individual JSON files from data/dtic/ subdirectories (authors/, works/,
organizations/, topics/) and combines them into compressed JSONL files of
approximately 50MB compressed size per chunk.

Usage:
    # Convert all entity types
    python compress_to_jsonl.py

    # Convert specific entity types
    python compress_to_jsonl.py --entity-types authors works

    # Custom input/output directories
    python compress_to_jsonl.py --input-dir data/dtic --output-dir data/compressed

    # Different target size (in MB)
    python compress_to_jsonl.py --target-size 100

    # Dry run to preview
    python compress_to_jsonl.py --dry-run
"""

import json
import gzip
import argparse
import logging
from pathlib import Path
from typing import List
from datetime import datetime

try:
    import orjson

    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    logging.warning("orjson not available, falling back to standard json (slower)")

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
DEFAULT_INPUT_DIR = "data/dtic"
DEFAULT_OUTPUT_DIR = "data/dtic_compressed"
DEFAULT_TARGET_SIZE_MB = 50
ENTITY_TYPES = ["authors", "works", "orgs", "topics"]


class JSONLCompressor:
    """Handles compression of individual JSON files into JSONL chunks."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        target_size_mb: float = DEFAULT_TARGET_SIZE_MB,
    ):
        """
        Initialize the compressor.

        Args:
            input_dir: Directory containing entity subdirectories
            output_dir: Directory to write compressed JSONL files
            target_size_mb: Target compressed file size in MB
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.target_size_bytes = int(target_size_mb * 1024 * 1024)
        self.use_orjson = HAS_ORJSON

        if self.use_orjson:
            logger.info("Using orjson for fast JSON serialization")
        else:
            logger.info("Using standard json library")

    def _serialize_json(self, obj: dict) -> bytes:
        """
        Serialize a JSON object to bytes.

        Args:
            obj: Dictionary to serialize

        Returns:
            JSON bytes
        """
        if self.use_orjson:
            return orjson.dumps(obj)
        else:
            return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )

    def get_entity_files(self, entity_type: str) -> List[Path]:
        """
        Get all JSON files for a specific entity type.

        Args:
            entity_type: Entity type (authors, works, etc.)

        Returns:
            List of file paths
        """
        entity_dir = self.input_dir / entity_type

        if not entity_dir.exists():
            logger.warning(f"Directory not found: {entity_dir}")
            return []

        files = sorted(entity_dir.glob("*.json"))
        logger.info(f"Found {len(files)} files in {entity_type}/")
        return files

    def compress_entity_type(self, entity_type: str, dry_run: bool = False) -> dict:
        """
        Compress all files of a specific entity type into JSONL chunks.

        Args:
            entity_type: Entity type to process
            dry_run: If True, only simulate compression

        Returns:
            Dictionary with compression statistics
        """
        logger.info(f"Processing entity type: {entity_type}")

        # Get all files
        files = self.get_entity_files(entity_type)
        if not files:
            return {
                "entity_type": entity_type,
                "files_processed": 0,
                "chunks_created": 0,
                "total_size": 0,
            }

        # Create output directory
        if not dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # Process files into chunks
        chunk_num = 1
        current_chunk_path = None
        current_chunk_file = None
        current_chunk_size = 0
        files_in_chunk = 0
        total_chunks = 0
        total_size = 0
        files_processed = 0

        try:
            for i, file_path in enumerate(files):
                try:
                    # Read JSON file
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Serialize to JSONL format (one line)
                    json_line = self._serialize_json(data) + b"\n"

                    # Check if we need to start a new chunk
                    if (
                        current_chunk_file is None
                        or current_chunk_size >= self.target_size_bytes
                    ):
                        # Close previous chunk if exists
                        if current_chunk_file is not None:
                            current_chunk_file.close()
                            actual_size = current_chunk_path.stat().st_size
                            total_size += actual_size
                            logger.info(
                                f"  Completed chunk {chunk_num - 1}: {files_in_chunk} files, "
                                f"{actual_size / (1024 * 1024):.2f} MB compressed"
                            )

                        # Start new chunk
                        chunk_filename = f"dtic_{entity_type}_{chunk_num:03d}.jsonl.gz"
                        current_chunk_path = self.output_dir / chunk_filename

                        if dry_run:
                            logger.info(f"  [DRY RUN] Would create: {chunk_filename}")
                            current_chunk_file = None
                            current_chunk_size = 0
                        else:
                            current_chunk_file = gzip.open(
                                current_chunk_path, "wb", compresslevel=6
                            )
                            current_chunk_size = 0
                            files_in_chunk = 0

                        chunk_num += 1
                        total_chunks += 1

                    # Write to current chunk
                    if not dry_run and current_chunk_file is not None:
                        current_chunk_file.write(json_line)
                        # Update compressed size by checking actual file size
                        current_chunk_file.flush()
                        current_chunk_size = current_chunk_path.stat().st_size

                    files_in_chunk += 1
                    files_processed += 1

                    # Progress logging
                    if (i + 1) % 100 == 0 or (i + 1) == len(files):
                        logger.info(
                            f"  Progress: {i + 1}/{len(files)} files "
                            f"(chunk {chunk_num - 1}, ~{current_chunk_size / (1024 * 1024):.1f} MB)"
                        )

                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    continue

            # Close final chunk
            if current_chunk_file is not None:
                current_chunk_file.close()
                actual_size = current_chunk_path.stat().st_size
                total_size += actual_size
                logger.info(
                    f"  Completed chunk {chunk_num - 1}: {files_in_chunk} files, "
                    f"{actual_size / (1024 * 1024):.2f} MB compressed"
                )

        finally:
            if current_chunk_file is not None and not current_chunk_file.closed:
                current_chunk_file.close()

        logger.info(
            f"Completed {entity_type}: {files_processed} files -> "
            f"{total_chunks} chunks, {total_size / (1024 * 1024):.2f} MB total"
        )

        return {
            "entity_type": entity_type,
            "files_processed": files_processed,
            "chunks_created": total_chunks,
            "total_size": total_size,
            "avg_chunk_size": total_size / total_chunks if total_chunks > 0 else 0,
        }

    def compress_all(self, entity_types: List[str], dry_run: bool = False) -> dict:
        """
        Compress all specified entity types.

        Args:
            entity_types: List of entity types to process
            dry_run: If True, only simulate compression

        Returns:
            Dictionary with overall statistics
        """
        start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("JSONL COMPRESSION STARTED")
        logger.info("=" * 60)
        logger.info(f"Input directory: {self.input_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(
            f"Target chunk size: {self.target_size_bytes / (1024 * 1024):.1f} MB compressed"
        )
        logger.info(f"Entity types: {', '.join(entity_types)}")
        if dry_run:
            logger.info("[DRY RUN MODE]")
        logger.info("")

        results = []
        for entity_type in entity_types:
            result = self.compress_entity_type(entity_type, dry_run=dry_run)
            results.append(result)
            logger.info("")

        duration = (datetime.now() - start_time).total_seconds()

        # Print summary
        logger.info("=" * 60)
        logger.info("COMPRESSION SUMMARY")
        logger.info("=" * 60)

        total_files = sum(r["files_processed"] for r in results)
        total_chunks = sum(r["chunks_created"] for r in results)
        total_size = sum(r["total_size"] for r in results)

        for result in results:
            if result["chunks_created"] > 0:
                logger.info(
                    f"{result['entity_type']:15s}: {result['files_processed']:6d} files -> "
                    f"{result['chunks_created']:3d} chunks "
                    f"({result['total_size'] / (1024 * 1024):7.2f} MB, "
                    f"avg {result['avg_chunk_size'] / (1024 * 1024):.2f} MB/chunk)"
                )

        logger.info("-" * 60)
        logger.info(
            f"{'TOTAL':15s}: {total_files:6d} files -> "
            f"{total_chunks:3d} chunks ({total_size / (1024 * 1024):7.2f} MB)"
        )
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info("=" * 60)

        return {
            "results": results,
            "total_files": total_files,
            "total_chunks": total_chunks,
            "total_size": total_size,
            "duration": duration,
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert individual JSON files to gzipped JSONL chunks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--input-dir",
        type=str,
        default=DEFAULT_INPUT_DIR,
        help=f"Input directory containing entity subdirectories (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for compressed files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--entity-types",
        nargs="+",
        choices=ENTITY_TYPES,
        default=ENTITY_TYPES,
        help="Entity types to process (default: all)",
    )
    parser.add_argument(
        "--target-size",
        type=float,
        default=DEFAULT_TARGET_SIZE_MB,
        help=f"Target compressed chunk size in MB (default: {DEFAULT_TARGET_SIZE_MB})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be compressed without actually compressing",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check if orjson is available
    if not HAS_ORJSON:
        logger.warning("orjson library not found. Install with: pip install orjson")
        logger.warning("Continuing with standard json library (slower)")
        response = input("Continue? (y/n): ")
        if response.lower() != "y":
            return 1

    try:
        # Initialize compressor
        compressor = JSONLCompressor(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            target_size_mb=args.target_size,
        )

        # Compress all entity types
        results = compressor.compress_all(  # noqa: F841
            entity_types=args.entity_types, dry_run=args.dry_run
        )

        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
