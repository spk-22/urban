"""
cascade.py
=========================================================
OPTIMIZED URBAN CASCADE ENGINE
FAST VERSION FOR REAL-TIME HOTSPOT SIMULATION
=========================================================
"""

import copy
import math
import random
import statistics
from collections import defaultdict
from itertools import islice

import networkx as nx
import numpy as np


# =========================================================
# ROAD CLASS DEFINITIONS
# =========================================================

ROAD_CLASS_DEFAULTS = {

    "motorway": {
        "speed_kmh": 80,
        "edge_capacity": 4500,
        "node_capacity": 7000
    },

    "trunk": {
        "speed_kmh": 65,
        "edge_capacity": 3500,
        "node_capacity": 5500
    },

    "primary": {
        "speed_kmh": 55,
        "edge_capacity": 2600,
        "node_capacity": 4200
    },

    "secondary": {
        "speed_kmh": 42,
        "edge_capacity": 1800,
        "node_capacity": 3000
    },

    "tertiary": {
        "speed_kmh": 32,
        "edge_capacity": 1200,
        "node_capacity": 1800
    },

    "residential": {
        "speed_kmh": 22,
        "edge_capacity": 600,
        "node_capacity": 900
    },

    "service": {
        "speed_kmh": 15,
        "edge_capacity": 350,
        "node_capacity": 500
    },

    "unclassified": {
        "speed_kmh": 25,
        "edge_capacity": 700,
        "node_capacity": 1000
    }
}

DEFAULT_ROAD = {
    "speed_kmh": 30,
    "edge_capacity": 800,
    "node_capacity": 1200
}

BPR_ALPHA = 0.15
BPR_BETA = 4.0


# =========================================================
# MAIN ENGINE
# =========================================================

