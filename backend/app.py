# =========================
# FULLY UPDATED app.py
# XML Parsing + Excel Saving
# + AUTO ROAD GRAPH GENERATION
# + AUTO WATER GRAPH GENERATION
# + AUTO POWER GRAPH GENERATION
# + AUTO VISUALIZATION
# + AUTO GRAPH STORAGE
# =========================

from flask import Flask, request, jsonify, send_from_directory, render_template
import networkx as nx
import os
import json
from pathlib import Path

from ingestion.xml_parser import OSMParser

from graph.road import RoadGraphBuilder
from graph.water import WaterGraphBuilder
from graph.power import PowerGraphBuilder
from graph.cascade import RoadCascadeSimulator
from hotspot_simulator import HotspotSimulator, HOTSPOTS

import traceback

app = Flask(__name__, static_folder='data')

# =========================
# PROJECT PATHS
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]

UPLOAD_FOLDER = BASE_DIR / "data" / "raw"
PROCESSED_FOLDER = BASE_DIR / "data" / "processed"
GRAPH_FOLDER = BASE_DIR / "data" / "graphs"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)
GRAPH_FOLDER.mkdir(parents=True, exist_ok=True)


# =========================
# FILE TYPE CHOICE SYSTEM
# =========================
def get_file_type(choice):

    switch = {
        "1": "power",
        "2": "water",
        "3": "road"
    }

    return switch.get(choice, None)


# =========================
# XML PROCESSING ROUTE
# =========================
@app.route("/upload-xml", methods=["POST"])
def upload_xml():

    try:

        # =========================
        # FILE VALIDATION
        # =========================
        if "file" not in request.files:

            return jsonify({
                "error": "No file uploaded"
            }), 400

        file = request.files["file"]

        if file.filename == "":

            return jsonify({
                "error": "Empty filename"
            }), 400

        # =========================
        # CHOICE VALIDATION
        # =========================
        file_choice = request.form.get("choice")

        if not file_choice:

            return jsonify({
                "error": "No infrastructure type selected"
            }), 400

        file_type = get_file_type(file_choice)

        if not file_type:

            return jsonify({
                "error": "Invalid choice"
            }), 400

        # =========================
        # SAVE RAW XML
        # =========================
        file_path = UPLOAD_FOLDER / file.filename

        file.save(file_path)

        print(f"\nUploaded XML saved at: {file_path}")
        print(f"Selected type: {file_type}")

        # =========================
        # PARSER INIT
        # =========================
        parser = OSMParser()

        # =========================
        # PARSE INFRASTRUCTURE
        # =========================
        if file_type == "power":

            df = parser.parse_power_osm(
                str(file_path)
            )

        elif file_type == "water":

            df = parser.parse_water_osm(
                str(file_path)
            )

        elif file_type == "road":

            df = parser.parse_road_osm(
                str(file_path)
            )

        else:

            return jsonify({
                "error": "Unsupported infrastructure type"
            }), 400

        # =========================
        # DATA VALIDATION
        # =========================
        if df is None or df.empty:

            return jsonify({
                "error": f"No {file_type} data extracted"
            }), 404

        print(f"Rows extracted: {len(df)}")

        # =========================
        # SAVE EXCEL
        # =========================
        excel_path = parser.save_to_excel(
            df,
            file_type
        )

        if excel_path is None:

            return jsonify({
                "error": "Excel file saving failed",
                "details": "save_to_excel returned None"
            }), 500

        if not Path(excel_path).exists():

            return jsonify({
                "error": "Excel file not found after saving",
                "details": str(excel_path)
            }), 500

        print(f"Excel successfully saved at: {excel_path}")

        # =========================
        # GRAPH AUTO GENERATION
        # =========================
        graph_outputs = {}

        # =====================================
        # POWER GRAPH
        # =====================================
        if file_type == "power":

            print("\n===== STARTING POWER GRAPH GENERATION =====")

            try:

                graph_builder = PowerGraphBuilder()

                graph_result = (
                    graph_builder.build_graph_from_xlsx(
                        str(excel_path)
                    )
                )

                if graph_result:

                    graph_file = graph_builder.save_graph(
                        graph_result
                    )

                    html_map = (
                        graph_builder
                        .visualize_interactive_map(
                            graph_result
                        )
                    )

                    png_graph = (
                        graph_builder
                        .visualize_static_graph(
                            graph_result
                        )
                    )

                    graph_outputs = {
                        "graphml_output": str(graph_file),
                        "interactive_map": str(html_map),
                        "static_graph": str(png_graph),
                        "nodes": graph_result.number_of_nodes(),
                        "edges": graph_result.number_of_edges()
                    }

                    print(
                        "Power graph successfully generated."
                    )

                else:

                    print(
                        "WARNING: Power graph builder returned None"
                    )

            except Exception as graph_error:

                print("\n===== POWER GRAPH ERROR =====")

                traceback.print_exc()

                graph_outputs = {
                    "graph_error": str(graph_error)
                }

        # =====================================
        # ROAD GRAPH
        # =====================================
        elif file_type == "road":

            print("\n===== STARTING ROAD GRAPH GENERATION =====")

            try:

                graph_builder = RoadGraphBuilder()

                graph_result = (
                    graph_builder
                    .build_graph_from_dataframe(df)
                )

                if graph_result:

                    graph_outputs = {
                        "graphml_output": (
                            graph_result.get("graphml")
                        ),

                        "interactive_map": (
                            graph_result.get(
                                "interactive_map"
                            )
                        ),

                        "static_graph": (
                            graph_result.get(
                                "static_graph"
                            )
                        ),

                        "nodes": (
                            graph_result.get("nodes")
                        ),

                        "edges": (
                            graph_result.get("edges")
                        )
                    }

                    print(
                        "Road graph successfully generated."
                    )

                else:

                    print(
                        "WARNING: Road graph builder returned None"
                    )

            except Exception as graph_error:

                print("\n===== ROAD GRAPH ERROR =====")

                traceback.print_exc()

                graph_outputs = {
                    "graph_error": str(graph_error)
                }

        # =====================================
        # WATER GRAPH
        # =====================================
        elif file_type == "water":

            print("\n===== STARTING WATER GRAPH GENERATION =====")

            try:

                graph_builder = WaterGraphBuilder()

                graph_result = (
                    graph_builder
                    .build_graph_from_dataframe(df)
                )

                if graph_result:

                    graph_outputs = {
                        "graphml_output": (
                            graph_result.get("graphml")
                        ),

                        "interactive_map": (
                            graph_result.get(
                                "interactive_map"
                            )
                        ),

                        "static_graph": (
                            graph_result.get(
                                "static_graph"
                            )
                        ),

                        "nodes": (
                            graph_result.get("nodes")
                        ),

                        "edges": (
                            graph_result.get("edges")
                        )
                    }

                    print(
                        "Water graph successfully generated."
                    )

                else:

                    print(
                        "WARNING: Water graph builder returned None"
                    )

            except Exception as graph_error:

                print("\n===== WATER GRAPH ERROR =====")

                traceback.print_exc()

                graph_outputs = {
                    "graph_error": str(graph_error)
                }

        # =========================
        # FINAL RESPONSE
        # =========================
        response = {
            "message": (
                f"{file_type.capitalize()} "
                f"XML processed successfully"
            ),

            "selected_choice": file_choice,

            "file_type": file_type,

            "rows_extracted": len(df),

            "excel_output": str(excel_path),

            "uploaded_file": str(file_path)
        }

        response.update(graph_outputs)

        return jsonify(response), 200

    except Exception as e:

        print("\n===== FULL XML ERROR TRACE =====")

        traceback.print_exc()

        return jsonify({
            "error": "Processing failed",
            "details": str(e)
        }), 500


