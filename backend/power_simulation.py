import os
import json
import traceback
import math
from pathlib import Path
import networkx as nx
import folium
from flask import Flask, request, jsonify, send_from_directory, render_template_string

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parents[1]
GRAPH_PATH = BASE_DIR / "data" / "graphs" / "power_network.graphml"
OUT_DIR = BASE_DIR / "data" / "graphs" / "power"
OUT_DIR.mkdir(parents=True, exist_ok=True)

class PowerSimulator:
    def __init__(self, graph_path):
        self.original_G = nx.read_graphml(str(graph_path))
        self.G = None

    def prepare_graph(self):
        self.G = self.original_G.copy()
        
        try:
            betweenness = nx.betweenness_centrality(self.G)
        except Exception:
            betweenness = {n: 0.0 for n in self.G.nodes()}

        for n, data in self.G.nodes(data=True):
            infr_type = str(data.get("infrastructure", "substation")).lower()
            
            if infr_type == 'power plant':
                cap = 500.0 # MW
                volt_weight = 1.0
            else:
                cap = 100.0 # MW
                volt_weight = 0.5
                
            load = cap * 0.85 # baseline 85% load
            
            data["capacity"] = cap
            data["current_load"] = load
            data["load_factor"] = round(load / cap, 3)
            data["status"] = "normal"
            data["betweenness"] = betweenness.get(n, 0.0)
            data["voltage_weight"] = volt_weight
            
            # Criticality Score
            data["critical_score"] = round((data["betweenness"] * 0.5) + (volt_weight * 0.3) + (data["load_factor"] * 0.2), 4)

        for u, v, data in self.G.edges(data=True):
            data["status"] = "active"
            
        return self.G

    def run_cascade(self, initial_node):
        if initial_node not in self.G:
            return {"error": "Node not found"}

        G_active = self.G.copy()
        failed_nodes = []
        queue = [initial_node]
        
        while queue:
            current = queue.pop(0)
            if self.G.nodes[current].get("status") == "failed":
                continue
                
            lost_load = self.G.nodes[current].get("current_load", 0)
            self.G.nodes[current]["status"] = "failed"
            self.G.nodes[current]["current_load"] = 0
            failed_nodes.append(current)
            
            # Identify active neighbors before removing
            active_neighbors = [nbr for nbr in G_active.neighbors(current)]
            
            if active_neighbors:
                share = lost_load / len(active_neighbors)
                for nbr in active_neighbors:
                    nbr_data = self.G.nodes[nbr]
                    if nbr_data.get("status") != "failed":
                        nbr_data["current_load"] += share
                        nbr_data["load_factor"] = round(nbr_data["current_load"] / nbr_data["capacity"], 3)
                        
                        if nbr_data["load_factor"] > 1.0 and nbr not in queue:
                            queue.append(nbr)
                            
            if current in G_active:
                G_active.remove_node(current)

        # Update remaining node statuses
        for n, data in self.G.nodes(data=True):
            if data.get("status") != "failed":
                lf = data.get("load_factor", 0)
                if lf >= 1.0:
                    data["status"] = "failed"
                elif lf >= 0.8:
                    data["status"] = "overloaded"

        # Islanding Detection & Blackouts
        islands = list(nx.connected_components(G_active))
        blackout_regions = []
        island_list = []
        
        for island in islands:
            island_nodes = list(island)
            island_list.append(island_nodes)
            
            has_source = False
            for n in island_nodes:
                if self.G.nodes[n].get("infrastructure", "").lower() == "power plant":
                    has_source = True
                    break
            
            if not has_source:
                blackout_regions.append(island_nodes)
                for n in island_nodes:
                    self.G.nodes[n]["status"] = "blackout"

        return {
            "initial_failure": initial_node,
            "failed_nodes": failed_nodes,
            "islands": island_list,
            "blackout_regions": blackout_regions
        }

    def generate_outputs(self, report_data):
        # 1. Save GraphML
        nx.write_graphml(self.G, str(OUT_DIR / "power_cascade.graphml"))
        
        # 2. Save JSON Report
        with open(OUT_DIR / "power_cascade_report.json", "w") as f:
            json.dump(report_data, f, indent=2)
            
        # 3. Create Map
        lats = [float(d.get("latitude", 0)) for _, d in self.G.nodes(data=True) if "latitude" in d]
        lons = [float(d.get("longitude", 0)) for _, d in self.G.nodes(data=True) if "longitude" in d]
        
        if lats and lons:
            center = [sum(lats)/len(lats), sum(lons)/len(lons)]
        else:
            center = [12.9716, 77.5946] # Bengaluru default
            
        m = folium.Map(location=center, zoom_start=11, tiles="cartodbpositron")
        
        # Draw Edges
        for u, v, data in self.G.edges(data=True):
            status_u = self.G.nodes[u].get("status")
            status_v = self.G.nodes[v].get("status")
            
            color = "#555555"
            weight = 1
            if status_u == "failed" or status_v == "failed":
                color = "#ff0000"
                weight = 2
            elif status_u == "blackout" and status_v == "blackout":
                color = "#000000"
                
            try:
                p1 = [float(self.G.nodes[u]["latitude"]), float(self.G.nodes[u]["longitude"])]
                p2 = [float(self.G.nodes[v]["latitude"]), float(self.G.nodes[v]["longitude"])]
                folium.PolyLine(locations=[p1, p2], color=color, weight=weight, opacity=0.6).add_to(m)
            except:
                continue

        # Draw Nodes
        for node, data in self.G.nodes(data=True):
            status = data.get("status", "normal")
            
            if status == "normal": color = "#2ecc71" # Green
            elif status == "overloaded": color = "#f1c40f" # Yellow
            elif status == "failed": color = "#e74c3c" # Red
            elif status == "blackout": color = "#000000" # Black
            else: color = "#2ecc71"
            
            radius = 8 if status in ["failed", "blackout"] else 5
            if node == report_data.get("initial_failure"):
                color = "#ffffff" # White for epicenter
                radius = 12
                
            popup = f"""
                <b>Node:</b> {data.get('name', node)}<br>
                <b>Type:</b> {data.get('infrastructure', 'N/A')}<br>
                <b>Status:</b> {status.upper()}<br>
                <b>Load Factor:</b> {data.get('load_factor', 0)}<br>
                <b>Critical Score:</b> {data.get('critical_score', 0)}
            """
            
            try:
                folium.CircleMarker(
                    location=[float(data["latitude"]), float(data["longitude"])],
                    radius=radius,
                    color=color,
                    fill=True,
                    fill_opacity=0.9,
                    popup=folium.Popup(popup, max_width=250)
                ).add_to(m)
            except:
                continue

        map_path = str(OUT_DIR / "power_cascade_map.html")
        m.save(map_path)
        
        report_data["files"] = [
            "/power_graphs/power_cascade.graphml",
            "/power_graphs/power_cascade_map.html",
            "/power_graphs/power_cascade_report.json"
        ]
        return report_data


