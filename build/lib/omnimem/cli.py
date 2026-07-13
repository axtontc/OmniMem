import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_compose():
    """Start the infrastructure via docker-compose."""
    compose_file = Path(__file__).parent.parent / "docker-compose.yml"
    print(f"Starting OmniMem infrastructure using {compose_file}...")
    subprocess.run(["docker-compose", "-f", str(compose_file), "up", "-d"], check=True)

def run_server():
    """Start the FastAPI backend."""
    print("Starting OmniMem REST API on port 8000...")
    subprocess.run([sys.executable, "-m", "uvicorn", "omnimem.api:app", "--host", "0.0.0.0", "--port", "8000"], check=True)

def run_worker():
    """Start the Celery worker."""
    print("Starting OmniMem Celery Worker...")
    subprocess.run([sys.executable, "-m", "celery", "-A", "omnimem.celery_app", "worker", "--loglevel=info"], check=True)

def main():
    parser = argparse.ArgumentParser(description="OmniMem System Orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("up", help="Spin up Redis, Neo4j, and PgVector in Docker")
    subparsers.add_parser("server", help="Start the FastAPI Memory Router")
    subparsers.add_parser("worker", help="Start the Celery worker node")
    
    args = parser.parse_args()
    
    if args.command == "up":
        run_compose()
    elif args.command == "server":
        run_server()
    elif args.command == "worker":
        run_worker()

if __name__ == "__main__":
    main()
