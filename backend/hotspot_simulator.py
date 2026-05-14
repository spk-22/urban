"""
hotspot_simulator.py
=========================================
BENGALURU TOP 5 TRAFFIC HOTSPOT SIMULATOR
=========================================
"""

import os
import json
import networkx as nx
from pathlib import Path
from graph.osm_fetcher import fetch_road_geojson
from graph.road import RoadGraphBuilder
from graph.cascade import RoadCascadeSimulator
from graph.cascade_visualizer import CascadeVisualizer

HOTSPOTS = {
    "silk_board": {
        "name": "Silk Board Junction",
        "bbox": (12.910, 77.615, 12.925, 77.635),
        "target_keywords": ["silk board", "hosur road"],
        "description": "Massive merging of Electronic City IT traffic and ORR freight."
    },
    "orr_it_corridor": {
        "name": "ORR - Marathahalli/Bellandur",
        "bbox": (12.920, 77.670, 12.955, 77.705),
        "target_keywords": ["outer ring road", "marathahalli"],
        "description": "The stop-go IT corridor serving hundreds of tech parks."
    },
    "kr_puram": {
        "name": "KR Puram - Tin Factory",
        "bbox": (12.985, 77.665, 13.005, 77.685),
        "target_keywords": ["old madras road", "tin factory", "kr puram"],
        "description": "Metro construction meets heavy freight and Whitefield commuters."
    },
    "hebbal": {
        "name": "Hebbal Junction",
        "bbox": (13.030, 77.585, 13.045, 77.605),
        "target_keywords": ["hebbal", "bellary road", "airport road"],
        "description": "Major multi-layer interchange for Airport and North Bengaluru."
    },
    "whitefield_crawl": {
        "name": "Marathahalli - Whitefield Road",
        "bbox": (12.950, 77.700, 12.965, 77.715),
        "target_keywords": ["whitefield road", "varthur"],
        "description": "High office-hour dependency with signal clustering and metro work."
    }
}

class HotspotSimulator:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parents[1]
        self.data_dir = self.base_dir / "data" / "processed"
        self.graph_dir = self.base_dir / "data" / "graphs"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.graph_dir.mkdir(parents=True, exist_ok=True)

    def run_hotspot(self, hotspot_id):
        if hotspot_id not in HOTSPOTS:
            return {"error": f"Unknown hotspot: {hotspot_id}"}

        config = HOTSPOTS[hotspot_id]
        print(f"\n>>> SIMULATING HOTSPOT: {config['name']}")

        # 1. Fetch / Load Data
        geojson_path = self.data_dir / f"{hotspot_id}.geojson"
        if not geojson_path.exists():
            print(f"Fetching data for {hotspot_id}...")
            fetch_road_geojson(config["bbox"], geojson_path)

        # 2. Build Graph
        builder = RoadGraphBuilder()
        import pandas as pd
        dummy_xlsx = self.data_dir / "dummy_hotspot.xlsx"
        pd.DataFrame(columns=["latitude", "longitude", "road_node_type"]).to_excel(dummy_xlsx, index=False)
        
        G = builder.build_graph(str(dummy_xlsx), str(geojson_path))
        
        if G is None or G.number_of_nodes() == 0:
            return {"error": "Failed to fetch or build road data for this area. Overpass API might be rate-limiting."}
            
        G = builder.assign_capacities(G)

        # 3. Setup PEAK HOUR Simulator (85% baseline)
        simulator = RoadCascadeSimulator(G)
        simulator.prepare_graph(baseline_load_range=(0.80, 0.90))

        # 4. Inject Failure at Hotspot Center
        major_edge = None
        for u, v, data in simulator.G.edges(data=True):
            name = str(data.get("road_name", "")).lower()
            if any(kw in name for kw in config["target_keywords"]):
                major_edge = (u, v)
                break
        
        if not major_edge:
            # Fallback to high degree node near center
            nodes_by_degree = sorted(simulator.G.degree(), key=lambda x: x[1], reverse=True)
            major_edge = list(simulator.G.edges(nodes_by_degree[0][0]))[0]

        print(f"Injecting failure at: {major_edge}")
        failure_res = simulator.inject_road_blockage(major_edge, f"peak_hour_{hotspot_id}_fail")
        failure_res["target_id"] = major_edge
        failure_res["displaced_traffic"] = 12000 # Heavy displacement

        # 5. Propagate
        cascade_res = simulator.propagate_cascade(failure_res, max_iterations=15)
        
        # 6. Find Alternate Routes for a representative pair
        # Just pick two distant nodes for demo
        nodes = list(simulator.G.nodes())
        if len(nodes) > 10:
            src, dst = nodes[0], nodes[-1]
            alternates = simulator.find_alternate_routes(src, dst, k=3)
            simulator.G.graph["alternate_routes"] = alternates["routes"]

        # 7. Visualize
        visualizer = CascadeVisualizer(output_dir=self.graph_dir)
        map_filename = f"map_{hotspot_id}.html"
        map_path = visualizer.create_cascade_map(
            simulator.G, 
            f"CRITICAL FAILURE: {config['name']}", 
            map_filename
        )

        return {
            "hotspot": config["name"],
            "description": config["description"],
            "failure_point": major_edge,
            "iterations": cascade_res["iterations"],
            "total_overloaded": cascade_res["total_overloaded"],
            "map_url": f"/maps/{map_filename}",
            "stats": cascade_res
        }

if __name__ == "__main__":
    sim = HotspotSimulator()
    res = sim.run_hotspot("silk_board")
    print(json.dumps(res, indent=2))
