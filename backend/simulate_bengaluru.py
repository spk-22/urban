"""
simulate_bengaluru.py
=========================================
BENGALURU ROAD CASCADE DEMO
Corridor: Silk Board → HSR Layout → Bellandur → Marathahalli

This script:
1. Creates a realistic synthetic network of the ORR corridor
2. Runs 3 failure scenarios:
   - Scenario 1: Accident on ORR (Road Blockage)
   - Scenario 2: Silk Board Signal Failure
   - Scenario 3: Bellandur Flyover Closure
3. Outputs cascade analysis and alternate routes
=========================================
"""

import networkx as nx
import json
from pathlib import Path
from graph.cascade import RoadCascadeSimulator
from graph.cascade_visualizer import CascadeVisualizer

def create_bengaluru_network():
    """Creates a synthetic corridor representing Bengaluru's Outer Ring Road."""
    G = nx.Graph()

    # Nodes: Junctions/Intersections
    nodes = {
        "SilkBoard": {"latitude": 12.9176, "longitude": 77.6233, "name": "Silk Board Junction", "node_type": "signal"},
        "HSR_Entry": {"latitude": 12.9141, "longitude": 77.6385, "name": "HSR Layout Entrance", "node_type": "junction"},
        "Agara": {"latitude": 12.9250, "longitude": 77.6500, "name": "Agara Junction", "node_type": "signal"},
        "Iblur": {"latitude": 12.9200, "longitude": 77.6650, "name": "Iblur Junction", "node_type": "signal"},
        "Bellandur": {"latitude": 12.9300, "longitude": 77.6800, "name": "Bellandur Junction", "node_type": "signal"},
        "Ecospace": {"latitude": 12.9250, "longitude": 77.6900, "name": "Ecospace Entrance", "node_type": "junction"},
        "Devarabeesanahalli": {"latitude": 12.9350, "longitude": 77.6950, "name": "Devarabeesanahalli Junction", "node_type": "signal"},
        "Kadubeesanahalli": {"latitude": 12.9400, "longitude": 77.7000, "name": "Kadubeesanahalli Junction", "node_type": "junction"},
        "Marathahalli": {"latitude": 12.9550, "longitude": 77.7050, "name": "Marathahalli Bridge", "node_type": "interchange"},
        
        # Parallel/Secondary Roads
        "Sarjapur_Road_1": {"latitude": 12.9150, "longitude": 77.6550, "name": "Sarjapur Road - Agara", "node_type": "junction"},
        "HSR_Sector_1": {"latitude": 12.9100, "longitude": 77.6450, "name": "HSR Sector 1", "node_type": "junction"},
        "HSR_Sector_7": {"latitude": 12.9050, "longitude": 77.6350, "name": "HSR Sector 7", "node_type": "junction"},
        "Haralur_Road": {"latitude": 12.9100, "longitude": 77.6750, "name": "Haralur Road Junction", "node_type": "junction"},
        "Panathur_Road": {"latitude": 12.9400, "longitude": 77.7150, "name": "Panathur Road", "node_type": "junction"}
    }

    for node_id, attrs in nodes.items():
        G.add_node(node_id, **attrs)

    # Edges: Road Segments
    edges = [
        # Main ORR (Outer Ring Road)
        ("SilkBoard", "HSR_Entry", {"road_name": "Outer Ring Road", "highway": "trunk", "weight": 1800}),
        ("HSR_Entry", "Agara", {"road_name": "Outer Ring Road", "highway": "trunk", "weight": 1500}),
        ("Agara", "Iblur", {"road_name": "Outer Ring Road", "highway": "trunk", "weight": 1200}),
        ("Iblur", "Bellandur", {"road_name": "Outer Ring Road", "highway": "trunk", "weight": 1600}),
        ("Bellandur", "Ecospace", {"road_name": "Outer Ring Road", "highway": "trunk", "weight": 1000}),
        ("Ecospace", "Devarabeesanahalli", {"road_name": "Outer Ring Road", "highway": "trunk", "weight": 1100}),
        ("Devarabeesanahalli", "Kadubeesanahalli", {"road_name": "Outer Ring Road", "highway": "trunk", "weight": 800}),
        ("Kadubeesanahalli", "Marathahalli", {"road_name": "Outer Ring Road", "highway": "trunk", "weight": 2000}),

        # Sarjapur Road
        ("Agara", "Sarjapur_Road_1", {"road_name": "Sarjapur Road", "highway": "primary", "weight": 800}),
        ("Iblur", "Sarjapur_Road_1", {"road_name": "Sarjapur Road", "highway": "primary", "weight": 900}),

        # HSR Interior Roads (Alternates)
        ("SilkBoard", "HSR_Sector_7", {"road_name": "HSR 27th Main", "highway": "secondary", "weight": 1400}),
        ("HSR_Sector_7", "HSR_Sector_1", {"road_name": "HSR 19th Main", "highway": "secondary", "weight": 1200}),
        ("HSR_Sector_1", "Agara", {"road_name": "HSR 14th Main", "highway": "secondary", "weight": 1000}),
        
        # Haralur/Secondary
        ("Iblur", "Haralur_Road", {"road_name": "Haralur Road", "highway": "tertiary", "weight": 1500}),
        ("Bellandur", "Haralur_Road", {"road_name": "Haralur Connection", "highway": "residential", "weight": 2000}),
        
        # Panathur/Secondary
        ("Kadubeesanahalli", "Panathur_Road", {"road_name": "Panathur Road", "highway": "tertiary", "weight": 1200}),
        ("Marathahalli", "Panathur_Road", {"road_name": "Panathur Connection", "highway": "tertiary", "weight": 1800})
    ]

    for u, v, attrs in edges:
        G.add_edge(u, v, **attrs)

    return G

def run_simulation():
    print("\n" + "="*50)
    print(" BENGALURU ROAD CASCADE SIMULATION DEMO ")
    print("="*50)

    # 1. Create and initialize simulator
    raw_G = create_bengaluru_network()
    simulator = RoadCascadeSimulator(raw_G)
    visualizer = CascadeVisualizer()
    
    # Define route pairs for alternate path checking (e.g., Silk Board to Marathahalli)
    route_pairs = [("SilkBoard", "Marathahalli")]

    # Baseline Map
    simulator.prepare_graph()
    visualizer.create_cascade_map(simulator.G, "Bengaluru ORR - Baseline Traffic", "blr_baseline.html")

    # SCENARIO 1: Road Blockage (Accident on ORR)
    print("\n>>> SCENARIO 1: Accident on ORR (Agara to Iblur)")
    res1 = simulator.simulate_scenario(
        "road_blockage", 
        ("Agara", "Iblur"), 
        "major_accident",
        route_pairs=route_pairs
    )
    print_summary(res1)
    visualizer.create_cascade_map(res1["graph"], "Scenario 1: Accident on ORR", "blr_scenario_1.html")

    # SCENARIO 2: Signal Failure (Silk Board)
    print("\n>>> SCENARIO 2: Silk Board Junction Signal Failure")
    res2 = simulator.simulate_scenario(
        "signal_failure", 
        "SilkBoard", 
        "power_outage",
        route_pairs=route_pairs
    )
    print_summary(res2)
    visualizer.create_cascade_map(res2["graph"], "Scenario 2: Silk Board Signal Failure", "blr_scenario_2.html")

    # SCENARIO 3: Flyover Closure (Bellandur)
    print("\n>>> SCENARIO 3: Bellandur Flyover Closure")
    res3 = simulator.simulate_scenario(
        "flyover_closure", 
        ("Iblur", "Bellandur"), 
        "structural_maintenance",
        route_pairs=route_pairs
    )
    print_summary(res3)
    visualizer.create_cascade_map(res3["graph"], "Scenario 3: Bellandur Flyover Closure", "blr_scenario_3.html")

def print_summary(res):
    failure = res["failure_details"]
    cascade = res["cascade"]
    
    print(f"Cause: {res['cause']}")
    print(f"Displaced Traffic: {failure['displaced_traffic']} vehicles")
    print(f"Cascade Iterations: {cascade['iterations']}")
    print(f"New Overloaded Junctions: {cascade['total_overloaded']}")
    
    if cascade["overloaded_nodes"]:
        print("Overloaded Junctions List:")
        for node in res["overloaded_junctions"]:
            if node["severity"] in ["failed", "critical"]:
                print(f" - {node['name']} ({node['severity'].upper()}): Load Ratio {node['load_ratio']}")

    if res["alternate_routes"]:
        print("\nAlternate Routes (Silk Board -> Marathahalli):")
        for i, route in enumerate(res["alternate_routes"][0]["routes"]):
            print(f" Option {i+1}: {' -> '.join(route['path'])}")
            print(f"   Time: {route['total_time']}s | Traffic Share: {route['traffic_share_pct']}% | Status: {route['label'].upper()}")

if __name__ == "__main__":
    run_simulation()
