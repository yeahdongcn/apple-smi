"""CLI entry point for apple-smi."""

import argparse
import os
import sys


def _is_root() -> bool:
    return os.geteuid() == 0


def _get_backend():
    """Select the appropriate backend based on env var and privileges."""
    env_backend = os.environ.get("APPLE_SMI_BACKEND", "").lower()

    if env_backend == "powermetrics":
        from .powermetrics import PowermetricsSampler
        return PowermetricsSampler()
    elif env_backend == "iokit":
        from .sampler import Sampler
        return Sampler()
    else:
        # Auto-detect: try IOKit first (sudoless), fall back to powermetrics
        try:
            from .sampler import Sampler
            return Sampler()
        except Exception:
            if _is_root():
                from .powermetrics import PowermetricsSampler
                return PowermetricsSampler()
            raise


def main():
    """Main entry point for apple-smi CLI."""
    parser = argparse.ArgumentParser(
        prog="apple-smi",
        description="nvidia-smi equivalent for macOS Apple Silicon – Monitor Metal GPU usage",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output metrics in JSON format",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=100,
        metavar="MS",
        help="Sampling interval in milliseconds (default: 100)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__import__('apple_smi').__version__}",
    )

    args = parser.parse_args()

    # Check platform
    if sys.platform != "darwin":
        print("Error: apple-smi only works on macOS.", file=sys.stderr)
        sys.exit(1)

    try:
        sampler = _get_backend()
    except Exception as e:
        print(f"Error initializing metrics backend: {e}", file=sys.stderr)
        print(
            "Tip: Try running with sudo or set APPLE_SMI_BACKEND=powermetrics",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        metrics = sampler.get_metrics(duration_ms=args.interval)
    except Exception as e:
        print(f"Error collecting metrics: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        from .formatter import format_json
        print(format_json(metrics, sampler.soc))
    else:
        from .formatter import format_table
        print(format_table(metrics, sampler.soc))


if __name__ == "__main__":
    main()
