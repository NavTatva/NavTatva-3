#!/usr/bin/env python3
"""Minimal bootstrap for Render deployment.

For full demo setup, use the original bootstrap script.
This version only sets up essential files for the API to start.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Minimal bootstrap for deployment")
    parser.add_argument("--minimal", action="store_true", help="Minimal setup for cloud deployment")
    args = parser.parse_args()
    
    root = Path(__file__).parent.parent
    data_dir = root / "data"
    
    # Create essential directories
    (data_dir / "sar").mkdir(parents=True, exist_ok=True)
    (data_dir / "ais").mkdir(parents=True, exist_ok=True)
    (data_dir / "jobs").mkdir(parents=True, exist_ok=True)
    (data_dir / "metocean").mkdir(parents=True, exist_ok=True)
    (data_dir / "optical").mkdir(parents=True, exist_ok=True)
    (data_dir / "land").mkdir(parents=True, exist_ok=True)
    
    # Create minimal scenes.json
    scenes_file = data_dir / "sar" / "scenes.json"
    if not scenes_file.exists():
        scenes_file.write_text(json.dumps({"scenes": []}, indent=2))
        print(f"✓ Created {scenes_file}")
    
    # Create empty AIS database placeholder
    ais_db = data_dir / "ais" / "store.db"
    if not ais_db.exists():
        ais_db.touch()
        print(f"✓ Created {ais_db}")
    
    print("✓ Minimal bootstrap complete")
    print("Note: This is a minimal setup for cloud deployment.")
    print("For full demo with scenes and data, run without --minimal flag locally.")


if __name__ == "__main__":
    main()
