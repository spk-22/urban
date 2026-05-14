# ============================================================
# ADVANCED URBAN SHOCKWAVE ENGINE
# FULLY UPGRADED app.py
# ============================================================

from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
    render_template
)

import networkx as nx
import traceback
import json
import os
from pathlib import Path
from datetime import datetime

# ============================================================
# INTERNAL IMPORTS
# ============================================================

from ingestion.xml_parser import OSMParser

from graph.road import RoadGraphBuilder
from graph.water import WaterGraphBuilder
from graph.power import PowerGraphBuilder

from graph.cascade import RoadCascadeSimulator
from graph.cascade_visualizer import CascadeVisualizer

from hotspot_simulator import (
    HotspotSimulator,
    HOTSPOTS
)

# ============================================================
# FLASK INIT
# ============================================================

app = Flask(
    __name__,
    static_folder="data",
    template_folder="templates"
)

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

UPLOAD_FOLDER = BASE_DIR / "data" / "raw"
PROCESSED_FOLDER = BASE_DIR / "data" / "processed"
GRAPH_FOLDER = BASE_DIR / "data" / "graphs"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)
GRAPH_FOLDER.mkdir(parents=True, exist_ok=True)

# ============================================================
# GLOBAL CACHE
# ============================================================

LATEST_TIMELINE = []
LATEST_ANALYTICS = {}
LATEST_GRAVITY = {}
LATEST_SIGNAL_HEALTH = {}

# ============================================================
# FILE TYPE SYSTEM
# ============================================================

def get_file_type(choice):

    switch = {
        "1": "power",
        "2": "water",
        "3": "road"
    }

    return switch.get(choice)

# ============================================================
# GRAPH LOADER
# ============================================================

def load_road_graph():

    graph_path = GRAPH_FOLDER / "road_network.graphml"

    if not graph_path.exists():
        raise FileNotFoundError(
            "road_network.graphml not found"
        )

    G = nx.read_graphml(graph_path)

    preprocess_graph(G)

    return G

# ============================================================
# GRAPH PREPROCESSING
# ============================================================

def preprocess_graph(G):

    print("\n===== PREPROCESSING ROAD NETWORK =====")

    try:

        centrality = nx.betweenness_centrality(
            G,
            k=min(100, len(G.nodes)),
            normalized=True
        )

    except:
        centrality = {}

    for node in G.nodes():

        G.nodes[node]["centrality"] = (
            centrality.get(node, 0)
        )

        degree = G.degree(node)

        G.nodes[node]["traffic_gravity"] = round(
            (degree * 0.4)
            +
            (centrality.get(node, 0) * 10),
            4
        )

        node_type = str(
            G.nodes[node].get("node_type", "")
        ).lower()

        G.nodes[node]["is_signal"] = (
            "signal" in node_type
        )

        G.nodes[node]["signal_criticality"] = round(
            G.nodes[node]["traffic_gravity"]
            *
            (
                2.5
                if G.nodes[node]["is_signal"]
                else 1.0
            ),
            4
        )

    for u, v, data in G.edges(data=True):

        rc = str(
            data.get(
                "road_class",
                data.get("highway", "residential")
            )
        ).lower()

        if rc in [
            "motorway",
            "trunk",
            "primary"
        ]:

            hierarchy = "arterial"
            absorption = 3.5

        elif rc in [
            "secondary",
            "tertiary"
        ]:

            hierarchy = "secondary"
            absorption = 2.0

        else:

            hierarchy = "local"
            absorption = 0.8

        data["hierarchy"] = hierarchy
        data["reroute_absorption"] = absorption

        data["gravity_score"] = round(
            (
                G.nodes[u].get("traffic_gravity", 1)
                +
                G.nodes[v].get("traffic_gravity", 1)
            )
            / 2,
            4
        )

        data["shockwave_multiplier"] = round(
            absorption
            *
            data["gravity_score"],
            4
        )

    print("Graph preprocessing complete.")

# ============================================================
# XML UPLOAD
# ============================================================

@app.route("/upload-xml", methods=["POST"])
def upload_xml():

    try:

        if "file" not in request.files:

            return jsonify({
                "error": "No file uploaded"
            }), 400

        file = request.files["file"]

        if file.filename == "":

            return jsonify({
                "error": "Empty filename"
            }), 400

        choice = request.form.get("choice")

        file_type = get_file_type(choice)

        if not file_type:

            return jsonify({
                "error": "Invalid infrastructure choice"
            }), 400

        save_path = UPLOAD_FOLDER / file.filename

        file.save(save_path)

        parser = OSMParser()

        # ====================================================
        # PARSE
        # ====================================================

        if file_type == "road":

            df = parser.parse_road_osm(
                str(save_path)
            )

        elif file_type == "water":

            df = parser.parse_water_osm(
                str(save_path)
            )

        else:

            df = parser.parse_power_osm(
                str(save_path)
            )

        if df is None or df.empty:

            return jsonify({
                "error": "No data extracted"
            }), 500

        excel_path = parser.save_to_excel(
            df,
            file_type
        )

        graph_outputs = {}

        # ====================================================
        # ROAD
        # ====================================================

        if file_type == "road":

            builder = RoadGraphBuilder()

            graph_outputs = (
                builder.build_graph_from_dataframe(df)
            )

        # ====================================================
        # WATER
        # ====================================================

        elif file_type == "water":

            builder = WaterGraphBuilder()

            graph_outputs = (
                builder.build_graph_from_dataframe(df)
            )

        # ====================================================
        # POWER
        # ====================================================

        else:

            builder = PowerGraphBuilder()

            graph_outputs = (
                builder.build_graph_from_xlsx(
                    str(excel_path)
                )
            )

        return jsonify({

            "message":
                f"{file_type} network processed",

            "rows_extracted":
                len(df),

            "excel_output":
                str(excel_path),

            "graph_outputs":
                graph_outputs
        })

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500

