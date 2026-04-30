"""Board game / RP tile manager (extended)
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional

TILES_FILE = Path("tiles.json")
STATE_FILE = Path("game_state.json")

"""
To add new types of info to a tile:
add under 'class Tile:'
add under 'from_dict'
add under 'elif cmd == "addtile":'
"""

@dataclass
class Tile:
    name: str
    owner: str = "Unowned"
    development: int = 0
    population: int = 0
    growth_progress: float = 0.0
    terrain: str = "plain"
    precipitation: str = "base"
    region: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "Tile":
        return cls(
            name=name,
            owner=str(data.get("owner", "Unowned")),
            development=int(data.get("development", 0)),
            population=int(data.get("population", 0)),
            growth_progress=float(data.get("growth_progress", 0.0)),
            terrain=str(data.get("terrain", "plain")),
            precipitation=str(data.get("precipitation", "base")),
            region=str(data.get("region", "")),
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
        self.tiles: Dict[str, Tile] = {}
        self.state: Dict[str, Any] = {}

    def load(self):
        self.state = self._load_json(STATE_FILE, DEFAULT_STATE)
        raw_tiles = self._load_json(TILES_FILE, {})
        self.tiles = {name: Tile.from_dict(name, data) for name, data in raw_tiles.items()}

    def save(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=2) + "\n")
        raw = {n: t.to_dict() for n, t in self.tiles.items()}
        TILES_FILE.write_text(json.dumps(raw, indent=2) + "\n")

    def _load_json(self, path, default):
        if not path.exists():
            return default.copy()
        return json.loads(path.read_text())

    def require_tile(self, name: str) -> Tile:
        if name not in self.tiles:
            raise KeyError(f"Tile '{name}' not found")
        return self.tiles[name]

    # --- Tile actions ---

    def add_tile(self, **kwargs):
        name = kwargs["name"]
        if name in self.tiles:
            raise ValueError("Tile exists")
        self.tiles[name] = Tile(**kwargs)

    def change_owner(self, tile_name: str, new_owner: str):
        self.require_tile(tile_name).owner = new_owner

    def change_owner_region(self, region: str, new_owner: str):
        for t in self.tiles.values():
            if t.region == region:
                t.owner = new_owner

    def add_development(self, tile_name: str, amt: int):
        t = self.require_tile(tile_name)
        t.development = max(0, t.development + amt)

    def run_growth(self):
        rate = self.state.get("population_growth_rate", 0.25)
        for t in self.tiles.values():
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
                print("addtile, owner, owner_region, devadd, growth, turn, list, quit, saveas")

            elif cmd == "addtile":
                name = input("Name: ")
                owner = input("Owner: ") or "Unowned"
                dev = int(input("Development: ") or 0)
                pop = int(input("Population: ") or 0)
                region = input("Region: ")
                terrain = input("Terrain: ") or "plain"
                precipitation = input("precipitation: ") or "base"

                g.add_tile(name=name, owner=owner, development=dev,
                           population=pop, region=region, terrain=terrain, precipitation=precipitation)
                g.save()

            elif cmd == "owner":
                g.change_owner(args[0], args[1])
                g.save()

            elif cmd == "owner_region":
                g.change_owner_region(args[0], args[1])
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
                for t in g.tiles.values():
                    print(t)

            elif cmd == "loadfrom":
                import shutil, os
                if len(args) < 1:
                    print("Usage: loadfrom <folder_name>")
                else:
                    base = "savegames"
                    folder = os.path.join(base, args[0])
                    tiles_path = os.path.join(folder, "tiles.json")
                    state_path = os.path.join(folder, "game_state.json")

                    if not os.path.exists(tiles_path) or not os.path.exists(state_path):
                        print("Error: folder does not contain required save files.")
                    else:
                        shutil.copy(tiles_path, TILES_FILE)
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
                    shutil.copy(TILES_FILE, os.path.join(folder, "tiles.json"))
                    shutil.copy(STATE_FILE, os.path.join(folder, "game_state.json"))
                    print(f"Backup saved to '{folder}'")

            elif cmd == "quit":
                g.save()
                break

        except Exception as e:
            print("Error:", e)


if __name__ == "__main__":
    repl()
