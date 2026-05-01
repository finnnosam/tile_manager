"""Board game / RP tile manager (extended)
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional

COLORS = [
    "\033[91m",  # red
    "\033[92m",  # green
    "\033[93m",  # yellow
    "\033[94m",  # blue
    "\033[95m",  # magenta
    "\033[96m",  # cyan
]
RESET = "\033[0m"

REGIONS_FILE = Path("regions.json")
STATE_FILE = Path("game_state.json")

"""
To add new types of info to a region:
add under 'class Region:'
add under 'from_dict'
add under 'elif cmd == "addregion":'
"""

@dataclass
class Region:
    name: str
    owner: str = "Unowned"
    development: int = 0
    population: int = 0
    growth_progress: float = 0.0
    terrain: str = "plain"
    precipitation: str = "base"
    temperature: str = "moderate"
    notes: str = ""

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "Region":
        return cls(
            name=name,
            owner=str(data.get("owner", "Unowned")),
            development=int(data.get("development", 0)),
            population=int(data.get("population", 0)),
            growth_progress=float(data.get("growth_progress", 0.0)),
            terrain=str(data.get("terrain", "plain")),
            precipitation=str(data.get("precipitation", "base")),
            temperature=str(data.get("temperature", "moderate")),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("name", None)
        return d


DEFAULT_STATE = {
    "turn": 1,
    "population_growth_rate": 0.25,
}


class GameManager:
    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.state: Dict[str, Any] = {}

    def load(self):
        self.state = self._load_json(STATE_FILE, DEFAULT_STATE)
        raw_regions = self._load_json(REGIONS_FILE, {})
        self.regions = {name: Region.from_dict(name, data) for name, data in raw_regions.items()}

    def save(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=2) + "\n")
        raw = {n: t.to_dict() for n, t in self.regions.items()}
        REGIONS_FILE.write_text(json.dumps(raw, indent=2) + "\n")

    def _load_json(self, path, default):
        if not path.exists():
            return default.copy()
        return json.loads(path.read_text())

    def require_region(self, name: str) -> Region:
        if name not in self.regions:
            raise KeyError(f"Region '{name}' not found")
        return self.regions[name]

    # --- Regions actions ---

    def add_region(self, **kwargs):
        name = kwargs["name"]
        if name in self.regions:
            raise ValueError("Region exists")
        self.regions[name] = Region(**kwargs)

    def change_owner(self, region_name: str, new_owner: str):
        self.require_region(region_name).owner = new_owner

    def add_development(self, region_name: str, amt: int):
        t = self.require_region(region_name)
        t.development = max(0, t.development + amt)

    def run_growth(self):
        rate = self.state.get("population_growth_rate", 0.25)
        for t in self.regions.values():
            # growth accumulates into progress
            t.growth_progress += rate * (1 + t.development * 0.1)

            # convert progress into population
            while t.growth_progress >= 1.0:
                t.population += 1
                t.growth_progress -= 1.0

    def advance_turn(self):
        self.state["turn"] += 1


# --- CLI ---

def parse(raw):
    try:
        parts = shlex.split(raw)
    except Exception:
        return "", []
    return (parts[0], parts[1:]) if parts else ("", [])


def repl():
    g = GameManager()
    g.load()

    print("Loaded. Type help.")

    while True:
        cmd, args = parse(input("> "))

        try:
            if cmd == "help":
                print("addregion, owner, devadd, growth, turn, list, quit, saveas")

            elif cmd == "addregion":
                name = input("Name: ")
                owner = input("Owner: ") or "Unowned"
                dev = int(input("Development: ") or 0)
                pop = int(input("Population: ") or 0)
                terrain = input("Terrain: ") or "plain"
                precipitation = input("precipitation: ") or "base"
                temperature = input("temperature: ") or "moderate"

                g.add_region(name=name, owner=owner, development=dev,
                           population=pop, terrain=terrain, precipitation=precipitation, temperature=temperature)
                g.save()

            elif cmd == "owner":
                g.change_owner(args[0], args[1])
                g.save()

            elif cmd == "devadd":
                g.add_development(args[0], int(args[1]))
                g.save()

            elif cmd == "growth":
                g.run_growth()
                g.save()

            elif cmd == "turn":
                g.advance_turn()
                g.save()

            elif cmd == "list":
                owners = {}

                for t in g.regions.values():
                    owners.setdefault(t.owner, []).append(t.name)

                owner_colors = {}
                for i, owner in enumerate(owners):
                    owner_colors[owner] = COLORS[i % len(COLORS)]

                for owner, regions in owners.items():
                    print(f"{owner_colors[owner]}{owner}{RESET}")
                    for name in regions:
                        print(f"  {name}")
                    print()

            elif cmd == "loadfrom":
                import shutil, os
                if len(args) < 1:
                    print("Usage: loadfrom <folder_name>")
                else:
                    base = "savegames"
                    folder = os.path.join(base, args[0])
                    regions_path = os.path.join(folder, "regions.json")
                    state_path = os.path.join(folder, "game_state.json")

                    if not os.path.exists(regions_path) or not os.path.exists(state_path):
                        print("Error: folder does not contain required save files.")
                    else:
                        shutil.copy(regions_path, REGIONS_FILE)
                        shutil.copy(state_path, STATE_FILE)
                        g.load()
                        print(f"Loaded save from '{folder}'")

            elif cmd == "saveas":
                import shutil, os
                if len(args) < 1:
                    print("Usage: saveas <folder_name>")
                else:
                    base = "savegames"
                    os.makedirs(base, exist_ok=True)
                    folder = os.path.join(base, args[0])
                    os.makedirs(folder, exist_ok=True)
                    g.save()
                    shutil.copy(REGIONS_FILE, os.path.join(folder, "regions.json"))
                    shutil.copy(STATE_FILE, os.path.join(folder, "game_state.json"))
                    print(f"Backup saved to '{folder}'")

            elif cmd == "quit":
                g.save()
                break

        except Exception as e:
            print("Error:", e)


if __name__ == "__main__":
    repl()
