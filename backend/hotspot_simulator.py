"""
hotspot_simulator.py
=========================================================
ADVANCED BENGALURU TRAFFIC HOTSPOT CASCADE SIMULATOR
Compatible with:
- Updated cascade.py
- Updated cascade_visualizer.py
- Updated app.py
=========================================================
"""

import json
import random
import traceback
from pathlib import Path

import pandas as pd

from graph.osm_fetcher import fetch_road_geojson
from graph.road import RoadGraphBuilder
from graph.cascade import RoadCascadeSimulator
from graph.cascade_visualizer import CascadeVisualizer


# =========================================================
# HOTSPOT DEFINITIONS
# =========================================================

HOTSPOTS = {

    "silk_board": {

        "name": "Silk Board Junction",

        "bbox": (
            12.910,
            77.615,
            12.925,
            77.635
        ),

        "target_keywords": [
            "silk board",
            "hosur road",
            "electronic city"
        ],

        "description": (
            "Massive merging of Electronic City IT traffic "
            "with ORR freight movement causing cascading "
            "shockwave congestion."
        ),

        "severity": "EXTREME",

        "baseline_load": (
            0.88,
            0.97
        ),

        "failure_type": "road_blockage",

        "reroute_pressure": 15000,

        "max_iterations": 8
    },

    "orr_it_corridor": {

        "name": "ORR IT Corridor",

        "bbox": (
            12.920,
            77.670,
            12.955,
            77.705
        ),

        "target_keywords": [
            "outer ring road",
            "marathahalli",
            "bellandur"
        ],

        "description": (
            "High-density IT corridor with recurring stop-go "
            "traffic waves and severe office-hour congestion."
        ),

        "severity": "CRITICAL",

        "baseline_load": (
            0.84,
            0.94
        ),

        "failure_type": "flyover_closure",

        "reroute_pressure": 12000,

        "max_iterations": 8
    },

    "kr_puram": {

        "name": "KR Puram - Tin Factory",

        "bbox": (
            12.985,
            77.665,
            13.005,
            77.685
        ),

        "target_keywords": [
            "old madras road",
            "tin factory",
            "kr puram"
        ],

        "description": (
            "Metro construction mixed with freight and "
            "Whitefield commuter congestion."
        ),

        "severity": "HIGH",

        "baseline_load": (
            0.82,
            0.92
        ),

        "failure_type": "signal_failure",

        "reroute_pressure": 10000,

        "max_iterations": 7
    },

    "hebbal": {

        "name": "Hebbal Junction",

        "bbox": (
            13.030,
            77.585,
            13.045,
            77.605
        ),

        "target_keywords": [
            "hebbal",
            "airport road",
            "bellary road"
        ],

        "description": (
            "Critical airport interchange with layered flyover "
            "merges and intense directional traffic conflicts."
        ),

        "severity": "CRITICAL",

        "baseline_load": (
            0.83,
            0.95
        ),

        "failure_type": "flyover_closure",

        "reroute_pressure": 13000,

        "max_iterations": 8
    },

    "whitefield_crawl": {

        "name": "Whitefield Road Stretch",

        "bbox": (
            12.950,
            77.700,
            12.965,
            77.715
        ),

        "target_keywords": [
            "whitefield",
            "varthur",
            "marathahalli"
        ],

        "description": (
            "Office-hour dependency combined with signal "
            "clustering and metro work creates severe crawling."
        ),

        "severity": "HIGH",

        "baseline_load": (
            0.80,
            0.90
        ),

        "failure_type": "road_blockage",

        "reroute_pressure": 9000,

        "max_iterations": 6
    }
}


# =========================================================
# HOTSPOT SIMULATOR
# =========================================================