# ============================================================
# STOCHASTIC SIMULATION API
# ============================================================

@app.route(
    "/api/stochastic-simulate",
    methods=["POST"]
)
def stochastic_simulation():

    global LATEST_TIMELINE
    global LATEST_ANALYTICS
    global LATEST_GRAVITY
    global LATEST_SIGNAL_HEALTH

    try:

        payload = request.json

        scenario_type = payload.get(
            "scenario_type",
            "road_blockage"
        )

        target = payload.get("target")

        cause = payload.get(
            "cause",
            "unknown"
        )

        if isinstance(target, list):
            target = tuple(target)

        G = load_road_graph()

        simulator = RoadCascadeSimulator(G)

        results = simulator.simulate_scenario(
            scenario_type=scenario_type,
            target_id=target,
            cause=cause
        )

        graph = results.get("graph")

        # ====================================================
        # VISUALIZATION
        # ====================================================

        visualizer = CascadeVisualizer()

        filename = (
            f"shockwave_"
            f"{datetime.now().strftime('%H%M%S')}.html"
        )

        map_path = visualizer.create_cascade_map(
            graph,
            title="Urban Shockwave Simulation",
            filename=filename
        )

        # ====================================================
        # STORE GLOBALS
        # ====================================================

        LATEST_TIMELINE = (
            results.get("cascade", {})
            .get("cascade_log", [])
        )

        LATEST_ANALYTICS = {

            "97th_percentile_delay":
                results.get(
                    "risk_97_delay",
                    0
                ),

            "97th_percentile_load":
                results.get(
                    "risk_97_load",
                    0
                ),

            "shockwave_radius":
                results.get(
                    "shockwave_radius",
                    0
                ),

            "spillback_probability":
                results.get(
                    "spillback_probability",
                    0
                ),

            "reroute_entropy":
                results.get(
                    "reroute_entropy",
                    0
                )
        }

        gravity_corridors = []

        for u, v, d in graph.edges(data=True):

            gravity_corridors.append({

                "u": u,
                "v": v,

                "gravity_score":
                    d.get(
                        "gravity_score",
                        0
                    ),

                "hierarchy":
                    d.get(
                        "hierarchy",
                        "local"
                    ),

                "load_ratio":
                    d.get(
                        "load_ratio",
                        0
                    )
            })

        gravity_corridors.sort(
            key=lambda x: x["gravity_score"],
            reverse=True
        )

        LATEST_GRAVITY = {
            "top_corridors":
                gravity_corridors[:25]
        }

        signals = []

        for node, data in graph.nodes(data=True):

            if data.get("is_signal"):

                signals.append({

                    "node": node,

                    "queue_pressure":
                        data.get(
                            "queue_pressure",
                            0
                        ),

                    "signal_stability":
                        data.get(
                            "signal_stability",
                            1
                        ),

                    "spillback_probability":
                        data.get(
                            "spillback_probability",
                            0
                        ),

                    "status":
                        data.get(
                            "status",
                            "normal"
                        )
                })

        LATEST_SIGNAL_HEALTH = {
            "signals": signals
        }

        results.pop("graph", None)

        return jsonify({

            "message":
                "Advanced stochastic simulation complete",

            "map_url":
                f"/maps/{Path(map_path).name}",

            "results":
                results,

            "analytics":
                LATEST_ANALYTICS
        })

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500

# ============================================================
# SIGNAL HEALTH API
# ============================================================

@app.route(
    "/api/signal-health",
    methods=["GET"]
)
def signal_health():

    return jsonify(
        LATEST_SIGNAL_HEALTH
    )

# ============================================================
# TRAFFIC GRAVITY API
# ============================================================

@app.route(
    "/api/traffic-gravity",
    methods=["GET"]
)
def traffic_gravity():

    return jsonify(
        LATEST_GRAVITY
    )

# ============================================================
# CASCADE TIMELINE API
# ============================================================

@app.route(
    "/api/cascade-timeline",
    methods=["GET"]
)
def cascade_timeline():

    return jsonify({

        "timeline":
            LATEST_TIMELINE
    })

# ============================================================
# HOTSPOT SIMULATION
# ============================================================

@app.route(
    "/api/simulate-hotspot",
    methods=["POST"]
)
def simulate_hotspot():

    try:

        data = request.json

        hotspot_id = data.get(
            "hotspot_id"
        )

        if not hotspot_id:

            return jsonify({
                "error":
                    "Missing hotspot_id"
            }), 400

        simulator = HotspotSimulator()

        results = simulator.run_hotspot(
            hotspot_id
        )

        return jsonify(results)

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500

# ============================================================
# HOTSPOTS
# ============================================================

@app.route(
    "/api/hotspots",
    methods=["GET"]
)
def get_hotspots():

    return jsonify(HOTSPOTS)

# ============================================================
# MAP SERVING
# ============================================================

@app.route("/maps/<path:filename>")
def serve_map(filename):

    return send_from_directory(
        GRAPH_FOLDER,
        filename
    )

# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )

# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return jsonify({

        "status":
            "Urban Shockwave Engine Running",

        "apis": [

            "/upload-xml",

            "/api/stochastic-simulate",

            "/api/signal-health",

            "/api/traffic-gravity",

            "/api/cascade-timeline",

            "/api/hotspots"
        ]
    })

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )