#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="TDD pytest runner")
    parser.add_argument("--path", default="tests", help="Path to tests directory or file")
    parser.add_argument("-k", dest="keyword", default=None, help="Only run tests matching the expression")
    parser.add_argument("--cov", dest="cov", default=None, help="Measure coverage for the given package/module")
    parser.add_argument("--junit-xml", dest="junit_xml", default=None, help="Write JUnit XML report to file")
    parser.add_argument("--maxfail", dest="maxfail", default=None, help="Exit after first N failures")
    parser.add_argument("-q", dest="quiet", action="store_true", help="Quiet mode")
    args, unknown = parser.parse_known_args()

    cmd = [sys.executable, "-m", "pytest", args.path]
    if args.keyword:
        cmd += ["-k", args.keyword]
    if args.cov:
        cmd += ["--cov", args.cov]
    if args.junit_xml:
        Path(args.junit_xml).parent.mkdir(parents=True, exist_ok=True)
        cmd += ["--junit-xml", args.junit_xml]
    if args.maxfail:
        cmd += ["--maxfail", str(args.maxfail)]
    if args.quiet:
        cmd += ["-q"]
    # Allow passing through any additional pytest args
    cmd += unknown

    try:
        print("Running:", " ".join(cmd))
        completed = subprocess.run(cmd)
        sys.exit(completed.returncode)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
