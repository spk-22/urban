"""
XML Parser for OSM Files (Power & Water Infrastructure)
GUI file upload + Correct output path + Required columns
"""

import xml.etree.ElementTree as ET
import pandas as pd
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog
import openpyxl 

class OSMParser:
    def __init__(self):
        # ✅ Project root
        BASE_DIR = Path(__file__).resolve().parents[2]

        # ✅ Output directory
        self.output_dir = BASE_DIR / "data" / "processed"

        print(f"DEBUG: Saving files to -> {self.output_dir}")

        self.create_output_directory()

    def create_output_directory(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            print(f"Output directory ready: {self.output_dir}")
        except Exception as e:
            print(f"Error creating output directory: {e}")
            sys.exit(1)

    def upload_file(self):
        print("\nOpening file dialog...")

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        file_path = filedialog.askopenfilename(
            title="Select OSM File",
            filetypes=[("OSM Files", "*.osm")]
        )

        if not file_path:
            print("No file selected. Exiting.")
            sys.exit(1)

        print(f"Selected file: {file_path}")
        return file_path

    def detect_file_type(self, file_path):
        filename = os.path.basename(file_path).lower()

        if 'power' in filename:
            return 'power'
        elif 'water' in filename:
            return 'water'
        else:
            choice = input("Enter 1 for Power or 2 for Water: ").strip()
            if choice == '1':
                return 'power'
            elif choice == '2':
                return 'water'
            else:
                print("Invalid choice.")
                sys.exit(1)

    # ================= POWER PARSER =================
    def parse_power_osm(self, file_path):
        print("\nParsing Power Infrastructure...")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except Exception as e:
            print(f"Error: {e}")
            return None

        data = []

        REQUIRED = [
            "frequency", "location", "name", "operator",
            "power", "rating", "ref", "start_date",
            "substation", "voltage"
        ]

        node_coords = {}
        for node in root.findall("node"):
            node_id = node.get("id")
            lat = node.get("lat")
            lon = node.get("lon")
            if lat and lon:
                node_coords[node_id] = (lat, lon)

        def get_tags(element):
            return {tag.get("k"): tag.get("v") for tag in element.findall("tag")}

        for element in root.findall("node") + root.findall("way"):
            tags = get_tags(element)

            if tags.get("power") in ["substation", "station"]:
                if all(field in tags for field in REQUIRED):

                    lat, lon = "N/A", "N/A"

                    if element.tag == "node":
                        lat = element.get("lat", "N/A")
                        lon = element.get("lon", "N/A")

                    elif element.tag == "way":
                        node_refs = [nd.get("ref") for nd in element.findall("nd")]
                        if node_refs and node_refs[0] in node_coords:
                            lat, lon = node_coords[node_refs[0]]

                    data.append({
                        "frequency": tags["frequency"],
                        "location": tags["location"],
                        "name": tags["name"],
                        "operator": tags["operator"],
                        "power": tags["power"],
                        "rating": tags["rating"],
                        "reference": tags["ref"],
                        "start_date": tags["start_date"],
                        "substation": tags["substation"],
                        "voltage": tags["voltage"],
                        "latitude": lat,
                        "longitude": lon
                    })

        if not data:
            print("No power data found")
            return None

        df = pd.DataFrame(data)
        print(f"Extracted {len(df)} power records")
        return df

    # ================= WATER PARSER =================
    def parse_water_osm(self, file_path):
        print("\nParsing Water Infrastructure...")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except Exception as e:
            print(f"Error: {e}")
            return None

        data = []

        node_coords = {}
        for node in root.findall("node"):
            node_id = node.get("id")
            lat = node.get("lat")
            lon = node.get("lon")

            if node_id and lat and lon:
                node_coords[node_id] = (float(lat), float(lon))

        def get_tags(element):
            return {tag.get("k"): tag.get("v") for tag in element.findall("tag")}

        def get_center(refs):
            lats, lons = [], []
            for ref in refs:
                if ref in node_coords:
                    lat, lon = node_coords[ref]
                    lats.append(lat)
                    lons.append(lon)

            if lats:
                return sum(lats) / len(lats), sum(lons) / len(lons)
            return None, None

        for element in root.findall("node") + root.findall("way"):
            tags = get_tags(element)

            if (
                tags.get("man_made") == "water_works"
                or tags.get("landuse") in ["reservoir", "basin"]
            ):

                name = tags.get("name", "N/A").lower()

                if "tank" in name:
                    asset_type = "Water Tank"
                elif "reservoir" in name:
                    asset_type = "Reservoir"
                else:
                    asset_type = "Water Works"

                if element.tag == "node":
                    lat = element.get("lat")
                    lon = element.get("lon")
                    node_refs = element.get("id")
                else:
                    refs = [nd.get("ref") for nd in element.findall("nd")]
                    node_refs = ",".join(refs)
                    lat, lon = get_center(refs)

                data.append({
                    "type": asset_type,
                    "node_ref": node_refs,
                    "name": tags.get("name", "N/A"),
                    "operator": tags.get("operator", "N/A"),
                    "landuse": tags.get("landuse", "N/A"),
                    "man_made": tags.get("man_made", "N/A"),
                    "latitude": lat,
                    "longitude": lon
                })

        if not data:
            print("No water data found")
            return None

        df = pd.DataFrame(data)

        df.drop_duplicates(inplace=True)
        df.dropna(subset=["latitude", "longitude"], inplace=True)

        df = df[
            ["type", "node_ref", "name", "operator", "landuse", "man_made", "latitude", "longitude"]
        ]

        print(f"Extracted {len(df)} water records")
        return df
        # ================= ROAD PARSER =================
    def parse_road_osm(self, file_path):
        print("\nParsing Road Infrastructure...")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except Exception as e:
            print(f"Error parsing XML file: {e}")
            return None

        data = []

        # =========================
        # TAG EXTRACTION HELPER
        # =========================
        def get_tags(element):
            return {
                tag.get("k"): tag.get("v")
                for tag in element.findall("tag")
            }

        # =========================
        # NODE PROCESSING
        # =========================
        for node in root.findall("node"):
            node_id = node.get("id")
            lat = node.get("lat")
            lon = node.get("lon")

            if not node_id or not lat or not lon:
                continue

            tags = get_tags(node)

            # =========================
            # ROAD FEATURES
            # =========================
            highway_type = tags.get("highway", "normal")
            crossing_type = tags.get("crossing", "N/A")
            traffic_signal = tags.get("traffic_signals", "N/A")
            junction_type = tags.get("junction", "N/A")

            # =========================
            # ROAD NODE TYPE
            # =========================
            if highway_type == "traffic_signals":
                road_node_type = "Traffic Signal Junction"

            elif crossing_type != "N/A":
                road_node_type = "Crossing"

            elif junction_type != "N/A":
                road_node_type = f"Junction ({junction_type})"

            elif highway_type in [
                "motorway",
                "trunk",
                "primary",
                "secondary",
                "tertiary",
                "residential",
                "service"
            ]:
                road_node_type = "Road Infrastructure Node"

            else:
                road_node_type = "General Road Node"

            # =========================
            # IMPORTANCE CLASSIFICATION
            # =========================
            if highway_type in ["motorway", "trunk", "primary"]:
                importance = "Highway"

            elif highway_type in ["secondary", "tertiary"]:
                importance = "Major Road"

            elif highway_type == "traffic_signals":
                importance = "Critical Traffic Point"

            elif crossing_type != "N/A":
                importance = "Pedestrian Crossing"

            else:
                importance = "Normal"

            # =========================
            # STORE DATA
            # =========================
            data.append({
                "node_id": node_id,
                "latitude": lat,
                "longitude": lon,
                "road_node_type": road_node_type,
                "highway_type": highway_type,
                "crossing_type": crossing_type,
                "traffic_signal": traffic_signal,
                "junction_type": junction_type,
                "importance": importance,
                "name": tags.get("name", "N/A"),
                "surface": tags.get("surface", "N/A"),
                "lanes": tags.get("lanes", "N/A"),
                "maxspeed": tags.get("maxspeed", "N/A"),
                "timestamp": node.get("timestamp", "N/A"),
                "user": node.get("user", "N/A")
            })

        # =========================
        # EMPTY CHECK
        # =========================
        if not data:
            print("No road infrastructure data found.")
            return None

        # =========================
        # DATAFRAME CREATION
        # =========================
        df = pd.DataFrame(data)

        # Remove duplicates
        df.drop_duplicates(subset=["node_id"], inplace=True)

        # =========================
        # COLUMN ORDER
        # =========================
        df = df[
            [
                "node_id",
                "latitude",
                "longitude",
                "road_node_type",
                "highway_type",
                "crossing_type",
                "traffic_signal",
                "junction_type",
                "importance",
                "name",
                "surface",
                "lanes",
                "maxspeed",
                "timestamp",
                "user"
            ]
        ]

        print(f"Extracted {len(df)} road infrastructure records")

        return df
    # ================= SAVE =================
    # ================= SAVE =================
    def save_to_excel(self, df, file_type):
        try:
            # Ensure output directory exists
            self.output_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{file_type}_infrastructure.xlsx"
            filepath = self.output_dir / filename

            print(f"\nDEBUG: Attempting to save Excel file...")
            print(f"DEBUG: Save path -> {filepath}")

            # Explicit engine avoids silent failure
            df.to_excel(filepath, index=False, engine="openpyxl")

            # Verify file exists
            if filepath.exists():
                print("\nExcel saved successfully!")
                print(f"Location: {filepath}")
                print(f"Rows: {len(df)}")

                return filepath  # IMPORTANT

            else:
                print("ERROR: File save attempted but file does not exist.")
                return None

        except Exception as e:
            print(f"Error saving Excel: {e}")
            return None 


def main():
    parser = OSMParser()
    parser.run()


if __name__ == "__main__":
    main()