class HotspotSimulator:

    def __init__(self):

        self.base_dir = Path(__file__).resolve().parents[1]

        self.data_dir = (
            self.base_dir / "data" / "processed"
        )

        self.graph_dir = (
            self.base_dir / "data" / "graphs"
        )

        self.raw_dir = (
            self.base_dir / "data" / "raw"
        )

        self.data_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.graph_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.raw_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    # =====================================================
    # FETCH GEOJSON
    # =====================================================

    def fetch_hotspot_geojson(
        self,
        hotspot_id,
        config
    ):

        geojson_path = (
            self.data_dir / f"{hotspot_id}.geojson"
        )

        if geojson_path.exists():

            print(
                f"[INFO] Using cached GeoJSON: "
                f"{geojson_path}"
            )

            return geojson_path

        print(
            f"[INFO] Fetching OSM data for "
            f"{config['name']}"
        )

        fetch_road_geojson(
            config["bbox"],
            geojson_path
        )

        return geojson_path

    # =====================================================
    # BUILD GRAPH
    # =====================================================

    def build_graph(
        self,
        hotspot_id,
        geojson_path
    ):

        builder = RoadGraphBuilder()

        dummy_xlsx = (
            self.data_dir /
            f"dummy_{hotspot_id}.xlsx"
        )

        pd.DataFrame(
            columns=[
                "latitude",
                "longitude",
                "road_node_type"
            ]
        ).to_excel(
            dummy_xlsx,
            index=False
        )

        G = builder.build_graph(
            str(dummy_xlsx),
            str(geojson_path)
        )

        if G is None:
            raise Exception(
                "Road graph builder returned None"
            )

        if G.number_of_nodes() == 0:
            raise Exception(
                "Generated graph contains zero nodes"
            )

        print(
            f"[INFO] Graph Created | "
            f"Nodes={G.number_of_nodes()} | "
            f"Edges={G.number_of_edges()}"
        )

        return G

    # =====================================================
    # FIND FAILURE EDGE
    # =====================================================

    def find_failure_edge(
        self,
        simulator,
        config
    ):

        best_edge = None
        best_score = -1

        for u, v, data in simulator.G.edges(data=True):

            road_name = str(
                data.get("road_name", "")
            ).lower()

            road_class = str(
                data.get("road_class", "")
            ).lower()

            score = 0

            for kw in config["target_keywords"]:

                if kw in road_name:
                    score += 10

            if road_class == "motorway":
                score += 8

            elif road_class == "trunk":
                score += 6

            elif road_class == "primary":
                score += 4

            score += (
                data.get("load_ratio", 0) * 10
            )

            score += (
                data.get("capacity", 0) / 1000
            )

            if score > best_score:

                best_score = score
                best_edge = (u, v)

        # fallback
        if best_edge is None:

            degrees = sorted(
                simulator.G.degree(),
                key=lambda x: x[1],
                reverse=True
            )

            center_node = degrees[0][0]

            edges = list(
                simulator.G.edges(center_node)
            )

            if not edges:

                raise Exception(
                    "Unable to determine fallback edge"
                )

            best_edge = edges[0]

        print(
            f"[INFO] Failure edge selected: "
            f"{best_edge}"
        )

        return best_edge

    # =====================================================
    # BUILD SUMMARY
    # =====================================================

    def build_summary(
        self,
        simulator
    ):

        failed_nodes = 0
        degraded_nodes = 0
        congested_edges = 0
        blocked_edges = 0

        total_edge_load = 0
        total_edges = 0

        for _, data in simulator.G.nodes(data=True):

            status = data.get("status")

            if status == "failed":
                failed_nodes += 1

            elif status == "degraded":
                degraded_nodes += 1

        for _, _, data in simulator.G.edges(data=True):

            status = data.get("status")

            if status == "critical":
                congested_edges += 1

            elif status == "blocked":
                blocked_edges += 1

            total_edge_load += data.get(
                "load_ratio",
                0
            )

            total_edges += 1

        avg_network_load = round(
            total_edge_load /
            max(total_edges, 1),
            4
        )

        return {

            "failed_nodes": failed_nodes,

            "degraded_nodes": degraded_nodes,

            "congested_edges": congested_edges,

            "blocked_edges": blocked_edges,

            "average_network_load": avg_network_load
        }

    # =====================================================
    # OVERLOAD DETECTION
    # =====================================================

    def get_overloaded_junctions(
        self,
        simulator
    ):

        overloaded = []

        for node, data in simulator.G.nodes(data=True):

            queue_pressure = data.get(
                "queue_pressure",
                0
            )

            if queue_pressure >= 0.85:

                overloaded.append({

                    "node_id": str(node),

                    "status": data.get(
                        "status",
                        "normal"
                    ),

                    "queue_pressure": round(
                        queue_pressure,
                        3
                    ),

                    "incoming_load": int(
                        data.get(
                            "incoming_load",
                            0
                        )
                    ),

                    "outgoing_load": int(
                        data.get(
                            "outgoing_load",
                            0
                        )
                    ),

                    "signal_stability": round(
                        data.get(
                            "signal_stability",
                            1
                        ),
                        3
                    ),

                    "spillback_probability": round(
                        data.get(
                            "spillback_probability",
                            0
                        ),
                        3
                    )
                })

        overloaded = sorted(
            overloaded,
            key=lambda x: x["queue_pressure"],
            reverse=True
        )

        return overloaded

    # =====================================================
    # RUN HOTSPOT
    # =====================================================

    def run_hotspot(
        self,
        hotspot_id
    ):

        try:

            if hotspot_id not in HOTSPOTS:

                return {

                    "success": False,

                    "error": (
                        f"Unknown hotspot: "
                        f"{hotspot_id}"
                    )
                }

            config = HOTSPOTS[hotspot_id]

            print("\n" + "=" * 60)

            print(
                f"SIMULATING HOTSPOT: "
                f"{config['name']}"
            )

            print("=" * 60)

            # =================================================
            # FETCH OSM
            # =================================================

            geojson_path = self.fetch_hotspot_geojson(
                hotspot_id,
                config
            )

            # =================================================
            # BUILD GRAPH
            # =================================================

            G = self.build_graph(
                hotspot_id,
                geojson_path
            )

            # =================================================
            # INITIALIZE SIMULATOR
            # =================================================

            simulator = RoadCascadeSimulator(G)

            # reduce heavy computation
            simulator.num_driver_agents = 800
            simulator.redistribution_iterations = 3
            simulator.max_reroute_paths = 2

            simulator.prepare_graph(

                baseline_load_range=(

                    config["baseline_load"][0],

                    config["baseline_load"][1]
                )
            )

            # =================================================
            # FIND FAILURE EDGE
            # =================================================

            major_edge = self.find_failure_edge(
                simulator,
                config
            )

            # =================================================
            # APPLY FAILURE
            # =================================================

            failure_type = config["failure_type"]

            if failure_type == "road_blockage":

                failure_result = (
                    simulator.inject_road_blockage(
                        major_edge,
                        f"{hotspot_id}_road_block"
                    )
                )

            elif failure_type == "signal_failure":

                failure_result = (
                    simulator.inject_signal_failure(
                        major_edge[0],
                        "signal_power_outage"
                    )
                )

            elif failure_type == "flyover_closure":

                failure_result = (
                    simulator.inject_flyover_closure(
                        major_edge,
                        "flyover_structural_issue"
                    )
                )

            else:

                failure_result = (
                    simulator.inject_road_blockage(
                        major_edge,
                        "unknown_failure"
                    )
                )

            failure_result["target_id"] = major_edge

            failure_result["displaced_traffic"] = (
                config["reroute_pressure"]
            )

            # =================================================
            # CASCADE
            # =================================================

            print("[INFO] Propagating cascade...")

            cascade_result = (
                simulator.propagate_cascade(
                    failure_result,
                    max_iterations=config[
                        "max_iterations"
                    ]
                )
            )

            # =================================================
            # OVERLOADS
            # =================================================

            overloaded = self.get_overloaded_junctions(
                simulator
            )

            # =================================================
            # ALTERNATE ROUTES
            # =================================================

            alternate_routes = []

            nodes = list(simulator.G.nodes())

            if len(nodes) > 20:

                for _ in range(2):

                    src = random.choice(nodes)
                    dst = random.choice(nodes)

                    if src == dst:
                        continue

                    try:

                        alt = (
                            simulator
                            .find_alternate_routes(
                                src,
                                dst,
                                k=2
                            )
                        )

                        if alt.get("routes"):

                            alternate_routes.extend(
                                alt["routes"]
                            )

                    except Exception:
                        continue

            simulator.G.graph[
                "alternate_routes"
            ] = alternate_routes

            # =================================================
            # VISUALIZATION
            # =================================================

            print("[INFO] Creating visualization...")

            visualizer = CascadeVisualizer(
                output_dir=self.graph_dir
            )

            map_filename = (
                f"cascade_{hotspot_id}.html"
            )

            visualizer.create_cascade_map(

                simulator.G,

                title=(
                    f"{config['severity']} "
                    f"CASCADE FAILURE - "
                    f"{config['name']}"
                ),

                filename=map_filename
            )

            # =================================================
            # SUMMARY
            # =================================================

            summary = self.build_summary(
                simulator
            )

            # =================================================
            # RESPONSE
            # =================================================

            response = {

                "success": True,

                "hotspot_id": hotspot_id,

                "hotspot": config["name"],

                "description": config[
                    "description"
                ],

                "severity": config[
                    "severity"
                ],

                "failure_type": failure_type,

                "failure_point": {
                    "edge": list(major_edge)
                },

                "iterations": cascade_result.get(
                    "iterations",
                    0
                ),

                "total_overloaded": (
                    cascade_result.get(
                        "total_overloaded",
                        0
                    )
                ),

                "failed_nodes": summary[
                    "failed_nodes"
                ],

                "degraded_nodes": summary[
                    "degraded_nodes"
                ],

                "congested_edges": summary[
                    "congested_edges"
                ],

                "blocked_edges": summary[
                    "blocked_edges"
                ],

                "average_network_load": (
                    summary[
                        "average_network_load"
                    ]
                ),

                "alternate_routes_found": (
                    len(alternate_routes)
                ),

                "overloaded_junctions": (
                    overloaded[:15]
                ),

                "map_url": (
                    f"/maps/{map_filename}"
                ),

                "graph_stats": {

                    "nodes": (
                        simulator.G
                        .number_of_nodes()
                    ),

                    "edges": (
                        simulator.G
                        .number_of_edges()
                    )
                },

                "cascade_stats": cascade_result
            }

            print(
                "[SUCCESS] Hotspot simulation completed."
            )

            return response

        except Exception as e:

            print(
                "\n===== HOTSPOT SIMULATION ERROR ====="
            )

            traceback.print_exc()

            return {

                "success": False,

                "error": str(e)
            }


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    simulator = HotspotSimulator()

    result = simulator.run_hotspot(
        "silk_board"
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )