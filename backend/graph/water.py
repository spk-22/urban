"""
FIXED water.py
=========================================
WATER GEOJSON / XLSX → GRAPH CREATION + VISUALIZATION

Supports:
1. GeoJSON pipeline network
2. XLSX processed water infrastructure
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
import pandas as pd


class WaterGraphBuilder:

    def __init__(self):

        BASE_DIR = Path(__file__).resolve().parents[2]

        self.output_dir = (
            BASE_DIR / "data" / "graphs"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        print(
            f"Water graph output directory: "
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
    # BUILD GRAPH FROM GEOJSON
    # =====================================
    def build_graph_from_geojson(
        self,
        geojson_data
    ):

        G = nx.Graph()

        node_counter = 0

        coord_to_node = {}

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

            geometry_type = geometry.get(
                "type"
            )

            coordinates = geometry.get(
                "coordinates",
                []
            )

            # =================================
            # LINESTRING
            # =================================
            if geometry_type == "LineString":

                previous_node = None

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
                            f"W{node_counter}"
                        )

                        coord_to_node[
                            current_coord
                        ] = node_id

                        G.add_node(
                            node_id,
                            latitude=lat,
                            longitude=lon,
                            infrastructure=properties.get(
                                "type",
                                "pipeline_node"
                            ),
                            name=properties.get(
                                "name",
                                "N/A"
                            )
                        )

                        node_counter += 1

                    current_node = (
                        coord_to_node[
                            current_coord
                        ]
                    )

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
                            pipeline_name=properties.get(
                                "name",
                                "N/A"
                            ),
                            pipeline_type=properties.get(
                                "type",
                                "N/A"
                            )
                        )

                    previous_node = current_node

        return G

    # =====================================
    # BUILD GRAPH FROM XLSX
    # =====================================
    def build_graph_from_xlsx(
        self,
        xlsx_path
    ):

        try:

            df = pd.read_excel(
                xlsx_path
            )

            G = nx.Graph()

            previous_node = None

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

                node_id = (
                    f"W{index}"
                )

                G.add_node(
                    node_id,
                    latitude=lat,
                    longitude=lon,
                    water_type=row.get(
                        "type",
                        "N/A"
                    ),
                    name=row.get(
                        "name",
                        "N/A"
                    ),
                    operator=row.get(
                        "operator",
                        "N/A"
                    ),
                    landuse=row.get(
                        "landuse",
                        "N/A"
                    ),
                    man_made=row.get(
                        "man_made",
                        "N/A"
                    )
                )

                # =============================
                # LOGICAL CONNECTION
                # =============================
                if previous_node:

                    prev_coord = (
                        G.nodes[
                            previous_node
                        ]["latitude"],

                        G.nodes[
                            previous_node
                        ]["longitude"]
                    )

                    current_coord = (
                        lat,
                        lon
                    )

                    distance = (
                        self.calculate_distance(
                            prev_coord,
                            current_coord
                        )
                    )

                    G.add_edge(
                        previous_node,
                        node_id,
                        weight=distance
                    )

                previous_node = node_id

            return G

        except Exception as e:

            print(
                f"Error building graph "
                f"from XLSX: {e}"
            )

            return None

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
                "water_network.graphml"
            )

            nx.write_graphml(
                G,
                graph_path
            )

            print(
                f"Water GraphML saved at: "
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

            water_map = folium.Map(
                location=[
                    center_lat,
                    center_lon
                ],
                zoom_start=11
            )

            # =============================
            # EDGES
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
                ).add_to(water_map)

            # =============================
            # NODES
            # =============================
            for node, data in G.nodes(
                data=True
            ):

                popup_text = (
                    f"{data.get('name', 'N/A')} "
                    f"({data.get('water_type', 'N/A')})"
                )

                folium.CircleMarker(
                    location=(
                        data["latitude"],
                        data["longitude"]
                    ),
                    radius=3,
                    popup=popup_text
                ).add_to(water_map)

            map_path = (
                self.output_dir /
                "water_network_map.html"
            )

            water_map.save(
                str(map_path)
            )

            print(
                f"Interactive map saved at: "
                f"{map_path}"
            )

            return map_path

        except Exception as e:

            print(
                f"Error visualizing water map: "
                f"{e}"
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
                node_size=8,
                with_labels=False
            )

            png_path = (
                self.output_dir /
                "water_network_graph.png"
            )

            plt.title(
                "Water Infrastructure Network"
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
    # COMPLETE WATER PIPELINE
    # =====================================
    def process_water_network(
        self,
        input_path,
        input_type="geojson"
    ):

        # =================================
        # GEOJSON
        # =================================
        if input_type == "geojson":

            geojson_data = (
                self.load_geojson(
                    input_path
                )
            )

            if not geojson_data:
                return None

            G = (
                self.build_graph_from_geojson(
                    geojson_data
                )
            )

        # =================================
        # XLSX
        # =================================
        elif input_type == "xlsx":

            G = (
                self.build_graph_from_xlsx(
                    input_path
                )
            )

        else:

            print(
                "Unsupported input type."
            )

            return None

        # =================================
        # EMPTY GRAPH CHECK
        # =================================
        if (
            G is None
            or
            G.number_of_nodes() == 0
        ):

            print(
                "No valid water nodes found."
            )

            return None

        # =================================
        # SAVE OUTPUTS
        # =================================
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

    builder = WaterGraphBuilder()

    file_path = input(
        "Enter water file path: "
    ).strip()

    input_type = input(
        "Enter type (geojson/xlsx): "
    ).strip().lower()

    result = (
        builder.process_water_network(
            file_path,
            input_type
        )
    )

    if result:

        print(
            "\n===== WATER GRAPH PROCESS COMPLETE ====="
        )

        print(result)

    else:
        print("Processing failed.")


if __name__ == "__main__":
    main()