# =========================
# DIRECT ROAD GEOJSON ROUTE
# =========================
@app.route("/upload-road-geojson", methods=["POST"])
def upload_road_geojson():

    try:

        if "file" not in request.files:

            return jsonify({
                "error": "No GeoJSON file uploaded"
            }), 400

        file = request.files["file"]

        if file.filename == "":

            return jsonify({
                "error": "Empty filename"
            }), 400

        geojson_path = UPLOAD_FOLDER / file.filename

        file.save(geojson_path)

        print(
            f"\nUploaded Road GeoJSON saved at: "
            f"{geojson_path}"
        )

        graph_builder = RoadGraphBuilder()

        graph_result = (
            graph_builder.process_road_network(
                str(geojson_path)
            )
        )

        if graph_result is None:

            return jsonify({
                "error": "Road graph generation failed"
            }), 500

        return jsonify({
            "message": (
                "Road graph created successfully"
            ),

            "geojson_input": str(geojson_path),

            "graphml_output": (
                graph_result["graphml"]
            ),

            "interactive_map": (
                graph_result["interactive_map"]
            ),

            "static_graph": (
                graph_result["static_graph"]
            ),

            "nodes": graph_result["nodes"],

            "edges": graph_result["edges"]
        }), 200

    except Exception as e:

        print(
            "\n===== FULL ROAD GRAPH ERROR TRACE ====="
        )

        traceback.print_exc()

        return jsonify({
            "error": "Road graph processing failed",
            "details": str(e)
        }), 500


# =========================
# DIRECT WATER GEOJSON ROUTE
# =========================
@app.route("/upload-water-geojson", methods=["POST"])
def upload_water_geojson():

    try:

        if "file" not in request.files:

            return jsonify({
                "error": "No GeoJSON file uploaded"
            }), 400

        file = request.files["file"]

        if file.filename == "":

            return jsonify({
                "error": "Empty filename"
            }), 400

        geojson_path = UPLOAD_FOLDER / file.filename

        file.save(geojson_path)

        print(
            f"\nUploaded Water GeoJSON saved at: "
            f"{geojson_path}"
        )

        graph_builder = WaterGraphBuilder()

        graph_result = (
            graph_builder.process_water_network(
                str(geojson_path)
            )
        )

        if graph_result is None:

            return jsonify({
                "error": "Water graph generation failed"
            }), 500

        return jsonify({
            "message": (
                "Water graph created successfully"
            ),

            "geojson_input": str(geojson_path),

            "graphml_output": (
                graph_result["graphml"]
            ),

            "interactive_map": (
                graph_result["interactive_map"]
            ),

            "static_graph": (
                graph_result["static_graph"]
            ),

            "nodes": graph_result["nodes"],

            "edges": graph_result["edges"]
        }), 200

    except Exception as e:

        print(
            "\n===== FULL WATER GRAPH ERROR TRACE ====="
        )

        traceback.print_exc()

        return jsonify({
            "error": "Water graph processing failed",
            "details": str(e)
        }), 500


# =========================
# DIRECT POWER GEOJSON ROUTE
# =========================
@app.route("/upload-power-geojson", methods=["POST"])
def upload_power_geojson():

    try:

        if "file" not in request.files:

            return jsonify({
                "error": "No GeoJSON file uploaded"
            }), 400

        file = request.files["file"]

        if file.filename == "":

            return jsonify({
                "error": "Empty filename"
            }), 400

        geojson_path = UPLOAD_FOLDER / file.filename

        file.save(geojson_path)

        print(
            f"\nUploaded Power GeoJSON saved at: "
            f"{geojson_path}"
        )

        graph_builder = PowerGraphBuilder()

        graph_result = (
            graph_builder.process_power_network(
                str(geojson_path),
                "geojson"
            )
        )

        if graph_result is None:

            return jsonify({
                "error": "Power graph generation failed"
            }), 500

        return jsonify({
            "message": (
                "Power graph created successfully"
            ),

            "geojson_input": str(geojson_path),

            "graphml_output": (
                graph_result["graphml"]
            ),

            "interactive_map": (
                graph_result["interactive_map"]
            ),

            "static_graph": (
                graph_result["static_graph"]
            ),

            "nodes": graph_result["nodes"],

            "edges": graph_result["edges"]
        }), 200

    except Exception as e:

        print(
            "\n===== FULL POWER GRAPH ERROR TRACE ====="
        )

        traceback.print_exc()

        return jsonify({
            "error": "Power graph processing failed",
            "details": str(e)
        }), 500