class RoadCascadeSimulator:

    def __init__(self, G):

        self.original_graph = G
        self.G = None

        # FAST MODE
        self.num_driver_agents = 250
        self.max_reroute_paths = 2

        self.edge_load_samples = defaultdict(list)
        self.edge_delay_samples = defaultdict(list)

    # =====================================================
    # HELPERS
    # =====================================================

    def _get_road_class(self, data):

        rc = str(
            data.get(
                "road_class",
                data.get("highway", "unclassified")
            )
        ).lower()

        if rc in ("", "none", "n/a"):
            rc = "unclassified"

        return rc

    # =====================================================
    # PREPARE GRAPH
    # =====================================================

    def prepare_graph(
        self,
        baseline_load_range=(0.60, 0.85)
    ):

        self.G = copy.deepcopy(
            self.original_graph
        )

        # -----------------------------
        # NODES
        # -----------------------------

        for node, data in self.G.nodes(data=True):

            rc = self._get_road_class(data)

            defaults = ROAD_CLASS_DEFAULTS.get(
                rc,
                DEFAULT_ROAD
            )

            capacity = defaults["node_capacity"]

            current_load = int(
                capacity * random.uniform(
                    *baseline_load_range
                )
            )

            self.G.nodes[node]["capacity"] = capacity

            self.G.nodes[node]["current_load"] = (
                current_load
            )

            self.G.nodes[node]["status"] = "normal"

            self.G.nodes[node]["queue_pressure"] = (
                current_load / max(capacity, 1)
            )

        # -----------------------------
        # EDGES
        # -----------------------------

        for u, v, data in self.G.edges(data=True):

            rc = self._get_road_class(data)

            defaults = ROAD_CLASS_DEFAULTS.get(
                rc,
                DEFAULT_ROAD
            )

            edge_capacity = defaults["edge_capacity"]

            speed = defaults["speed_kmh"]

            distance = float(
                data.get("weight", 300)
            )

            free_flow = (
                (distance / 1000.0)
                / speed
            ) * 3600

            current_load = int(
                edge_capacity * random.uniform(
                    *baseline_load_range
                )
            )

            travel_time = self._bpr_travel_time(
                free_flow,
                current_load,
                edge_capacity
            )

            self.G.edges[u, v]["capacity"] = (
                edge_capacity
            )

            self.G.edges[u, v]["current_load"] = (
                current_load
            )

            self.G.edges[u, v]["free_flow_time"] = (
                round(free_flow, 2)
            )

            self.G.edges[u, v]["current_travel_time"] = (
                round(travel_time, 2)
            )

            self.G.edges[u, v]["load_ratio"] = (
                current_load / max(edge_capacity, 1)
            )

            self.G.edges[u, v]["status"] = "open"

            self.G.edges[u, v]["road_class"] = rc

        return self.G

    # =====================================================
    # BPR
    # =====================================================

    def _bpr_travel_time(
        self,
        free_flow,
        flow,
        capacity
    ):

        if capacity <= 0:
            return free_flow * 50

        ratio = flow / max(capacity, 1)

        delay = free_flow * (
            1 + BPR_ALPHA * (ratio ** BPR_BETA)
        )

        if ratio >= 1.10:
            delay *= 10

        elif ratio >= 1.0:
            delay *= 4

        elif ratio >= 0.90:
            delay *= 2

        return delay

    # =====================================================
    # BLOCKAGE
    # =====================================================

    def inject_road_blockage(
        self,
        edge,
        cause="accident"
    ):

        if not isinstance(edge, tuple):
            return {
                "error": "Edge must be tuple"
            }

        u, v = edge

        if not self.G.has_edge(u, v):

            return {
                "error": "Edge not found"
            }

        edge_data = self.G.edges[u, v]

        displaced = edge_data.get(
            "current_load",
            0
        )

        edge_data["status"] = "blocked"

        edge_data["capacity"] = 1

        edge_data["current_travel_time"] = (
            float("inf")
        )

        edge_data["load_ratio"] = 99

        return {

            "scenario": "road_blockage",

            "target_id": edge,

            "cause": cause,

            "displaced_traffic": displaced
        }

    # =====================================================
    # REDISTRIBUTION
    # =====================================================

    def stochastic_redistribution(
        self,
        displaced_traffic
    ):

        nodes = list(self.G.nodes())

        if len(nodes) < 10:
            return

        for _ in range(30):

            try:

                src = random.choice(nodes)
                dst = random.choice(nodes)

                if src == dst:
                    continue

                path = nx.shortest_path(
                    self.G,
                    src,
                    dst,
                    weight="current_travel_time"
                )

                traffic = (
                    displaced_traffic / 30
                )

                for i in range(len(path) - 1):

                    u = path[i]
                    v = path[i + 1]

                    if not self.G.has_edge(u, v):
                        continue

                    edge = self.G.edges[u, v]

                    if edge["status"] == "blocked":
                        continue

                    edge["current_load"] += traffic

                    cap = max(
                        edge["capacity"],
                        1
                    )

                    ratio = (
                        edge["current_load"] / cap
                    )

                    edge["load_ratio"] = ratio

                    edge["current_travel_time"] = (
                        self._bpr_travel_time(
                            edge["free_flow_time"],
                            edge["current_load"],
                            cap
                        )
                    )

                    self.edge_load_samples[
                        (u, v)
                    ].append(
                        edge["current_load"]
                    )

                    self.edge_delay_samples[
                        (u, v)
                    ].append(
                        edge["current_travel_time"]
                    )

            except:
                continue

    # =====================================================
    # CASCADE
    # =====================================================

    def propagate_cascade(
        self,
        failure_result,
        max_iterations=5
    ):

        displaced = failure_result.get(
            "displaced_traffic",
            0
        )

        cascade_log = []

        overloaded_nodes = set()

        for iteration in range(max_iterations):

            if displaced <= 20:
                break

            self.stochastic_redistribution(
                displaced
            )

            new_failures = []

            for u, v, edge in self.G.edges(data=True):

                ratio = edge.get(
                    "load_ratio",
                    0
                )

                if ratio >= 1.0:

                    edge["status"] = "critical"

                if ratio >= 1.2:

                    edge["status"] = "failed"

                    new_failures.append(
                        (u, v)
                    )

                    overloaded_nodes.add(u)
                    overloaded_nodes.add(v)

            displaced = len(new_failures) * 150

            cascade_log.append({

                "iteration": iteration + 1,

                "minute": (iteration + 1) * 2,

                "failed_edges": len(
                    new_failures
                ),

                "failed_nodes": len(
                    overloaded_nodes
                ),

                "displaced_traffic": int(
                    displaced
                )
            })

        self.compute_percentile_risk()

        return {

            "iterations": len(cascade_log),

            "cascade_log": cascade_log,

            "total_overloaded": len(
                overloaded_nodes
            ),

            "overloaded_nodes": list(
                overloaded_nodes
            )
        }

    # =====================================================
    # RISK
    # =====================================================

    def compute_percentile_risk(self):

        for (u, v), samples in self.edge_load_samples.items():

            if len(samples) < 2:
                continue

            edge = self.G.edges[u, v]

            edge["risk_97"] = round(
                np.percentile(samples, 97),
                2
            )

        for (u, v), samples in self.edge_delay_samples.items():

            if len(samples) < 2:
                continue

            edge = self.G.edges[u, v]

            edge["delay_97"] = round(
                np.percentile(samples, 97),
                2
            )

    # =====================================================
    # ROUTES
    # =====================================================

    def find_alternate_routes(
        self,
        source,
        target,
        k=2
    ):

        routes = []

        try:

            paths = nx.shortest_simple_paths(
                self.G,
                source,
                target,
                weight="current_travel_time"
            )

            for path in islice(paths, k):

                total_time = 0

                for i in range(len(path) - 1):

                    u = path[i]
                    v = path[i + 1]

                    total_time += (
                        self.G.edges[u, v].get(
                            "current_travel_time",
                            0
                        )
                    )

                routes.append({

                    "path": path,

                    "hops": len(path) - 1,

                    "total_time": round(
                        total_time,
                        2
                    )
                })

        except:
            pass

        return {
            "routes": routes
        }

    # =====================================================
    # SIMULATE
    # =====================================================

    def simulate_scenario(
        self,
        scenario_type,
        target_id,
        cause
    ):

        self.prepare_graph()

        if scenario_type == "road_blockage":

            failure = self.inject_road_blockage(
                target_id,
                cause
            )

        else:

            return {
                "error": "Unsupported scenario"
            }

        cascade = self.propagate_cascade(
            failure
        )

        return {

            "scenario": scenario_type,

            "cause": cause,

            "failure_details": failure,

            "cascade": cascade,

            "graph": self.G
        }