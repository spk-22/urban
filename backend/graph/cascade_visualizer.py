"""
cascade_visualizer.py
=========================================
INTERACTIVE CASCADE VISUALIZER
Uses Folium to create colour-coded maps showing
congestion levels and failure points.
=========================================
"""

import folium
from branca.colormap import LinearColormap
from pathlib import Path

class CascadeVisualizer:
    def __init__(self, output_dir=None):
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(__file__).resolve().parents[1] / "data" / "graphs"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_color_node(self, load_ratio):
        if load_ratio < 0.6: return "green"
        if load_ratio < 0.85: return "yellow"
        if load_ratio < 0.95: return "orange"
        if load_ratio < 1.0: return "#ff0000" # Bright Red
        return "black"

    def get_color_edge(self, load_ratio):
        if load_ratio < 0.6: return "#2ecc71" # Green
        if load_ratio < 0.85: return "#f1c40f" # Yellow
        if load_ratio < 0.95: return "#e67e22" # Orange
        if load_ratio < 1.0: return "#ff0000" # Bright Red
        return "#000000" # Black

    def create_cascade_map(self, G, title="Road Cascade Analysis", filename="cascade_map.html"):
        # Calculate center
        lats = [d["latitude"] for _, d in G.nodes(data=True)]
        lons = [d["longitude"] for _, d in G.nodes(data=True)]
        
        center = [sum(lats)/len(lats), sum(lons)/len(lons)]
        m = folium.Map(location=center, zoom_start=13, tiles="cartodbpositron")

        # Add Title
        title_html = f'''
             <h3 align="center" style="font-size:20px; font-weight:bold; color:red;">{title}</h3>
             '''
        m.get_root().html.add_child(folium.Element(title_html))

        # Add CSS for glowing epicenter
        css = """
        <style>
        .pulse-epicenter {
            width: 24px;
            height: 24px;
            background-color: #000;
            border: 3px solid #ff0000;
            border-radius: 50%;
            box-shadow: 0 0 0 0 rgba(255, 0, 0, 1);
            transform: scale(1) translate(-50%, -50%);
            animation: pulse-red 1.5s infinite;
        }
        @keyframes pulse-red {
            0% { transform: scale(0.95) translate(-50%, -50%); box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.8); }
            70% { transform: scale(1.1) translate(-50%, -50%); box-shadow: 0 0 0 25px rgba(255, 0, 0, 0); }
            100% { transform: scale(0.95) translate(-50%, -50%); box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }
        }
        .pulse-label {
            color: #ff0000;
            font-weight: bold;
            font-size: 14px;
            text-shadow: 1px 1px 2px black;
            white-space: nowrap;
            margin-top: 15px;
            margin-left: -50px;
        }
        </style>
        """
        m.get_root().header.add_child(folium.Element(css))

        # Draw Edges
        for u, v, data in G.edges(data=True):
            p1 = [G.nodes[u]["latitude"], G.nodes[u]["longitude"]]
            p2 = [G.nodes[v]["latitude"], G.nodes[v]["longitude"]]
            
            geom = data.get("geometry")
            if geom:
                locations = geom
            else:
                locations = [p1, p2]
            
            lr = data.get("load_ratio", 0)
            color = self.get_color_edge(lr)
            weight = 4 if lr > 0.85 else 2
            
            # Highlight failure source
            if data.get("status") == "blocked" and data.get("failure_cause"):
                color = "#000000" # Black for total block
                weight = 8
                
                mid_lat = (p1[0] + p2[0]) / 2
                mid_lon = (p1[1] + p2[1]) / 2
                
                # Glowing Marker
                folium.Marker(
                    location=[mid_lat, mid_lon],
                    icon=folium.DivIcon(html='<div class="pulse-epicenter"></div><div class="pulse-label">PRIMARY FAILURE SOURCE</div>')
                ).add_to(m)
            
            status = data.get("status", "open").upper()
            road_name = data.get("road_name", "Unnamed Road")
            
            popup = f"""
                <b>Road:</b> {road_name}<br>
                <b>Status:</b> {status}<br>
                <b>Load Ratio:</b> {lr:.2%}<br>
                <b>Travel Time:</b> {data.get('current_travel_time', 0)}s<br>
                <b>Capacity:</b> {data.get('capacity', 0)} veh/hr
            """
            
            folium.PolyLine(
                locations=locations,
                color=color,
                weight=weight,
                opacity=0.8,
                popup=folium.Popup(popup, max_width=300)
            ).add_to(m)

        # Draw Nodes
        for node, data in G.nodes(data=True):
            lr = data.get("load_ratio", 0)
            node_type = str(data.get("node_type", "N/A")).lower()
            
            is_major = node_type in ["junction", "traffic_signals", "signal", "roundabout", "signal_failed"]
            
            if is_major:
                color = self.get_color_node(lr)
                radius = 6 if lr > 0.95 else 4
                opacity = 0.8
            else:
                color = "#7f8c8d" # Gray dot for minor points
                radius = 1
                opacity = 0.3
            
            popup = f"""
                <b>Junction:</b> {data.get('name', node)}<br>
                <b>Type:</b> {node_type}<br>
                <b>Status:</b> {data.get('status', 'normal').upper()}<br>
                <b>Load Ratio:</b> {lr:.2%}<br>
                <b>Load:</b> {data.get('current_load', 0)} / {data.get('capacity', 0)}
            """
            
            folium.CircleMarker(
                location=[data["latitude"], data["longitude"]],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=opacity,
                popup=folium.Popup(popup, max_width=300)
            ).add_to(m)

        # Add Legend
        legend_html = '''
             <div style="position: fixed; 
                         bottom: 50px; left: 50px; width: 150px; height: 130px; 
                         border:2px solid grey; z-index:9999; font-size:14px;
                         background-color: white; opacity: 0.85;
                         padding: 10px;">
             <b>Load Level</b><br>
             &nbsp;<i class="fa fa-circle" style="color:#2ecc71"></i>&nbsp; Normal (&lt;60%)<br>
             &nbsp;<i class="fa fa-circle" style="color:#f1c40f"></i>&nbsp; Moderate (60-85%)<br>
             &nbsp;<i class="fa fa-circle" style="color:#e67e22"></i>&nbsp; Congested (85-95%)<br>
             &nbsp;<i class="fa fa-circle" style="color:#e74c3c"></i>&nbsp; Critical (95-100%)<br>
             &nbsp;<i class="fa fa-circle" style="color:#2c3e50"></i>&nbsp; Failed (&gt;100%)
             </div>
             '''
        m.get_root().html.add_child(folium.Element(legend_html))

        # --- Draw Alternate Routes ---
        if "alternate_routes" in G.graph:
            for route in G.graph["alternate_routes"]:
                path = route["path"]
                # Create a feature group for the route
                fg = folium.FeatureGroup(name=f"Alt Route: {route.get('method', 'Path')}")
                
                # Draw the path with a distinct style
                points = []
                for node in path:
                    points.append([G.nodes[node]["latitude"], G.nodes[node]["longitude"]])
                
                folium.PolyLine(
                    locations=points,
                    color="#3498db", # Bright Blue
                    weight=6,
                    opacity=0.6,
                    dash_array='10, 10',
                    tooltip=f"Alternate Route ({route['total_time']}s) - {route.get('traffic_share_pct')}% traffic"
                ).add_to(fg)
                fg.add_to(m)

        save_path = self.output_dir / filename
        m.save(str(save_path))
        print(f"Cascade map saved at: {save_path}")
        return str(save_path)
