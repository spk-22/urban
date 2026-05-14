"""
FIXED road.py
=========================================
ROAD XLSX + GEOJSON → GRAPH CREATION + VISUALIZATION

Uses:
1. Processed XML Excel file
   (/data/processed/road_infrastructure.xlsx)

2. Processed GeoJSON/KML file
   (road_network_geojson.json)

Final Output:
- Unified Road Graph
- GraphML
- Interactive HTML map
- PNG graph
=========================================
"""

import json
from pathlib import Path

import networkx as nx
from geopy.distance import geodesic
import folium
import matplotlib.pyplot as plt
import pandas as pd

# =========================================
# ROAD CLASS DEFAULTS
# =========================================
ROAD_CLASS_DEFAULTS = {
    "motorway":    {"speed_kmh": 80, "edge_capacity": 4000, "node_capacity": 6000},
    "trunk":       {"speed_kmh": 60, "edge_capacity": 3000, "node_capacity": 4500},
    "primary":     {"speed_kmh": 50, "edge_capacity": 2000, "node_capacity": 3500},
    "secondary":   {"speed_kmh": 40, "edge_capacity": 1500, "node_capacity": 2500},
    "tertiary":    {"speed_kmh": 30, "edge_capacity": 1000, "node_capacity": 1500},
    "residential": {"speed_kmh": 20, "edge_capacity": 500,  "node_capacity": 800},
    "service":     {"speed_kmh": 15, "edge_capacity": 300,  "node_capacity": 500},
    "unclassified": {"speed_kmh": 25, "edge_capacity": 600, "node_capacity": 900},
}

DEFAULT_ROAD = {"speed_kmh": 30, "edge_capacity": 800, "node_capacity": 1200}

# BPR formula constants
BPR_ALPHA = 0.15
BPR_BETA = 4.0


class RoadGraphBuilder:

    def __init__(self):

        BASE_DIR = Path(__file__).resolve().parents[2]

        self.output_dir = (
            BASE_DIR /
            "data" /
            "graphs"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        print(
            f"Road graph output directory: "
            f"{self.output_dir}"
        )

    # =====================================
    # DISTANCE CALCULATOR
    # =====================================
    def calculate_distance(
        self,
        coord1,
        coord2
    ):

        try:

            return geodesic(
                coord1,
                coord2
            ).meters

        except Exception:
            return 0

    # =====================================
    # LOAD GEOJSON
    # =====================================
    def load_geojson(
        self,
        file_path
    ):

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)

        except Exception as e:

            print(
                f"Error loading GeoJSON: {e}"
            )

            return None

    # =====================================
    # BUILD UNIFIED GRAPH
    # =====================================
    def build_graph(
        self,
        xlsx_path,
        geojson_path
    ):

        G = nx.Graph()

        coord_to_node = {}

        node_counter = 0

        # =================================
        # LOAD XLSX
        # =================================
        try:

            df = pd.read_excel(
                xlsx_path
            )

            print(
                f"Loaded XLSX rows: "
                f"{len(df)}"
            )

        except Exception as e:

            print(
                f"Error reading XLSX: {e}"
            )

            return None

        # =================================
        # LOAD GEOJSON
        # =================================
        geojson_data = self.load_geojson(
            geojson_path
        )

        if not geojson_data:
            return None

        # =================================
        # ADD XLSX NODES
        # =================================
        for index, row in df.iterrows():

            try:

                lat = float(
                    row["latitude"]
                )

                lon = float(
                    row["longitude"]
                )

            except:
                continue

            current_coord = (
                lat,
                lon
            )

            if (
                current_coord
                not in coord_to_node
            ):

                node_id = (
                    f"R{node_counter}"
                )

                coord_to_node[
                    current_coord
                ] = node_id

                G.add_node(
                    node_id,
                    latitude=lat,
                    longitude=lon,
                    road_type=row.get("road_node_type", "N/A"),
                    highway_type=row.get("highway_type", "N/A"),
                    importance=row.get("importance", "N/A"),
                    source="xlsx",
                    # capacity attributes
                    capacity=800,  # placeholder, will be updated later via enhance_graph
                    current_load=0,
                    load_ratio=0.0,
                    node_type="junction",
                    status="normal"
                )

                node_counter += 1

        print(
            f"Road facility nodes added: "
            f"{G.number_of_nodes()}"
        )

        # =================================
        # PROCESS GEOJSON FEATURES
        # =================================
        for feature in geojson_data.get(
            "features",
            []
        ):

            properties = feature.get(
                "properties",
                {}
            )

            geometry = feature.get(
                "geometry",
                {}
            )

            if geometry.get(
                "type"
            ) != "LineString":

                continue

            coordinates = geometry.get(
                "coordinates",
                []
            )

            edge_geometry = [[lat, lon] for lon, lat in coordinates]
            previous_node = None

            # =============================
            # ROAD SEGMENTS
            # =============================
            for coord in coordinates:

                lon, lat = coord

                current_coord = (
                    lat,
                    lon
                )

                if (
                    current_coord
                    not in coord_to_node
                ):

                    node_id = (
                        f"R{node_counter}"
                    )

                    coord_to_node[
                        current_coord
                    ] = node_id

                    G.add_node(
                        node_id,
                        latitude=lat,
                        longitude=lon,
                        road_name=properties.get("name", "N/A"),
                        road_class=properties.get("class", properties.get("highway", "N/A")),
                        source="geojson",
                        # capacity attributes
                        capacity=800,
                        current_load=0,
                        load_ratio=0.0,
                        node_type="junction",
                        status="normal"
                    )

                    node_counter += 1

                current_node = coord_to_node[
                    current_coord
                ]

                # =========================
                # CREATE EDGES
                # =========================
                if previous_node:

                    prev_coord = (

                        G.nodes[
                            previous_node
                        ]["latitude"],

                        G.nodes[
                            previous_node
                        ]["longitude"]
                    )

                    distance = (
                        self.calculate_distance(
                            prev_coord,
                            current_coord
                        )
                    )

                    G.add_edge(
                        previous_node,
                        current_node,
                        weight=distance,
                        # capacity attributes (placeholder values, will be refined later)
                        capacity=800,
                        current_load=0,
                        free_flow_time=distance / (50 * 1000 / 3600),  # assuming 50 km/h speed, convert to m/s
                        current_travel_time=distance / (50 * 1000 / 3600),
                        status="open",
                        geometry=edge_geometry # Store full LineString geometry
                    )

                previous_node = current_node

        print(
            f"Final Graph Nodes: "
            f"{G.number_of_nodes()}"
        )

        print(
            f"Final Graph Edges: "
            f"{G.number_of_edges()}"
        )

        return G

    # =====================================
    # SAVE GRAPH
    # =====================================
    def save_graph(
        self,
        G
    ):

        try:

            graph_path = (
                self.output_dir /
                "road_network.graphml"
            )

            nx.write_graphml(
                G,
                graph_path
            )

            print(
                f"Road GraphML saved at: "
                f"{graph_path}"
            )

            return graph_path

        except Exception as e:

            print(
                f"Error saving graph: {e}"
            )

            return None

    # =====================================
    # INTERACTIVE MAP
    # =====================================
    def visualize_interactive_map(
        self,
        G
    ):

        try:

            lats = [
                data["latitude"]
                for _, data
                in G.nodes(data=True)
            ]

            lons = [
                data["longitude"]
                for _, data
                in G.nodes(data=True)
            ]

            center_lat = (
                sum(lats) / len(lats)
            )

            center_lon = (
                sum(lons) / len(lons)
            )

            road_map = folium.Map(
                location=[
                    center_lat,
                    center_lon
                ],
                zoom_start=12
            )

            # =============================
            # DRAW EDGES
            # =============================
            for u, v in G.edges():

                point1 = (
                    G.nodes[u]["latitude"],
                    G.nodes[u]["longitude"]
                )

                point2 = (
                    G.nodes[v]["latitude"],
                    G.nodes[v]["longitude"]
                )

                geom = G.edges[u, v].get("geometry")
                if geom:
                    locations = geom
                else:
                    locations = [point1, point2]

                folium.PolyLine(
                    locations=locations,
                    weight=2
                ).add_to(road_map)

            # =============================
            # DRAW NODES
            # =============================
            for node, data in G.nodes(
                data=True
            ):

                popup_text = (
                    f"{data.get('road_name', 'Road Node')} "
                    f"({data.get('road_class', 'N/A')})"
                )

                folium.CircleMarker(
                    location=(
                        data["latitude"],
                        data["longitude"]
                    ),

                    radius=2,

                    popup=popup_text
                ).add_to(road_map)

            map_path = (
                self.output_dir /
                "road_network_map.html"
            )

            road_map.save(
                str(map_path)
            )

            print(
                f"Interactive map saved at: "
                f"{map_path}"
            )

            return map_path

        except Exception as e:

            print(
                f"Error visualizing map: {e}"
            )

            return None

    # =====================================
    # STATIC GRAPH
    # =====================================
    def visualize_static_graph(
        self,
        G
    ):

        try:

            plt.figure(
                figsize=(20, 16)
            )

            pos = {

                node: (
                    data["longitude"],
                    data["latitude"]
                )

                for node, data
                in G.nodes(data=True)
            }

            nx.draw(
                G,
                pos,

                node_size=1,

                with_labels=False
            )

            png_path = (
                self.output_dir /
                "road_network_graph.png"
            )

            plt.title(
                "Road Infrastructure Network"
            )

            plt.savefig(
                png_path,
                dpi=300
            )

            plt.close()

            print(
                f"Static graph saved at: "
                f"{png_path}"
            )

            return png_path

        except Exception as e:

            print(
                f"Error visualizing graph: {e}"
            )

            return None

    # =====================================
    # COMPLETE ROAD PIPELINE
    # =====================================
    def assign_capacities(self, G):
        """Assign realistic capacity, speed, and derived attributes to nodes and edges.
        Uses ROAD_CLASS_DEFAULTS mapping based on road_class/highway_type.
        Also initializes random baseline loads (~50-70% of capacity).
        """
        import random
        for node, data in G.nodes(data=True):
            rc = data.get('road_class') or data.get('highway_type') or data.get('road_type')
            rc_key = rc.lower() if rc else 'default'
            defaults = ROAD_CLASS_DEFAULTS.get(rc_key, DEFAULT_ROAD)
            cap = defaults['node_capacity']
            load = int(cap * random.uniform(0.45, 0.7))
            data.update({
                'capacity': cap,
                'current_load': load,
                'load_ratio': round(load / cap, 4),
                'node_type': data.get('node_type', 'junction'),
                'status': 'normal'
            })
        for u, v, data in G.edges(data=True):
            rc = data.get('road_class') or data.get('highway')
            rc_key = rc.lower() if rc else 'default'
            defaults = ROAD_CLASS_DEFAULTS.get(rc_key, DEFAULT_ROAD)
            cap = defaults['edge_capacity']
            speed = defaults['speed_kmh']
            distance = data.get('weight', 0)
            free_flow = (distance / 1000) / speed * 3600  # seconds
            load = int(cap * random.uniform(0.45, 0.7))
            travel_time = free_flow * (1 + BPR_ALPHA * (load / cap) ** BPR_BETA)
            data.update({
                'capacity': cap,
                'current_load': load,
                'load_ratio': round(load / cap, 4),
                'speed_kmh': speed,
                'free_flow_time': round(free_flow, 2),
                'current_travel_time': round(travel_time, 2),
                'status': 'open'
            })
        return G

    # =====================================
    # COMPLETE ROAD PIPELINE
    # =====================================
    def process_road_network(
        self,
        xlsx_path,
        geojson_path
    ):

        G = self.build_graph(
            xlsx_path,
            geojson_path
        )

        if (
            G is None
            or G.number_of_nodes() == 0
        ):

            print(
                "No valid road nodes found."
            )

            return None

        # Assign capacities and loads
        G = self.assign_capacities(G)

        graph_file = self.save_graph(G)

        html_map = (
            self.visualize_interactive_map(G)
        )

        png_graph = (
            self.visualize_static_graph(G)
        )

        return {

            "graph": G,

            "graphml": str(graph_file)
            if graph_file else None,

            "interactive_map": str(html_map)
            if html_map else None,

            "static_graph": str(png_graph)
            if png_graph else None,

            "nodes": G.number_of_nodes(),

            "edges": G.number_of_edges()
        }


# =====================================
# TESTING
# =====================================
def main():

    BASE_DIR = Path(__file__).resolve().parents[2]

    xlsx_path = (
        BASE_DIR /
        "data" /
        "processed" /
        "road_infrastructure.xlsx"
    )

    geojson_path = (
        BASE_DIR /
        "data" /
        "processed" /
        "road_network_geojson.json"
    )

    builder = RoadGraphBuilder()

    result = builder.process_road_network(
        str(xlsx_path),
        str(geojson_path)
    )

    if result:

        print(
            "\n===== ROAD GRAPH PROCESS COMPLETE ====="
        )

        print(result)

    else:
        print("Processing failed.")


if __name__ == "__main__":
    main()