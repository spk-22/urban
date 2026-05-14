"""
cascade.py
=========================================
CAPACITY-BASED ROAD CASCADE FAILURE SIMULATOR

Core principle:
  A node fails when vehicles cannot effectively
  pass through it — NOT when it disappears.

Bengaluru roads rarely fully disconnect.
Instead: travel time explodes, congestion propagates.

Three failure scenarios:
  1. Road Blockage (accident/flood/construction)
  2. Traffic Signal Failure (power outage)
  3. Flyover Closure (structural/maintenance)

Uses:
  - BPR formula for travel time
  - Yen's K-shortest paths for alternates
  - Probabilistic traffic redistribution
=========================================
"""

import copy
import math
import random
import networkx as nx
from itertools import islice


# =========================================
# ROAD CLASS DEFAULTS
# =========================================
ROAD_CLASS_DEFAULTS = {
    "motorway":    {"speed_kmh": 80, "edge_capacity": 4000, "node_capacity": 6000},
    "trunk":       {"speed_kmh": 60, "edge_capacity": 3000, "node_capacity": 4500},
    "primary":     {"speed_kmh": 50, "edge_capacity": 2000, "node_capacity": 3500},
    "secondary":   {"speed_kmh": 40, "edge_capacity": 1500, "node_capacity": 2500},
    "tertiary":    {"speed_kmh": 30, "edge_capacity": 1000, "node_capacity": 1500},
    "residential": {"speed_kmh": 20, "edge_capacity": 500,  "node_capacity": 800},
    "service":     {"speed_kmh": 15, "edge_capacity": 300,  "node_capacity": 500},
    "unclassified": {"speed_kmh": 25, "edge_capacity": 600, "node_capacity": 900},
}

DEFAULT_ROAD = {"speed_kmh": 30, "edge_capacity": 800, "node_capacity": 1200}

# BPR formula constants
BPR_ALPHA = 0.15
BPR_BETA = 4.0


class RoadCascadeSimulator:
    """
    Capacity-based cascade failure simulator for road networks.
    Works on undirected graphs (nx.Graph).
    """

    def __init__(self, G):
        """
        Initialize with a networkx Graph that has
        latitude, longitude on nodes and weight (distance) on edges.
        """
        self.original_graph = G
        self.G = None  # working copy, set per simulation
        from geopy.distance import geodesic
        self._geodesic = geodesic

    def _geodesic_dist(self, n1_data, n2_data):
        try:
            # Fast Euclidean approximation (roughly meters, adequate for weighting)
            lat1, lon1 = float(n1_data["latitude"]), float(n1_data["longitude"])
            lat2, lon2 = float(n2_data["latitude"]), float(n2_data["longitude"])
            return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2) * 111000.0
        except:
            return 1000.0

    # =========================================
    # GRAPH PREPARATION
    # =========================================
    def prepare_graph(self, baseline_load_range=(0.45, 0.70)):
        """
        Add capacity, load, travel-time attributes
        to all nodes and edges. Creates a deep copy.
        """
        self.G = copy.deepcopy(self.original_graph)

        # --- Nodes ---
        for node, data in self.G.nodes(data=True):
            rc = self._get_road_class(data)
            defaults = ROAD_CLASS_DEFAULTS.get(rc, DEFAULT_ROAD)

            cap = defaults["node_capacity"]
            load_pct = random.uniform(*baseline_load_range)
            load = int(cap * load_pct)

            self.G.nodes[node]["capacity"] = cap
            self.G.nodes[node]["current_load"] = load
            self.G.nodes[node]["load_ratio"] = round(load / cap, 4)
            self.G.nodes[node]["node_type"] = data.get("node_type", "junction")
            self.G.nodes[node]["status"] = "normal"
            self.G.nodes[node]["road_class_used"] = rc

        # --- Edges ---
        for u, v, data in self.G.edges(data=True):
            rc = data.get("road_class", data.get("highway", "default"))
            if rc in ("N/A", None, ""):
                rc = "default"
            defaults = ROAD_CLASS_DEFAULTS.get(rc, DEFAULT_ROAD)

            cap = defaults["edge_capacity"]
            speed = defaults["speed_kmh"]
            dist_m = float(data.get("weight", 500))
            free_flow = (dist_m / 1000.0) / speed * 3600  # seconds

            load_pct = random.uniform(*baseline_load_range)
            load = int(cap * load_pct)
            travel_time = self._bpr_travel_time(free_flow, load, cap)
            
            # Queue Storage Capacity (approx 6 meters per vehicle * lanes)
            lanes = 2
            if rc in ["motorway", "trunk"]: lanes = 3
            elif rc in ["residential", "service"]: lanes = 1
            storage_capacity = int((dist_m / 6.0) * lanes)

            self.G.edges[u, v]["capacity"] = cap
            self.G.edges[u, v]["storage_capacity"] = storage_capacity
            self.G.edges[u, v]["current_load"] = load
            self.G.edges[u, v]["free_flow_time"] = round(free_flow, 2)
            self.G.edges[u, v]["current_travel_time"] = round(travel_time, 2)
            self.G.edges[u, v]["load_ratio"] = round(load / cap, 4)
            self.G.edges[u, v]["speed_kmh"] = speed
            self.G.edges[u, v]["status"] = "open"
            self.G.edges[u, v]["road_class"] = rc

        return self.G

    # =========================================
    # BPR TRAVEL TIME (NON-LINEAR SHOCKWAVE)
    # =========================================
    def _bpr_travel_time(self, free_flow, flow, capacity):
        if capacity <= 0:
            return free_flow * 100
        ratio = flow / capacity
        base_bpr = free_flow * (1 + BPR_ALPHA * (ratio ** BPR_BETA))
        
        # Bengaluru non-linear escalation
        if ratio >= 0.97:
            return base_bpr * 20.0 # Catastrophic gridlock
        elif ratio >= 0.92:
            return base_bpr * 5.0  # Unstable
        elif ratio >= 0.85:
            return base_bpr * 2.0  # Heavy queue
            
        return base_bpr

    # =========================================
    # ROAD CLASS HELPER
    # =========================================
    def _get_road_class(self, data):
        for key in ("road_class", "highway_type", "highway", "road_type"):
            val = data.get(key, "")
            if val and val != "N/A":
                val_lower = str(val).lower().strip()
                if val_lower in ROAD_CLASS_DEFAULTS:
                    return val_lower
        return "default"

    # =========================================
    # SCENARIO 1: ROAD BLOCKAGE
    # =========================================
    def inject_road_blockage(self, edge_or_node, cause="accident"):
        """
        Block a road segment (edge) or junction (node).
        Returns displaced traffic volume.
        """
        displaced = 0

        if isinstance(edge_or_node, tuple) and len(edge_or_node) == 2:
            u, v = edge_or_node
            if self.G.has_edge(u, v):
                displaced = self.G.edges[u, v].get("current_load", 0)
                self.G.edges[u, v]["status"] = "blocked"
                self.G.edges[u, v]["capacity"] = 0
                self.G.edges[u, v]["current_load"] = 0
                self.G.edges[u, v]["current_travel_time"] = float('inf')
                self.G.edges[u, v]["load_ratio"] = 0
                self.G.edges[u, v]["failure_cause"] = cause
        else:
            node = edge_or_node
            if self.G.has_node(node):
                displaced = self.G.nodes[node].get("current_load", 0)
                self.G.nodes[node]["status"] = "failed"
                self.G.nodes[node]["current_load"] = 0
                self.G.nodes[node]["capacity"] = 0
                self.G.nodes[node]["load_ratio"] = 0
                self.G.nodes[node]["failure_cause"] = cause
                # Block all adjacent edges
                for neighbor in list(self.G.neighbors(node)):
                    edge_load = self.G.edges[node, neighbor].get("current_load", 0)
                    displaced += edge_load
                    self.G.edges[node, neighbor]["status"] = "blocked"
                    self.G.edges[node, neighbor]["capacity"] = 0
                    self.G.edges[node, neighbor]["current_load"] = 0
                    self.G.edges[node, neighbor]["current_travel_time"] = float('inf')

        return {"displaced_traffic": displaced, "cause": cause, "scenario": "road_blockage"}

    # =========================================
    # SCENARIO 2: SIGNAL FAILURE
    # =========================================
    def inject_signal_failure(self, node_id, cause="power_outage"):
        """
        Signal failure reduces junction capacity by 60-70%.
        Throughput drops, congestion increases.
        """
        if not self.G.has_node(node_id):
            return {"error": f"Node {node_id} not found"}

        data = self.G.nodes[node_id]
        old_cap = data.get("capacity", 1200)
        reduction = random.uniform(0.60, 0.70)
        new_cap = int(old_cap * (1 - reduction))

        self.G.nodes[node_id]["capacity"] = new_cap
        self.G.nodes[node_id]["status"] = "degraded"
        self.G.nodes[node_id]["node_type"] = "signal_failed"
        self.G.nodes[node_id]["failure_cause"] = cause

        current = data.get("current_load", 0)
        new_ratio = current / new_cap if new_cap > 0 else 99.0
        self.G.nodes[node_id]["load_ratio"] = round(new_ratio, 4)

        displaced = max(0, current - new_cap)

        # Increase travel time on all adjacent edges
        for neighbor in self.G.neighbors(node_id):
            edge = self.G.edges[node_id, neighbor]
            old_tt = edge.get("current_travel_time", 60)
            edge["current_travel_time"] = round(old_tt * 2.5, 2)
            edge["status"] = "congested"

        return {
            "displaced_traffic": displaced,
            "old_capacity": old_cap,
            "new_capacity": new_cap,
            "reduction_pct": round(reduction * 100, 1),
            "cause": cause,
            "scenario": "signal_failure"
        }

    # =========================================
    # SCENARIO 3: FLYOVER CLOSURE
    # =========================================
    def inject_flyover_closure(self, edge, cause="structural_issue"):
        """
        Close a flyover edge. All traffic must use
        ground-level alternatives.
        """
        if isinstance(edge, tuple) and len(edge) == 2:
            u, v = edge
        else:
            return {"error": "Edge must be (u, v) tuple"}

        if not self.G.has_edge(u, v):
            return {"error": f"Edge {u}-{v} not found"}

        displaced = self.G.edges[u, v].get("current_load", 0)
        self.G.edges[u, v]["status"] = "blocked"
        self.G.edges[u, v]["capacity"] = 0
        self.G.edges[u, v]["current_load"] = 0
        self.G.edges[u, v]["current_travel_time"] = float('inf')
        self.G.edges[u, v]["load_ratio"] = 0
        self.G.edges[u, v]["failure_cause"] = cause
        self.G.edges[u, v]["closure_type"] = "flyover"

        return {
            "displaced_traffic": displaced,
            "cause": cause,
            "scenario": "flyover_closure"
        }

    # =========================================
    # CASCADE PROPAGATION ENGINE (TEMPORAL)
    # =========================================
    def propagate_cascade(self, failure_result, max_iterations=15):
        """
        Temporal cascade simulation. Simulates Minute by Minute.
        Includes Queue Spillback and Junction Failure multipliers.
        """
        cascade_log = []
        displaced = failure_result.get("displaced_traffic", 0)

        if displaced <= 0:
            return {"iterations": 0, "cascade_log": [], "total_overloaded": 0}

        newly_overloaded = set()
        
        # SUPER-NODES: Roads that trigger massive collapses
        super_node_keywords = ["outer ring road", "hosur road", "bellary road", "old madras road"]

        for iteration in range(max_iterations):
            minute = iteration * 2 # Represents time progression
            if displaced <= 50:
                break

            # Find candidate nodes
            candidate_nodes = []
            for node, data in self.G.nodes(data=True):
                if data.get("status") == "failed":
                    continue
                remaining = data.get("capacity", 0) - data.get("current_load", 0)
                if remaining > 0:
                    candidate_nodes.append((node, remaining))

            if not candidate_nodes:
                cascade_log.append({
                    "minute": minute,
                    "event": "NO_CAPACITY_LEFT",
                    "displaced_remaining": displaced
                })
                break

            total_score = 0
            node_scores = []
            
            failure_points = []
            if iteration == 0:
                target = failure_result.get("target_id")
                if isinstance(target, tuple):
                    u, v = target
                    failure_points.append(self.G.nodes[u])
                    failure_points.append(self.G.nodes[v])
                elif target in self.G.nodes:
                    failure_points.append(self.G.nodes[target])
            else:
                for n_id in newly_overloaded:
                    failure_points.append(self.G.nodes[n_id])

            for node, remaining_cap in candidate_nodes:
                dist_score = 1.0
                if failure_points:
                    min_dist = float('inf')
                    for fp in failure_points:
                        d = self._geodesic_dist(self.G.nodes[node], fp)
                        min_dist = min(min_dist, d)
                    dist_score = 1.0 / (1.0 + (min_dist / 1000.0) ** 2)

                # Intersection hierarchy weight (higher degree = attracts more)
                degree_weight = 1.0 + (self.G.degree[node] * 0.2)
                
                # Super-node amplifier
                name = str(self.G.nodes[node].get("road_name", "")).lower()
                if any(kw in name for kw in super_node_keywords):
                    degree_weight *= 2.0

                score = remaining_cap * dist_score * degree_weight
                node_scores.append((node, score, remaining_cap))
                total_score += score

            iteration_overloads = []
            
            # --- DISTRIBUTE LOAD ---
            for node, score, remaining_cap in node_scores:
                share = (score / total_score) * displaced if total_score > 0 else 0
                share *= 3.0 # Stronger localization

                old_load = self.G.nodes[node]["current_load"]
                new_load = old_load + int(share)
                cap = self.G.nodes[node]["capacity"]
                
                # If it's a signalized junction, fail faster (threshold 0.85 instead of 1.0)
                fail_threshold = 0.85 if self.G.nodes[node].get("node_type") == "signal" else 1.0

                self.G.nodes[node]["current_load"] = new_load
                new_ratio = new_load / cap if cap > 0 else 99.0
                self.G.nodes[node]["load_ratio"] = round(new_ratio, 4)

                # Update adjacent edges & SPILLBACK
                for neighbor in self.G.neighbors(node):
                    edge = self.G.edges[node, neighbor]
                    if edge.get("status") == "blocked":
                        continue
                        
                    e_cap = edge.get("capacity", 800)
                    e_load = edge.get("current_load", 0)
                    storage_cap = edge.get("storage_capacity", 100)
                    
                    added = int(share * 0.4)
                    new_e_load = e_load + added
                    edge["current_load"] = new_e_load
                    edge["load_ratio"] = round(new_e_load / e_cap, 4) if e_cap > 0 else 99.0
                    
                    # QUEUE SPILLBACK LOGIC
                    if new_e_load > storage_cap:
                        # Queue exceeds physical storage! Upstream node is penalized.
                        upstream_node = neighbor # Simplified direction assumption
                        u_data = self.G.nodes[upstream_node]
                        if u_data.get("status") != "failed":
                            # Sharp capacity reduction for upstream intersection
                            u_data["capacity"] = int(u_data.get("capacity", 1000) * 0.5)
                            u_data["status"] = "degraded"
                    
                    ff = edge.get("free_flow_time", 60)
                    edge["current_travel_time"] = round(self._bpr_travel_time(ff, new_e_load, e_cap), 2)
                    
                    if new_e_load > e_cap:
                        edge["status"] = "congested"

                # Check overload
                if new_ratio > fail_threshold:
                    self.G.nodes[node]["status"] = "failed"
                    excess = new_load - int(cap * fail_threshold)
                    self.G.nodes[node]["capacity"] = int(cap * 0.5) # Crippled
                    newly_overloaded.add(node)
                    iteration_overloads.append({
                        "node": node,
                        "load_ratio": round(new_ratio, 3),
                        "excess": excess,
                        "lat": self.G.nodes[node].get("latitude"),
                        "lon": self.G.nodes[node].get("longitude"),
                        "name": self.G.nodes[node].get("road_name", self.G.nodes[node].get("name", node))
                    })
                elif new_ratio > 0.9:
                    self.G.nodes[node]["status"] = "degraded"

            displaced = sum(o["excess"] for o in iteration_overloads)

            cascade_log.append({
                "iteration": iteration + 1,
                "minute": minute,
                "displaced_traffic": displaced,
                "new_overloads": iteration_overloads,
                "num_overloaded": len(iteration_overloads)
            })

            if not iteration_overloads:
                break

        return {
            "iterations": len(cascade_log),
            "cascade_log": cascade_log,
            "total_overloaded": len(newly_overloaded),
            "overloaded_nodes": list(newly_overloaded)
        }

    # =========================================
    # ALTERNATE ROUTE FINDER
    # Dijkstra + Yen's K-Shortest Paths
    # =========================================
    def find_alternate_routes(self, source, target, k=3):
        """
        Find top K alternate routes using Yen's algorithm.
        Weight = current_travel_time (congestion-aware).
        Score each route and distribute load probabilistically.
        """
        # Build weight function: use travel time, skip blocked
        def weight_fn(u, v, data):
            if data.get("status") == "blocked":
                return float('inf')
            return data.get("current_travel_time", 9999)

        routes = []
        try:
            # Yen's K-shortest simple paths
            paths_gen = nx.shortest_simple_paths(
                self.G, source, target, weight=weight_fn
            )
            for path in islice(paths_gen, k):
                route_info = self._score_route(path)
                if route_info["total_time"] < float('inf'):
                    routes.append(route_info)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        # Also try plain Dijkstra for comparison
        try:
            dij_path = nx.dijkstra_path(self.G, source, target, weight=weight_fn)
            dij_info = self._score_route(dij_path)
            dij_info["method"] = "dijkstra"
            # Add if not duplicate
            existing_paths = [tuple(r["path"]) for r in routes]
            if tuple(dij_path) not in existing_paths:
                routes.insert(0, dij_info)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        if not routes:
            return {"routes": [], "message": "No viable route found"}

        # Probabilistic load distribution
        routes = self._distribute_load(routes)

        return {"routes": routes, "source": source, "target": target}

    def _score_route(self, path):
        """Score a route by travel time, congestion, capacity."""
        total_time = 0
        total_congestion = 0
        min_remaining_cap = float('inf')
        congested_segments = []
        edges_info = []
        has_blocked = False

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge = self.G.edges.get((u, v), {})
            tt = edge.get("current_travel_time", 9999)
            lr = edge.get("load_ratio", 0)
            cap = edge.get("capacity", 0)
            load = edge.get("current_load", 0)
            status = edge.get("status", "open")

            if status == "blocked":
                has_blocked = True

            total_time += tt
            total_congestion += lr
            remaining = cap - load
            if remaining < min_remaining_cap:
                min_remaining_cap = remaining

            if lr > 0.8:
                congested_segments.append({
                    "edge": f"{u} → {v}",
                    "load_ratio": round(lr, 3),
                    "road": edge.get("road_name", "N/A")
                })

            edges_info.append({
                "from": u, "to": v,
                "travel_time": round(tt, 1),
                "load_ratio": round(lr, 3),
                "status": status,
                "road_name": edge.get("road_name", "N/A")
            })

        avg_congestion = total_congestion / max(len(path) - 1, 1)

        if has_blocked:
            label = "blocked"
        elif avg_congestion > 0.95:
            label = "avoid"
        elif avg_congestion > 0.8:
            label = "congested"
        elif avg_congestion > 0.6:
            label = "moderate"
        else:
            label = "clear"

        return {
            "path": path,
            "hops": len(path) - 1,
            "total_time": round(total_time, 2),
            "avg_congestion": round(avg_congestion, 4),
            "min_remaining_capacity": max(0, int(min_remaining_cap)) if min_remaining_cap != float('inf') else 0,
            "congested_segments": congested_segments,
            "label": label,
            "method": "yen_k_shortest",
            "edges": edges_info
        }

    def _distribute_load(self, routes):
        """
        Human-biased probabilistic load distribution.
        70% fastest, 20% secondary, 10% local/leakage.
        """
        if not routes:
            return routes

        # Sort routes by travel time
        routes.sort(key=lambda x: x["total_time"])
        
        if len(routes) == 1:
            routes[0]["traffic_share_pct"] = 100.0
            return routes
            
        elif len(routes) == 2:
            routes[0]["traffic_share_pct"] = 75.0
            routes[1]["traffic_share_pct"] = 25.0
            return routes
            
        elif len(routes) >= 3:
            routes[0]["traffic_share_pct"] = 70.0 # Google Maps favorite
            routes[1]["traffic_share_pct"] = 20.0 # Secondary arterial
            routes[2]["traffic_share_pct"] = 10.0 # Local leakage
            
            # If there are more than 3, zero them out for simplicity of the 70/20/10 model
            for i in range(3, len(routes)):
                routes[i]["traffic_share_pct"] = 0.0
                
        return routes

    # =========================================
    # JUNCTION OVERLOAD DETECTOR
    # =========================================
    def detect_overloaded_junctions(self, threshold=0.85):
        """
        Scan all junction nodes, return sorted by load_ratio.
        """
        overloaded = []

        for node, data in self.G.nodes(data=True):
            lr = data.get("load_ratio", 0)
            if lr < threshold:
                continue

            affected_roads = []
            over_cap_edges = 0
            for neighbor in self.G.neighbors(node):
                edge = self.G.edges[node, neighbor]
                road_name = edge.get("road_name", "N/A")
                if edge.get("load_ratio", 0) > 0.8:
                    over_cap_edges += 1
                    affected_roads.append(road_name)

            if lr > 1.0:
                severity = "failed"
            elif lr > 0.95:
                severity = "critical"
            elif lr > 0.85:
                severity = "warning"
            else:
                severity = "watch"

            overloaded.append({
                "node_id": node,
                "name": data.get("road_name", data.get("name", node)),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "load_ratio": round(lr, 4),
                "capacity": data.get("capacity", 0),
                "current_load": data.get("current_load", 0),
                "status": data.get("status", "normal"),
                "severity": severity,
                "over_capacity_edges": over_cap_edges,
                "affected_roads": list(set(affected_roads)),
                "node_type": data.get("node_type", "junction")
            })

        overloaded.sort(key=lambda x: x["load_ratio"], reverse=True)
        return overloaded

    # =========================================
    # FULL SIMULATION RUNNER
    # =========================================
    def simulate_scenario(self, scenario_type, target_id, cause,
                          route_pairs=None):
        """
        End-to-end: inject failure → propagate cascade →
        detect overloads → find alternates.
        """
        # 1. Prepare graph with capacity attributes
        self.prepare_graph()

        # 2. Snapshot before state
        before_state = self._snapshot_state()

        # 3. Inject failure
        if scenario_type == "road_blockage":
            failure = self.inject_road_blockage(target_id, cause)
        elif scenario_type == "signal_failure":
            failure = self.inject_signal_failure(target_id, cause)
        elif scenario_type == "flyover_closure":
            failure = self.inject_flyover_closure(target_id, cause)
        else:
            return {"error": f"Unknown scenario: {scenario_type}"}

        # 4. Propagate cascade
        cascade = self.propagate_cascade(failure)

        # 5. Detect overloaded junctions
        overloaded = self.detect_overloaded_junctions()

        # 6. Find alternate routes if pairs given
        alternate_routes = []
        if route_pairs:
            for src, dst in route_pairs:
                result = self.find_alternate_routes(src, dst)
                alternate_routes.append(result)

        # 7. After state
        after_state = self._snapshot_state()

        return {
            "scenario": scenario_type,
            "cause": cause,
            "failure_details": failure,
            "cascade": cascade,
            "overloaded_junctions": overloaded,
            "alternate_routes": alternate_routes,
            "before_state": before_state,
            "after_state": after_state,
            "graph": self.G
        }

    def _snapshot_state(self):
        """Quick summary of current graph state."""
        statuses = {"normal": 0, "degraded": 0, "failed": 0}
        for _, data in self.G.nodes(data=True):
            s = data.get("status", "normal")
            statuses[s] = statuses.get(s, 0) + 1

        edge_statuses = {"open": 0, "congested": 0, "blocked": 0}
        avg_tt = 0
        count = 0
        for _, _, data in self.G.edges(data=True):
            s = data.get("status", "open")
            edge_statuses[s] = edge_statuses.get(s, 0) + 1
            tt = data.get("current_travel_time", 0)
            if tt < float('inf'):
                avg_tt += tt
                count += 1

        return {
            "node_statuses": statuses,
            "edge_statuses": edge_statuses,
            "avg_travel_time": round(avg_tt / max(count, 1), 2),
            "total_nodes": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges()
        }
