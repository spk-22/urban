"""
cascade_visualizer.py
=========================================================
ADVANCED STOCHASTIC URBAN SHOCKWAVE VISUALIZER

Features:
- OSM Highway Hierarchy Rendering
- Signal Junction Visualization
- Traffic Gravity Heat Representation
- Spillback Shockwave Rendering
- 97th Percentile Risk Visualization
- Alternate Route Leakage Visualization
- Congestion Pressure Layers
- Bengaluru-style Urban Cascade Visualization
=========================================================
"""

import folium
from folium.plugins import HeatMap, Fullscreen, MiniMap
from branca.element import Template, MacroElement
from pathlib import Path
import math


class CascadeVisualizer:

    def __init__(self, output_dir=None):

        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = (
                Path(__file__).resolve().parents[1]
                / "data"
                / "graphs"
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)

    # =====================================================
    # LOAD COLORS
    # =====================================================

    def get_congestion_color(self, ratio):

        if ratio < 0.55:
            return "#2ecc71"

        elif ratio < 0.75:
            return "#f1c40f"

        elif ratio < 0.90:
            return "#e67e22"

        elif ratio < 1.00:
            return "#ff0000"

        return "#000000"

    # =====================================================
    # ROAD CLASS STYLING
    # =====================================================

    def get_road_style(self, road_class, load_ratio=0.0):

        road_class = str(road_class).lower()

        base_styles = {

            "motorway": {
                "weight": 10,
                "color": "#8e44ad",
                "opacity": 0.95
            },

            "trunk": {
                "weight": 8,
                "color": "#c0392b",
                "opacity": 0.92
            },

            "primary": {
                "weight": 7,
                "color": "#e74c3c",
                "opacity": 0.90
            },

            "secondary": {
                "weight": 5,
                "color": "#f39c12",
                "opacity": 0.82
            },

            "tertiary": {
                "weight": 4,
                "color": "#f1c40f",
                "opacity": 0.75
            },

            "residential": {
                "weight": 2,
                "color": "#95a5a6",
                "opacity": 0.50
            },

            "service": {
                "weight": 1,
                "color": "#7f8c8d",
                "opacity": 0.40
            },

            "unclassified": {
                "weight": 2,
                "color": "#bdc3c7",
                "opacity": 0.45
            }
        }

        style = base_styles.get(
            road_class,
            {
                "weight": 2,
                "color": "#bdc3c7",
                "opacity": 0.45
            }
        )

        # Escalate during congestion
        if load_ratio >= 0.95:
            style["color"] = "#ff0000"
            style["weight"] += 3

        elif load_ratio >= 1.0:
            style["color"] = "#000000"
            style["weight"] += 5

        return style

    # =====================================================
    # SIGNAL NODE STYLE
    # =====================================================

    def get_signal_style(self, queue_pressure, failed=False):

        if failed:
            return {
                "radius": 12,
                "color": "#ff0000",
                "fillColor": "#000000",
                "weight": 4
            }

        if queue_pressure < 0.4:
            return {
                "radius": 6,
                "color": "#2ecc71",
                "fillColor": "#2ecc71",
                "weight": 2
            }

        elif queue_pressure < 0.75:
            return {
                "radius": 8,
                "color": "#f39c12",
                "fillColor": "#f39c12",
                "weight": 3
            }

        return {
            "radius": 10,
            "color": "#ff0000",
            "fillColor": "#ff0000",
            "weight": 4
        }

    # =====================================================
    # MAIN MAP
    # =====================================================

    def create_cascade_map(
        self,
        G,
        title="Urban Shockwave Simulation",
        filename="cascade_map.html"
    ):

        # =================================================
        # MAP CENTER
        # =================================================

        lats = [
            d["latitude"]
            for _, d in G.nodes(data=True)
            if "latitude" in d
        ]

        lons = [
            d["longitude"]
            for _, d in G.nodes(data=True)
            if "longitude" in d
        ]

        center = [
            sum(lats) / len(lats),
            sum(lons) / len(lons)
        ]

        # =================================================
        # BASE MAP
        # =================================================

        m = folium.Map(
            location=center,
            zoom_start=12,
            tiles="cartodbpositron",
            prefer_canvas=True
        )

        Fullscreen().add_to(m)
        MiniMap().add_to(m)

        # =================================================
        # TITLE
        # =================================================

        title_html = f"""
        <div style="
            position: fixed;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index:9999;
            background: rgba(0,0,0,0.82);
            padding: 12px 20px;
            border-radius: 12px;
            border: 2px solid #ff0000;
            color: white;
            font-size: 22px;
            font-weight: bold;
            box-shadow: 0 0 20px rgba(255,0,0,0.5);
        ">
            {title}
        </div>
        """

        m.get_root().html.add_child(
            folium.Element(title_html)
        )

        # =================================================
        # CSS
        # =================================================

        css = """
        <style>

        .signal-pulse {

            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: rgba(255,0,0,0.95);
            position: relative;
            animation: pulseSignal 1.5s infinite;
            border: 2px solid white;
        }

        @keyframes pulseSignal {

            0% {
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(255,0,0,0.7);
            }

            70% {
                transform: scale(1.15);
                box-shadow: 0 0 0 20px rgba(255,0,0,0);
            }

            100% {
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(255,0,0,0);
            }
        }

        .gravity-zone {

            color: #ff0000;
            font-weight: bold;
            font-size: 13px;
            text-shadow: 1px 1px 2px black;
            white-space: nowrap;
        }

        </style>
        """

        m.get_root().header.add_child(
            folium.Element(css)
        )

        # =================================================
        # HEATMAP DATA
        # =================================================

        heat_data = []

        # =================================================
        # DRAW EDGES
        # =================================================

        for u, v, data in G.edges(data=True):

            if (
                "latitude" not in G.nodes[u]
                or "latitude" not in G.nodes[v]
            ):
                continue

            p1 = [
                G.nodes[u]["latitude"],
                G.nodes[u]["longitude"]
            ]

            p2 = [
                G.nodes[v]["latitude"],
                G.nodes[v]["longitude"]
            ]

            geom = data.get("geometry")

            if geom:
                locations = geom
            else:
                locations = [p1, p2]

            load_ratio = data.get("load_ratio", 0)

            road_class = data.get(
                "road_class",
                "unclassified"
            )

            style = self.get_road_style(
                road_class,
                load_ratio
            )

            status = data.get(
                "status",
                "open"
            )

            # =============================================
            # FAILURE SOURCE
            # =============================================

            if (
                status == "blocked"
                and data.get("failure_cause")
            ):

                style["color"] = "#000000"
                style["weight"] += 4

                mid_lat = (p1[0] + p2[0]) / 2
                mid_lon = (p1[1] + p2[1]) / 2

                folium.Marker(
                    location=[mid_lat, mid_lon],
                    icon=folium.DivIcon(
                        html="""
                        <div class="signal-pulse"></div>
                        """
                    ),
                    tooltip="PRIMARY FAILURE SOURCE"
                ).add_to(m)

            # =============================================
            # SPILLBACK VISUALIZATION
            # =============================================

            spillback = data.get(
                "spillback_factor",
                1.0
            )

            if spillback > 1.4:

                folium.PolyLine(
                    locations=locations,
                    color="#8e44ad",
                    weight=style["weight"] + 2,
                    opacity=0.25,
                    dash_array="15, 10"
                ).add_to(m)

            # =============================================
            # TOOLTIP
            # =============================================

            tooltip_html = f"""
            <div style="font-size:13px; width:300px;">

            <b style="font-size:15px;">
            {data.get('road_name', 'Unnamed Road')}
            </b>

            <hr>

            <b>OSM Highway:</b>
            {road_class}

            <br>

            <b>Status:</b>
            {status.upper()}

            <br>

            <b>Current Load:</b>
            {round(data.get('current_load', 0), 2)}

            <br>

            <b>97th Percentile Load:</b>
            {round(data.get('p97_load', data.get('current_load', 0)), 2)}

            <br>

            <b>Load Ratio:</b>
            {round(load_ratio * 100, 2)}%

            <br>

            <b>Travel Time:</b>
            {round(data.get('current_travel_time', 0), 2)} sec

            <br>

            <b>97th Percentile Delay:</b>
            {round(data.get('p97_delay', data.get('current_travel_time', 0)), 2)} sec

            <br>

            <b>Capacity:</b>
            {data.get('capacity', 0)} veh/hr

            <br>

            <b>Storage Capacity:</b>
            {data.get('storage_capacity', 0)}

            <br>

            <b>Gravity Weight:</b>
            {round(data.get('gravity_weight', 1.0), 2)}

            <br>

            <b>Lane Entrapment:</b>
            {round(data.get('lane_entrapment', 0), 3)}

            <br>

            <b>Turning Friction:</b>
            {round(data.get('turning_friction', 0), 3)}

            <br>

            <b>Signal Confusion:</b>
            {round(data.get('signal_confusion', 0), 3)}

            <br>

            <b>Spillback Factor:</b>
            {round(data.get('spillback_factor', 1.0), 3)}

            <br>

            <b>Shockwave Severity:</b>
            {data.get('shockwave_severity', 'stable')}

            </div>
            """

            popup_html = f"""
            <div style="width:320px;">
            <h4>{data.get('road_name', 'Unnamed Road')}</h4>

            <b>Road Type:</b> {road_class}<br>
            <b>Operational State:</b> {status}<br>
            <b>Urban Role:</b>
            {'Major Arterial Corridor' if road_class in ['motorway','trunk','primary'] else 'Redistribution Corridor'}
            </div>
            """

            folium.PolyLine(
                locations=locations,
                color=style["color"],
                weight=style["weight"],
                opacity=style["opacity"],
                tooltip=tooltip_html,
                popup=folium.Popup(
                    popup_html,
                    max_width=350
                )
            ).add_to(m)

            # =============================================
            # HEATMAP
            # =============================================

            if load_ratio > 0.7:

                heat_data.append([
                    p1[0],
                    p1[1],
                    min(load_ratio, 2.0)
                ])

        # =================================================
        # SIGNAL NODES
        # =================================================

        for node, data in G.nodes(data=True):

            if "latitude" not in data:
                continue

            lat = data["latitude"]
            lon = data["longitude"]

            is_signal = data.get(
                "is_signal",
                False
            )

            load_ratio = data.get(
                "load_ratio",
                0
            )

            queue_pressure = data.get(
                "queue_pressure",
                0
            )

            spillback_probability = data.get(
                "spillback_probability",
                0
            )

            status = data.get(
                "status",
                "normal"
            )

            # =============================================
            # SIGNALIZED JUNCTIONS
            # =============================================

            if is_signal:

                style = self.get_signal_style(
                    queue_pressure,
                    failed=(status == "failed")
                )

                tooltip = f"""
                <div style="width:300px;">

                <b style="font-size:15px;">
                SIGNALIZED INTERSECTION
                </b>

                <hr>

                <b>Name:</b>
                {data.get('name', node)}

                <br>

                <b>Status:</b>
                {status.upper()}

                <br>

                <b>Incoming Load:</b>
                {round(data.get('incoming_load', 0), 2)}

                <br>

                <b>Outgoing Load:</b>
                {round(data.get('outgoing_load', 0), 2)}

                <br>

                <b>Queue Pressure:</b>
                {round(queue_pressure, 3)}

                <br>

                <b>Spillback Probability:</b>
                {round(spillback_probability * 100, 2)}%

                <br>

                <b>Signal Stability:</b>
                {round(1 - spillback_probability, 3)}

                <br>

                <b>Current Load:</b>
                {round(data.get('current_load', 0), 2)}

                <br>

                <b>97th Percentile Pressure:</b>
                {round(data.get('p97_pressure', queue_pressure), 3)}

                <br>

                <b>Node Capacity:</b>
                {data.get('capacity', 0)}

                <br>

                <b>Urban Role:</b>
                Dynamic Queue Control Node

                </div>
                """

                folium.CircleMarker(
                    location=[lat, lon],
                    radius=style["radius"],
                    color=style["color"],
                    fill=True,
                    fill_color=style["fillColor"],
                    fill_opacity=0.95,
                    weight=style["weight"],
                    tooltip=tooltip
                ).add_to(m)

                # Pulse marker for failed signal
                if status in ["failed", "degraded"]:

                    folium.Marker(
                        location=[lat, lon],
                        icon=folium.DivIcon(
                            html="""
                            <div class="signal-pulse"></div>
                            """
                        )
                    ).add_to(m)

            # =============================================
            # NORMAL NODES
            # =============================================

            else:

                if load_ratio > 0.85:

                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=4,
                        color=self.get_congestion_color(
                            load_ratio
                        ),
                        fill=True,
                        fill_opacity=0.5,
                        opacity=0.5,
                        tooltip=f"""
                        Node: {node}<br>
                        Load Ratio: {round(load_ratio * 100, 2)}%
                        """
                    ).add_to(m)

        # =================================================
        # HEATMAP LAYER
        # =================================================

        if heat_data:

            HeatMap(
                heat_data,
                radius=18,
                blur=20,
                min_opacity=0.4
            ).add_to(m)

        # =================================================
        # ALTERNATE ROUTES
        # =================================================

        if "alternate_routes" in G.graph:

            for route in G.graph["alternate_routes"]:

                path = route["path"]

                points = []

                for node in path:

                    if node in G.nodes:

                        points.append([
                            G.nodes[node]["latitude"],
                            G.nodes[node]["longitude"]
                        ])

                folium.PolyLine(
                    locations=points,
                    color="#3498db",
                    weight=6,
                    opacity=0.75,
                    dash_array="12,8",
                    tooltip=f"""
                    Alternate Redistribution Route<br>
                    Travel Time:
                    {route.get('total_time', 0)} sec<br>
                    Traffic Share:
                    {route.get('traffic_share_pct', 0)}%
                    """
                ).add_to(m)

        # =================================================
        # LEGEND
        # =================================================

        legend_html = """
        <div style="
            position: fixed;
            bottom: 30px;
            left: 20px;
            width: 320px;
            background: rgba(0,0,0,0.88);
            color: white;
            z-index:9999;
            padding: 18px;
            border-radius: 14px;
            border: 2px solid #34495e;
            font-size: 13px;
        ">

        <h4 style="margin-top:0;">
        Bengaluru Urban Shockwave Layers
        </h4>

        <hr>

        <b>ROAD HIERARCHY</b><br>

        <span style="color:#8e44ad;">━━</span>
        Motorway / Expressway<br>

        <span style="color:#c0392b;">━━</span>
        Trunk Corridor<br>

        <span style="color:#e74c3c;">━━</span>
        Primary Arterial<br>

        <span style="color:#f39c12;">━━</span>
        Secondary Road<br>

        <span style="color:#95a5a6;">━━</span>
        Residential / Local<br>

        <hr>

        <b>INFRASTRUCTURE NODES</b><br>

        🔴 Signalized Junction<br>
        ⚫ Failed Signal Collapse<br>
        🟣 Spillback Shockwave<br>

        <hr>

        <b>CONGESTION</b><br>

        🟢 Stable<br>
        🟡 Moderate<br>
        🟠 Congested<br>
        🔴 Critical<br>
        ⚫ Collapse State

        <hr>

        <b>SIMULATION ENGINE</b><br>

        • Stochastic Redistribution<br>
        • Spillback Shockwaves<br>
        • Lane Entrapment<br>
        • Signal Collapse Dynamics<br>
        • 97th Percentile Stress

        </div>
        """

        m.get_root().html.add_child(
            folium.Element(legend_html)
        )

        # =================================================
        # SAVE
        # =================================================

        save_path = self.output_dir / filename

        m.save(str(save_path))

        print(f"[✓] Cascade map saved: {save_path}")

        return str(save_path)