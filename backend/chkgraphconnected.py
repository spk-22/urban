"""
road_network_analyzer.py
=========================================
AUTO LOADS:
data/graphs/road_network.graphml

ROAD GRAPH ANALYSIS REPORT
=========================================
"""

from pathlib import Path
import networkx as nx


class RoadNetworkAnalyzer:
    def __init__(self):
        # =====================================
        # AUTO PATH DETECTION
        # =====================================
        BASE_DIR = Path(__file__).resolve().parents[2]

        self.graphml_path = (
            BASE_DIR /"blore_utility_ntwk" / "data" / "graphs" / "water_network.graphml"
        )

        if not self.graphml_path.exists():
            raise FileNotFoundError(
                f"GraphML file not found:\n{self.graphml_path}"
            )

        print(f"Loading graph from:\n{self.graphml_path}")

        # =====================================
        # LOAD GRAPH
        # =====================================
        self.G = nx.read_graphml(self.graphml_path)

        print("Graph loaded successfully.")

    # =====================================
    # BASIC METRICS
    # =====================================
    def get_basic_metrics(self):
        total_nodes = self.G.number_of_nodes()
        total_edges = self.G.number_of_edges()

        is_connected = nx.is_connected(self.G)

        connected_components = list(
            nx.connected_components(self.G)
        )

        num_components = len(connected_components)

        largest_component_size = max(
            len(component)
            for component in connected_components
        )

        density = nx.density(self.G)

        avg_degree = (
            sum(dict(self.G.degree()).values()) / total_nodes
            if total_nodes > 0
            else 0
        )

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "is_connected": is_connected,
            "num_components": num_components,
            "largest_component_size": largest_component_size,
            "density": density,
            "avg_degree": avg_degree
        }

    # =====================================
    # TOP CRITICAL NODES
    # =====================================
    def get_top_critical_nodes(self, top_n=5):
        degree_sorted = sorted(
            self.G.degree(),
            key=lambda x: x[1],
            reverse=True
        )

        critical_nodes = []

        for node_id, degree in degree_sorted[:top_n]:
            attrs = self.G.nodes[node_id]

            category = (
                attrs.get("highway_type")
                or attrs.get("road_type")
                or attrs.get("importance")
                or "road_node"
            )

            critical_nodes.append({
                "node_id": node_id,
                "connections": degree,
                "category": category
            })

        return critical_nodes

    # =====================================
    # REPORT
    # =====================================
    def generate_report(self):
        metrics = self.get_basic_metrics()
        critical_nodes = self.get_top_critical_nodes()

        print("\n==============================")
        print(" ROAD NETWORK ANALYSIS REPORT ")
        print("==============================")

        print(f"Total Nodes: {metrics['total_nodes']}")
        print(f"Total Edges: {metrics['total_edges']}")
        print(f"Is Graph Fully Connected? {metrics['is_connected']}")
        print(
            f"Number of Connected Components: "
            f"{metrics['num_components']}"
        )
        print(
            f"Size of Largest Component: "
            f"{metrics['largest_component_size']} nodes"
        )

        print("\nTop 5 Most Critical Road Nodes (by Degree):")

        for idx, node in enumerate(critical_nodes, start=1):
            print(
                f"{idx}. {node['node_id']} | "
                f"Connections: {node['connections']} | "
                f"Category: {node['category']}"
            )

        print(f"\nNetwork Density: {metrics['density']:.6f}")
        print(
            f"Average Connections per Node: "
            f"{metrics['avg_degree']:.2f}"
        )

        return {
            "metrics": metrics,
            "critical_nodes": critical_nodes
        }


# =====================================
# MAIN
# =====================================
def main():
    analyzer = RoadNetworkAnalyzer()
    analyzer.generate_report()


if __name__ == "__main__":
    main()