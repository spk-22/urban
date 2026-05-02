"""
FIXED road.py
=========================================
ROAD XML DATAFRAME → GRAPH CREATION + VISUALIZATION
Supports:
1. GeoJSON input
2. Parsed XML dataframe input
3. Saves:
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


class RoadGraphBuilder:
    def __init__(self):
        BASE_DIR = Path(__file__).resolve().parents[2]

        self.output_dir = BASE_DIR / "data" / "graphs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Graph output directory: {self.output_dir}")

    # =====================================
    # DISTANCE CALCULATOR
    # =====================================
    def calculate_distance(self, coord1, coord2):
        try:
            return geodesic(coord1, coord2).meters
        except Exception:
            return 0

    # =====================================
    # LOAD GEOJSON
    # =====================================
    def load_geojson(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading GeoJSON: {e}")
            return None

    # =====================================
    # BUILD GRAPH FROM GEOJSON
    # =====================================
    def build_graph(self, geojson_data):
        G = nx.Graph()
        node_counter = 0
        coord_to_node = {}

        for feature in geojson_data.get("features", []):
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})

            if geometry.get("type") != "LineString":
                continue

            coordinates = geometry.get("coordinates", [])
            previous_node = None

            for coord in coordinates:
                lon, lat = coord
                current_coord = (lat, lon)

                if current_coord not in coord_to_node:
                    node_id = f"N{node_counter}"
                    coord_to_node[current_coord] = node_id

                    G.add_node(
                        node_id,
                        latitude=lat,
                        longitude=lon
                    )

                    node_counter += 1

                current_node = coord_to_node[current_coord]

                if previous_node:
                    prev_coord = (
                        G.nodes[previous_node]["latitude"],
                        G.nodes[previous_node]["longitude"]
                    )

                    distance = self.calculate_distance(
                        prev_coord,
                        current_coord
                    )

                    G.add_edge(
                        previous_node,
                        current_node,
                        weight=distance,
                        road_name=properties.get("name", "N/A"),
                        road_class=properties.get("class", "N/A")
                    )

                previous_node = current_node

        return G

    # =====================================
    # BUILD GRAPH FROM XML DATAFRAME
    # =====================================
    def build_graph_from_dataframe(self, df):
        try:
            G = nx.Graph()

            previous_node = None

            for index, row in df.iterrows():
                try:
                    lat = float(row["latitude"])
                    lon = float(row["longitude"])
                except:
                    continue

                node_id = str(row["node_id"])

                G.add_node(
                    node_id,
                    latitude=lat,
                    longitude=lon,
                    road_type=row.get("road_node_type", "N/A"),
                    highway_type=row.get("highway_type", "N/A"),
                    importance=row.get("importance", "N/A")
                )

                # Sequential connection
                if previous_node:
                    prev_coord = (
                        G.nodes[previous_node]["latitude"],
                        G.nodes[previous_node]["longitude"]
                    )

                    current_coord = (lat, lon)

                    distance = self.calculate_distance(
                        prev_coord,
                        current_coord
                    )

                    G.add_edge(
                        previous_node,
                        node_id,
                        weight=distance
                    )

                previous_node = node_id

            if G.number_of_nodes() == 0:
                print("No valid road nodes found.")
                return None

            graph_file = self.save_graph(G)
            html_map = self.visualize_interactive_map(G)
            png_graph = self.visualize_static_graph(G)

            return {
                "graph": G,
                "graphml": str(graph_file) if graph_file else None,
                "interactive_map": str(html_map) if html_map else None,
                "static_graph": str(png_graph) if png_graph else None,
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges()
            }

        except Exception as e:
            print(f"Error building graph from dataframe: {e}")
            return None

    # =====================================
    # SAVE GRAPH
    # =====================================
    def save_graph(self, G):
        try:
            graph_path = self.output_dir / "road_network.graphml"

            nx.write_graphml(G, graph_path)

            print(f"GraphML saved at: {graph_path}")

            return graph_path

        except Exception as e:
            print(f"Error saving graph: {e}")
            return None

    # =====================================
    # INTERACTIVE MAP
    # =====================================
    def visualize_interactive_map(self, G):
        try:
            lats = [data["latitude"] for _, data in G.nodes(data=True)]
            lons = [data["longitude"] for _, data in G.nodes(data=True)]

            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)

            road_map = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=12
            )

            for u, v in G.edges():
                point1 = (
                    G.nodes[u]["latitude"],
                    G.nodes[u]["longitude"]
                )

                point2 = (
                    G.nodes[v]["latitude"],
                    G.nodes[v]["longitude"]
                )

                folium.PolyLine(
                    locations=[point1, point2],
                    weight=2
                ).add_to(road_map)

            map_path = self.output_dir / "road_network_map.html"
            road_map.save(str(map_path))

            print(f"Interactive map saved at: {map_path}")

            return map_path

        except Exception as e:
            print(f"Error visualizing map: {e}")
            return None

    # =====================================
    # STATIC GRAPH
    # =====================================
    def visualize_static_graph(self, G):
        try:
            plt.figure(figsize=(20, 16))

            pos = {
                node: (
                    data["longitude"],
                    data["latitude"]
                )
                for node, data in G.nodes(data=True)
            }

            nx.draw(
                G,
                pos,
                node_size=1,
                with_labels=False
            )

            png_path = self.output_dir / "road_network_graph.png"

            plt.title("Road Infrastructure Network")
            plt.savefig(png_path, dpi=300)
            plt.close()

            print(f"Static graph saved at: {png_path}")

            return png_path

        except Exception as e:
            print(f"Error visualizing static graph: {e}")
            return None

    # =====================================
    # COMPLETE GEOJSON PIPELINE
    # =====================================
    def process_road_network(self, geojson_path):
        geojson_data = self.load_geojson(geojson_path)

        if not geojson_data:
            return None

        G = self.build_graph(geojson_data)

        if G.number_of_nodes() == 0:
            return None

        graph_file = self.save_graph(G)
        html_map = self.visualize_interactive_map(G)
        png_graph = self.visualize_static_graph(G)

        return {
            "graph": G,
            "graphml": str(graph_file) if graph_file else None,
            "interactive_map": str(html_map) if html_map else None,
            "static_graph": str(png_graph) if png_graph else None,
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges()
        }