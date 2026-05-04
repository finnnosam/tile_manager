"""Board game / RP tile manager (extended)
Refactored: terrain, precipitation, temperature moved from Tile -> Region
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any

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
ADJ_FILE = Path("adjacency.json")

@dataclass
class Tile:
    id: str
    development: int = 0
    population: int = 0
    growth_progress: float = 0.0

    @classmethod
    def from_dict(cls, tid: str, data: Dict[str, Any]) -> "Tile":
        return cls(
            id=tid,
            development=int(data.get("development", 0)),
            population=int(data.get("population", 0)),
            growth_progress=float(data.get("growth_progress", 0.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("id", None)
        return d

@dataclass
class Region:
    name: str
    owner: str = "Unowned"
    notes: str = ""
    terrain: str = "blank"
    precipitation: str = "blank"
    temperature: str = "blank"
    tiles: Dict[str, Tile] = None

    def __post_init__(self):
        if self.tiles is None:
            self.tiles = {}

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "Region":
        tiles_raw = data.get("tiles", {})
        tiles = {tid: Tile.from_dict(tid, tdata) for tid, tdata in tiles_raw.items()}

        return cls(
            name=name,
            owner=str(data.get("owner", "Unowned")),
            notes=str(data.get("notes", "")),
            terrain=str(data.get("terrain", "blank")),
            precipitation=str(data.get("precipitation", "blank")),
            temperature=str(data.get("temperature", "blank")),
            tiles=tiles,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "owner": self.owner,
            "notes": self.notes,
            "terrain": self.terrain,
            "precipitation": self.precipitation,
            "temperature": self.temperature,
            "tiles": {tid: t.to_dict() for tid, t in self.tiles.items()},
        }

    def next_tile_id(self) -> str:
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if c not in self.tiles:
                return c
        raise ValueError("Max tiles reached (26)")

@dataclass
class Adjacency:
    regionA: str
    regionB: str
    distance: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Adjacency":
        return cls(
            regionA=data["regionA"],
            regionB=data["regionB"],
            distance=int(data["distance"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

DEFAULT_STATE = {
    "turn": 1,
    "population_growth_rate": 0.25,
}


class GameManager:
    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.state: Dict[str, Any] = {}
        self.adjacency: list[Adjacency] = []

    def load(self):
        self.state = self._load_json(STATE_FILE, DEFAULT_STATE)
        raw_regions = self._load_json(REGIONS_FILE, {})
        self.regions = {name: Region.from_dict(name, data) for name, data in raw_regions.items()}

        raw_adj = self._load_json(ADJ_FILE, [])
        self.adjacency = [Adjacency.from_dict(a) for a in raw_adj]

    def save(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=2) + "\n")

        raw = {n: t.to_dict() for n, t in self.regions.items()}
        REGIONS_FILE.write_text(json.dumps(raw, indent=2) + "\n")

        raw_adj = [a.to_dict() for a in self.adjacency]
        ADJ_FILE.write_text(json.dumps(raw_adj, indent=2) + "\n")

    def _load_json(self, path, default):
        if not path.exists():
            return default.copy()
        return json.loads(path.read_text())

    def require_region(self, name: str) -> Region:
        if name not in self.regions:
            raise KeyError(f"Region '{name}' not found")
        return self.regions[name]

    def add_region(self, **kwargs):
        name = kwargs["name"]
        if name in self.regions:
            raise ValueError("Region exists")
        self.regions[name] = Region(**kwargs)

    def add_tile(self, region_name: str, **kwargs):
        region = self.require_region(region_name)
        tid = region.next_tile_id()
        region.tiles[tid] = Tile(id=tid, **kwargs)

    def add_adjacency(self, regionA: str, regionB: str, distance: int):
        self.require_region(regionA)
        self.require_region(regionB)

        for a in self.adjacency:
            if {a.regionA, a.regionB} == {regionA, regionB}:
                raise ValueError("Adjacency already exists")

        self.adjacency.append(Adjacency(regionA, regionB, distance))

    def get_neighbors(self, region_name: str):
        result = []

        for a in self.adjacency:
            if a.regionA == region_name:
                result.append((a.regionB, a.distance))
            elif a.regionB == region_name:
                result.append((a.regionA, a.distance))

        return result

    def change_owner(self, region_name: str, new_owner: str):
        self.require_region(region_name).owner = new_owner

    def add_development(self, region_name: str, tile_id: str, amt: int):
        tile = self.require_region(region_name).tiles[tile_id]
        tile.development = max(0, tile.development + amt)

    def run_growth(self):
        rate = self.state.get("population_growth_rate", 0.25)

        for region in self.regions.values():
            for t in region.tiles.values():
                t.growth_progress += rate * (1 + t.development * 0.1)

                while t.growth_progress >= 1.0:
                    t.population += 1
                    t.growth_progress -= 1.0

    def advance_turn(self):
        self.state["turn"] += 1


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
                print("formatting usually looks like: add_, change = chg_")
                print("addreg, owner, addadj, adj, adddev, growth, turn, list, quit, saveas")

            elif cmd == "addreg":
                name = input("Name: ")
                terrain = input("Terrain: ") or "blank"

                if terrain.lower() == "ocean":
                    # Ocean regions keep defaults for other fields
                    g.add_region(
                        name=name,
                        terrain=terrain,
                    )
                else:
                    owner = input("Owner: ") or "Unowned"
                    precipitation = input("Precipitation: ") or "blank"
                    temperature = input("Temperature: ") or "blank"

                    g.add_region(
                        name=name,
                        owner=owner,
                        terrain=terrain,
                        precipitation=precipitation,
                        temperature=temperature,
                    )

                g.add_tile(name)
                g.save()

            elif cmd == "owner":
                g.change_owner(args[0], args[1])
                g.save()

            elif cmd == "addadj":
                regA = input("RegionA: ")
                regB = input("RegionB: ")
                dist = 1

                g.add_adjacency(regA, regB, int(dist))
                g.save()

            elif cmd == "adj":
                region_name = input("Region: ")

                for name, dist in g.get_neighbors(region_name):
                    region = g.require_region(name)

                    # --- Color region name based on terrain ---
                    if region.terrain.lower() == "ocean":
                        name_color = "\033[94m"  # blue
                    else:
                        name_color = "\033[92m"

                    # --- Color distance based on value ---
                    if dist == 1:
                        dist_color = "\033[97m"  # white
                    elif dist == 2:
                        dist_color = "\033[93m"  # yellow
                    else:
                        dist_color = "\033[91m"  # red

                    print(f"{name_color}{name}{RESET} (dist {dist_color}{dist}{RESET})")

            elif cmd == "adddev":
                g.add_development(args[0], args[1], int(args[2]))
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

                savename = input("Save name: ")

                base = "savegames"
                folder = os.path.join(base, savename)
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

                savename = input("Save name: ")
                
                base = "savegames"
                os.makedirs(base, exist_ok=True)
                folder = os.path.join(base, savename)
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
