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

                    road_type=row.get(
                        "road_node_type",
                        "N/A"
                    ),

                    highway_type=row.get(
                        "highway_type",
                        "N/A"
                    ),

                    importance=row.get(
                        "importance",
                        "N/A"
                    ),

                    source="xlsx"
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

                        road_name=properties.get(
                            "name",
                            "N/A"
                        ),

                        road_class=properties.get(
                            "class",
                            properties.get(
                                "highway",
                                "N/A"
                            )
                        ),

                        source="geojson"
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

                        road_name=properties.get(
                            "name",
                            "N/A"
                        ),

                        road_class=properties.get(
                            "class",
                            properties.get(
                                "highway",
                                "N/A"
                            )
                        )
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

                folium.PolyLine(
                    locations=[
                        point1,
                        point2
                    ],
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