# =========================
# ROAD SIMULATION ROUTES
# =========================
@app.route("/simulate/road-blockage", methods=["POST"])
def simulate_road_blockage():
    try:
        data = request.json
        graph_path = GRAPH_FOLDER / "road_network.graphml"
        if not graph_path.exists():
            return jsonify({"error": "Road graph not found. Please upload road data first."}), 404
        
        G = nx.read_graphml(graph_path)
        simulator = RoadCascadeSimulator(G)
        
        target = data.get("target") # Can be node ID or [u, v] list
        if isinstance(target, list): target = tuple(target)
        cause = data.get("cause", "unknown")
        
        results = simulator.simulate_scenario("road_blockage", target, cause)
        # Convert graph to serializable form or remove it from response
        results.pop("graph", None)
        return jsonify(results), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/simulate/signal-failure", methods=["POST"])
def simulate_signal_failure():
    try:
        data = request.json
        graph_path = GRAPH_FOLDER / "road_network.graphml"
        if not graph_path.exists():
            return jsonify({"error": "Road graph not found."}), 404
        
        G = nx.read_graphml(graph_path)
        simulator = RoadCascadeSimulator(G)
        
        target = data.get("target")
        cause = data.get("cause", "power_outage")
        
        results = simulator.simulate_scenario("signal_failure", target, cause)
        results.pop("graph", None)
        return jsonify(results), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/simulate/flyover-closure", methods=["POST"])
def simulate_flyover_closure():
    try:
        data = request.json
        graph_path = GRAPH_FOLDER / "road_network.graphml"
        if not graph_path.exists():
            return jsonify({"error": "Road graph not found."}), 404
        
        G = nx.read_graphml(graph_path)
        simulator = RoadCascadeSimulator(G)
        
        target = data.get("target")
        if isinstance(target, list): target = tuple(target)
        cause = data.get("cause", "maintenance")
        
        results = simulator.simulate_scenario("flyover_closure", target, cause)
        results.pop("graph", None)
        return jsonify(results), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/simulate-hotspot", methods=["POST"])
def api_simulate_hotspot():
    try:
        data = request.json
        hotspot_id = data.get("hotspot_id")
        if not hotspot_id:
            return jsonify({"error": "Missing hotspot_id"}), 400
        
        sim = HotspotSimulator()
        results = sim.run_hotspot(hotspot_id)
        return jsonify(results), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/hotspots", methods=["GET"])
def api_get_hotspots():
    return jsonify(HOTSPOTS), 200

@app.route("/maps/<path:filename>")
def serve_graph_files(filename):
    return send_from_directory(GRAPH_FOLDER, filename)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# =========================
# HEALTH CHECK
# =========================
@app.route("/health", methods=["GET"])
def home():

    return jsonify({

        "message": (
            "OSM XML + Multi-Infrastructure "
            "Graph API Running"
        ),

        "available_routes": {

            "/upload-xml": {
                "1": "Power XML + Graph",
                "2": "Water XML + Graph",
                "3": "Road XML + Graph"
            },

            "/upload-road-geojson":
                "Road GeoJSON → Graph",

            "/upload-water-geojson":
                "Water GeoJSON → Graph",

            "/upload-power-geojson":
                "Power GeoJSON → Graph"
        },

        "output_locations": {

            "raw_files":
                str(UPLOAD_FOLDER),

            "excel_files":
                str(PROCESSED_FOLDER),

            "graph_files":
                str(GRAPH_FOLDER)
        }
    })


# =========================
# MAIN
# =========================
if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )