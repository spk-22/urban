# Road Network Cascade Failure Detection — Bengaluru

## Background & Core Principle

> **A node is NOT failed because it disappears from the graph.**
> **A node fails when it can no longer perform its real-world function — vehicles cannot effectively pass through it.**

This system models **capacity-based cascades**, not disconnection-based ones. Bengaluru roads rarely become fully disconnected. Instead:
- Travel time explodes
- Congestion propagates from failed/overloaded nodes to neighbours

---

## Existing Codebase

| File | Role |
|------|------|
| [road.py](file:///d:/urban%20el/backend/graph/road.py) | `RoadGraphBuilder` — builds graph from XLSX + GeoJSON, saves GraphML, creates HTML/PNG maps |
| [app.py](file:///d:/urban%20el/backend/app.py) | Flask API — upload routes for XML/GeoJSON |
| [chkgraphconnected.py](file:///d:/urban%20el/backend/chkgraphconnected.py) | Basic connectivity analysis |

The existing graph has nodes with `latitude`, `longitude`, `road_type`, `highway_type`, `importance` and edges with `weight` (distance in meters), `road_name`, `road_class`.

**What's missing:** capacity attributes, failure simulation, congestion propagation, alternate routing.

---

## Proposed Changes

### Component 1: Enhanced Road Graph with Capacity

#### [MODIFY] [road.py](file:///d:/urban%20el/backend/graph/road.py)

Add capacity and flow attributes to every node and edge when building the graph:

**Node attributes to add:**
- `capacity` — max vehicles/hour (derived from `road_class` / `highway_type`)
- `current_load` — current vehicles/hour (initialized via random realistic % of capacity)
- `load_ratio` — `current_load / capacity` (0.0–1.0+)
- `node_type` — `junction | signal | roundabout | flyover | interchange` (inferred or defaulted)
- `status` — `normal | degraded | failed`

**Edge attributes to add:**
- `capacity` — max vehicles/hour for the road segment
- `current_load` — current flow
- `free_flow_time` — travel time at zero congestion (distance / speed_limit)
- `current_travel_time` — travel time under current load (BPR formula)
- `status` — `open | congested | blocked`

**Speed/capacity mapping by road class:**

| Road Class | Speed (km/h) | Capacity (veh/hr) | Node Capacity |
|------------|--------------|-------------------|---------------|
| motorway | 80 | 4000 | 6000 |
| trunk | 60 | 3000 | 4500 |
| primary | 50 | 2000 | 3500 |
| secondary | 40 | 1500 | 2500 |
| tertiary | 30 | 1000 | 1500 |
| residential | 20 | 500 | 800 |
| default | 30 | 800 | 1200 |

**Travel time model:** BPR (Bureau of Public Roads) formula:
```
t = t_free × [1 + α × (flow/capacity)^β]
where α = 0.15, β = 4.0
```

---

### Component 2: Cascade Failure Simulator

#### [NEW] [cascade.py](file:///d:/urban%20el/backend/graph/cascade.py)

A new module `RoadCascadeSimulator` containing:

##### 2a. Three Failure Scenario Injectors

1. **`inject_road_blockage(node_or_edge, cause)`**
   - Sets edge `status = "blocked"`, `capacity = 0`
   - Redistributes traffic from blocked road to neighbouring edges
   - Cause can be: `accident | flooding | construction | protest | fallen_tree`

2. **`inject_signal_failure(node_id, cause)`**
   - Reduces node capacity by 60-70%
   - Sets `status = "degraded"`
   - Increases `current_travel_time` of all adjacent edges (throughput drops)
   - Cause: `power_outage | controller_malfunction`

3. **`inject_flyover_closure(edge_id, cause)`**
   - Sets the flyover edge `status = "blocked"`, `capacity = 0`
   - All traffic must use ground-level alternatives
   - Cause: `structural_issue | maintenance`

##### 2b. Capacity-Based Cascade Propagation Engine

**Algorithm: Iterative Congestion Propagation**

```
1. Inject failure (set node/edge capacity to 0 or reduced)
2. Identify displaced traffic volume
3. For each iteration (max ~10 rounds):
   a. Find all edges/nodes receiving redistributed traffic
   b. Recalculate load_ratio for each
   c. If load_ratio > 1.0 → node is "overloaded"
      - Mark status = "degraded" or "failed"
      - Excess traffic spills to NEXT neighbours
   d. Recalculate travel times using BPR formula
   e. If no new overloads → stop (equilibrium reached)
4. Return cascade report
```

Key design decisions:
- Traffic redistributes proportionally to remaining capacity of alternative edges
- A node with `load_ratio > 0.9` is "congested", `> 1.0` is "overloaded"
- Overloaded nodes reduce their effective capacity by 20% (modelling gridlock), pushing more traffic outward

##### 2c. Alternate Route Finder with Congestion Awareness

**`find_alternate_routes(source, destination, num_routes=3)`**

Uses a **congestion-weighted shortest path**:
- Edge weight = `current_travel_time` (NOT distance)
- Uses Yen's K-shortest paths algorithm
- For each route returned:
  - Total travel time
  - List of congested segments (edges with `load_ratio > 0.8`)
  - Congestion score (average `load_ratio` across route)
  - Label: `clear | moderate | congested | avoid`

**Route selection logic:**
- Filter out routes passing through `blocked` edges
- Rank by congestion score (lowest = best)
- If all routes congested, report "no clear alternate"

##### 2d. Junction Overload Detector

**`detect_overloaded_junctions(threshold=0.85)`**

- Scans all junction nodes
- Returns list sorted by `load_ratio` descending:
  - Junction ID, name, lat/lon
  - `load_ratio`
  - Number of incoming edges over capacity
  - List of affected connecting road names
  - Severity: `warning (0.85-0.95) | critical (0.95-1.0) | failed (>1.0)`

##### 2e. Simulation Runner

**`simulate_scenario(scenario_type, target, cause)`**

End-to-end pipeline:
1. Clone the current graph state
2. Inject the failure
3. Run cascade propagation
4. Detect overloaded junctions
5. Find alternate routes for affected OD pairs
6. Generate report + visualization

---

### Component 3: Worked Example — Silk Board Junction Simulation

#### [NEW] [simulate_bengaluru.py](file:///d:/urban%20el/backend/simulate_bengaluru.py)

A standalone script that:

1. **Creates a realistic Bengaluru sub-network** (synthetic but based on real topology):
   - ~30 junctions covering the Silk Board → Marathahalli → KR Puram corridor
   - Named roads: Outer Ring Road, Hosur Road, Sarjapur Road, etc.
   - Realistic capacities and baseline loads

2. **Runs all 3 failure scenarios** on this network:
   - **Scenario 1:** Accident blocking Outer Ring Road between Silk Board and HSR Layout
   - **Scenario 2:** Signal failure at Silk Board Junction
   - **Scenario 3:** Flyover closure at Hebbal

3. **For each scenario outputs:**
   - Before/after congestion state
   - Cascade propagation trace (which junctions overloaded, in what order)
   - Alternate routes with congestion ratings
   - List of overloaded junctions with severity

---

### Component 4: Interactive Visualization

#### [NEW] [cascade_visualizer.py](file:///d:/urban%20el/backend/graph/cascade_visualizer.py)

Generates a Folium HTML map showing:

- **Nodes colour-coded by status:**
  - 🟢 Green — Normal (load < 0.6)
  - 🟡 Yellow — Moderate (0.6 - 0.85)
  - 🟠 Orange — Congested (0.85 - 0.95)
  - 🔴 Red — Critical (0.95 - 1.0)
  - ⚫ Black — Failed (>1.0 or blocked)

- **Edges colour-coded by congestion:**
  - Green → Yellow → Orange → Red → Black gradient

- **Popups showing:**
  - Node: name, capacity, current load, load ratio, status
  - Edge: road name, capacity, current flow, travel time, status

- **Layer controls:**
  - Toggle: normal state / post-failure state
  - Show/hide alternate routes (highlighted in blue)
  - Show/hide cascade propagation order (numbered markers)

- **Legend** with colour meanings

---

### Component 5: Flask API Endpoints

#### [MODIFY] [app.py](file:///d:/urban%20el/backend/app.py)

Add new API routes:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulate/road-blockage` | POST | Inject road blockage, run cascade, return results |
| `/simulate/signal-failure` | POST | Inject signal failure, run cascade |
| `/simulate/flyover-closure` | POST | Inject flyover closure, run cascade |
| `/junctions/overloaded` | GET | List all currently overloaded junctions |
| `/routes/alternate` | POST | Find congestion-aware alternate routes |
| `/simulate/bengaluru-demo` | GET | Run the pre-built Silk Board demo |

---

## Open Questions

> [!IMPORTANT]
> **Data Source**: The current road graph is built from OSM XML/GeoJSON uploads. For the demo simulation, I'll create a **synthetic but realistic Bengaluru sub-network** with named junctions and roads. Should I also modify the existing `RoadGraphBuilder` to automatically assign capacity attributes when building from real OSM data?

> [!IMPORTANT]
> **Traffic Load Initialization**: For the demo, I'll initialize baseline traffic at ~50-70% of capacity (typical Bengaluru peak). Should the system also support loading real traffic data from an external source later?

---

## Verification Plan

### Automated Tests
1. Run `simulate_bengaluru.py` standalone — verify all 3 scenarios produce cascade reports
2. Start Flask app, hit `/simulate/bengaluru-demo` — verify JSON response with cascade data
3. Open generated HTML map — verify colour-coded visualization with cascades visible

### Manual Verification
- Open the Folium HTML maps in browser to visually confirm:
  - Failure point marked correctly
  - Congestion spreading to neighbouring junctions
  - Alternate routes highlighted
  - Junction overload indicators accurate