@app.route("/simulate/power-cascade", methods=["POST"])
def api_simulate_power():
    try:
        data = request.json
        node_id = data.get("node_id")
        
        if not node_id:
            return jsonify({"error": "Missing node_id"}), 400
            
        if not GRAPH_PATH.exists():
            return jsonify({"error": "Graph file not found."}), 404
            
        sim = PowerSimulator(GRAPH_PATH)
        sim.prepare_graph()
        
        report = sim.run_cascade(node_id)
        if "error" in report:
            return jsonify(report), 400
            
        final_report = sim.generate_outputs(report)
        return jsonify(final_report), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/power_graphs/<path:filename>")
def serve_graphs(filename):
    return send_from_directory(OUT_DIR, filename)

@app.route("/power/ui")
def ui():
    # Load graph nodes for dropdown
    sim = PowerSimulator(GRAPH_PATH)
    sim.prepare_graph()
    
    # Get top 20 most critical nodes
    nodes = []
    for n, d in sim.G.nodes(data=True):
        nodes.append({"id": n, "name": d.get("name", n), "score": d.get("critical_score", 0)})
        
    nodes = sorted(nodes, key=lambda x: x["score"], reverse=True)[:20]
    
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Power Grid Cascade Simulator</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-900 text-white min-h-screen p-8 font-sans">
        <h1 class="text-3xl font-bold mb-6">⚡ Power Grid Cascade Simulator</h1>
        
        <div class="flex gap-4 mb-8">
            <select id="node-select" class="bg-slate-800 border border-slate-700 rounded p-2 text-white">
                {% for node in nodes %}
                <option value="{{ node.id }}">{{ node.name }} (Score: {{ node.score }})</option>
                {% endfor %}
            </select>
            <button onclick="simulate()" class="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded font-bold">Simulate Failure</button>
        </div>
        
        <div class="grid grid-cols-4 gap-4 mb-4 text-center">
            <div class="bg-slate-800 p-4 rounded"><p class="text-xs text-slate-400">Failed Nodes</p><h2 id="s-failed" class="text-2xl text-red-500">-</h2></div>
            <div class="bg-slate-800 p-4 rounded"><p class="text-xs text-slate-400">Blackout Regions</p><h2 id="s-blackouts" class="text-2xl text-gray-500">-</h2></div>
            <div class="bg-slate-800 p-4 rounded"><p class="text-xs text-slate-400">Stable Islands</p><h2 id="s-islands" class="text-2xl text-blue-400">-</h2></div>
        </div>
        
        <iframe id="map-frame" class="w-full h-[600px] border border-slate-700 rounded bg-slate-800 hidden"></iframe>
        
        <script>
            async function simulate() {
                const nodeId = document.getElementById('node-select').value;
                const frame = document.getElementById('map-frame');
                frame.classList.add('hidden');
                
                const res = await fetch('/simulate/power-cascade', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({node_id: nodeId})
                });
                const data = await res.json();
                
                if (data.error) { alert(data.error); return; }
                
                document.getElementById('s-failed').innerText = data.failed_nodes.length;
                document.getElementById('s-blackouts').innerText = data.blackout_regions.length;
                
                // Subtract blackouts from total islands to get "stable" islands
                const stable = data.islands.length - data.blackout_regions.length;
                document.getElementById('s-islands').innerText = stable;
                
                frame.src = data.files[1];
                frame.classList.remove('hidden');
            }
        </script>
    </body>
    </html>
    """
    from flask import render_template_string
    return render_template_string(html, nodes=nodes)

if __name__ == "__main__":
    app.run(port=5002, debug=True)
