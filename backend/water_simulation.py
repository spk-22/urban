"""
water_simulation.py
=========================================
WATER NETWORK CASCADE FAILURE SIMULATOR
=========================================
Standalone Flask module for water infrastructure
supply-stress propagation simulation.

Completely independent from road cascade system.
Run: python water_simulation.py
Visit: http://localhost:5001/water/ui
=========================================
"""

import os
import copy
import random
import networkx as nx
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string

# =========================================
# PATHS
# =========================================
BASE_DIR = Path(__file__).resolve().parents[1]
GRAPH_DIR = BASE_DIR / "data" / "graphs"
WATER_GRAPH_PATH = GRAPH_DIR / "water_network.graphml"

# =========================================
# WATER NODE TYPE CLASSIFIER
# =========================================
SUPPLY_KEYWORDS = ["water_works", "water works", "bwssb", "pumping", "treatment", "supply", "source"]
STORAGE_KEYWORDS = ["reservoir", "tank", "storage", "cistern", "basin"]
DEMAND_KEYWORDS = ["water_tank", "water tank", "tap", "consumer", "demand", "service"]


def classify_node(data):
    """Auto-detect node type from attributes."""
    searchable = " ".join(str(v).lower() for v in data.values())
    if any(kw in searchable for kw in SUPPLY_KEYWORDS):
        return "supply"
    if any(kw in searchable for kw in STORAGE_KEYWORDS):
        return "storage"
    if any(kw in searchable for kw in DEMAND_KEYWORDS):
        return "demand"
    return "junction"


# =========================================
# WATER CASCADE SIMULATOR
# =========================================
class WaterCascadeSimulator:

    def __init__(self, graph_path=None):
        path = graph_path or WATER_GRAPH_PATH
        if not Path(path).exists():
            raise FileNotFoundError(f"Water graph not found: {path}")
        self.original = nx.read_graphml(str(path))
        self.G = None

    def prepare(self):
        self.G = copy.deepcopy(self.original)
        bet = nx.betweenness_centrality(self.G)
        deg = dict(self.G.degree())
        max_deg = max(deg.values()) if deg else 1
        max_bet = max(bet.values()) if bet else 1

        # Sort by betweenness to identify hubs
        sorted_by_bet = sorted(bet.items(), key=lambda x: x[1], reverse=True)
        top_hubs = {n for n, _ in sorted_by_bet[:max(3, len(sorted_by_bet) // 10)]}

        for node, data in self.G.nodes(data=True):
            node_deg = deg.get(node, 0)
            node_bet = bet.get(node, 0)

            # Role assignment based on graph position (not just labels)
            if node_deg <= 1:
                # Endpoint = true supply source
                role = "supply"
                cap = 1000
                demand = random.randint(80, 200)
            elif node in top_hubs:
                # High-betweenness hub = distribution junction (stressed)
                role = "distribution"
                cap = random.randint(500, 800)
                demand = int(cap * random.uniform(0.85, 0.98))
            else:
                # Interior chain node = pipeline segment (fragile)
                role = "pipeline"
                cap = random.randint(300, 600)
                demand = int(cap * random.uniform(0.82, 0.96))

            self.G.nodes[node]["water_type"] = role
            self.G.nodes[node]["capacity"] = cap
            self.G.nodes[node]["demand"] = demand
            self.G.nodes[node]["inflow"] = cap
            self.G.nodes[node]["stress"] = round(demand / max(cap, 1), 4)
            self.G.nodes[node]["status"] = "stable"
            self.G.nodes[node]["score"] = round(
                0.6 * (node_bet / max(max_bet, 0.001)) + 0.4 * (node_deg / max_deg), 4
            )

    def pick_failure_node(self, scenario):
        targets = []
        for n, d in self.G.nodes(data=True):
            wt = d.get("water_type", "pipeline")
            if scenario == "WATER_WORKS_FAILURE" and wt == "distribution":
                targets.append((n, d.get("score", 0)))
            elif scenario == "RESERVOIR_FAILURE" and wt == "pipeline":
                targets.append((n, d.get("score", 0)))
            elif scenario == "TANK_FAILURE" and wt == "supply":
                targets.append((n, d.get("score", 0)))
        if not targets:
            # Fallback: pick highest-score node
            all_nodes = [(n, d.get("score", 0)) for n, d in self.G.nodes(data=True)]
            all_nodes.sort(key=lambda x: x[1], reverse=True)
            return all_nodes[0][0] if all_nodes else None
        targets.sort(key=lambda x: x[1], reverse=True)
        return targets[0][0]

    def simulate(self, scenario, max_steps=20):
        self.prepare()
        seed = self.pick_failure_node(scenario)
        if seed is None:
            return {"error": "No suitable failure node found"}

        # Kill the seed node — pipeline break
        self.G.nodes[seed]["status"] = "failed"
        self.G.nodes[seed]["inflow"] = 0
        self.G.nodes[seed]["stress"] = 99.0

        failed = {seed}
        timeline = []

        # In a pipeline (chain), a break physically cuts the line.
        # Water can't flow past a failed node.
        # Cascade = BFS outward from break, each hop gets weaker residual pressure.
        # Decay per scenario determines how far the cascade reaches.
        if scenario == "WATER_WORKS_FAILURE":
            decay_per_hop = 0.15  # Severe — supply source gone
        elif scenario == "RESERVOIR_FAILURE":
            decay_per_hop = 0.25  # Moderate — buffer lost
        else:
            decay_per_hop = 0.45  # Localized — demand node only

        for step in range(1, max_steps + 1):
            new_failures = set()

            for node in list(self.G.nodes()):
                if node in failed:
                    continue

                neighbors = list(self.G.neighbors(node))
                if not neighbors:
                    continue

                failed_neighbors = [nb for nb in neighbors if nb in failed]
                if not failed_neighbors:
                    continue

                # Pipeline is broken on the failed-neighbor side.
                # Residual inflow = base capacity * decay^(distance from break)
                # Since we process one hop per step, use cumulative decay
                active_neighbors = [nb for nb in neighbors if nb not in failed]

                if not active_neighbors:
                    # All neighbors failed — node is completely cut off
                    inflow = 0
                else:
                    # Partial supply from surviving side, heavily reduced
                    surviving_supply = sum(
                        self.G.nodes[nb].get("inflow", 0) for nb in active_neighbors
                    )
                    inflow = int(surviving_supply * decay_per_hop)

                base_cap = self.G.nodes[node]["capacity"]
                inflow = min(inflow, base_cap)
                self.G.nodes[node]["inflow"] = inflow
                demand = self.G.nodes[node]["demand"]
                stress = demand / max(inflow, 1)
                self.G.nodes[node]["stress"] = round(stress, 4)

                # Failure: no inflow or demand far exceeds supply
                if inflow == 0 or stress > 1.1:
                    new_failures.add(node)
                    self.G.nodes[node]["status"] = "failed"
                    self.G.nodes[node]["inflow"] = 0
                    self.G.nodes[node]["stress"] = 99.0
                elif stress > 0.7:
                    self.G.nodes[node]["status"] = "stressed"
                else:
                    self.G.nodes[node]["status"] = "stable"

            timeline.append({
                "step": step,
                "new_failures": len(new_failures),
                "total_failed": len(failed) + len(new_failures),
                "nodes": list(new_failures)
            })

            if not new_failures:
                break
            failed.update(new_failures)

        total = self.G.number_of_nodes()
        node_details = []
        critical = []
        for n, d in self.G.nodes(data=True):
            entry = {
                "id": n,
                "name": d.get("name", n),
                "water_type": d.get("water_type", "junction"),
                "status": d.get("status", "stable"),
                "stress": round(d.get("stress", 0), 2),
                "inflow": d.get("inflow", 0),
                "demand": d.get("demand", 0),
                "capacity": d.get("capacity", 0),
                "lat": d.get("latitude", ""),
                "lon": d.get("longitude", "")
            }
            node_details.append(entry)
            if d.get("score", 0) > 0.3 and d["status"] != "failed":
                critical.append(n)

        return {
            "scenario": scenario,
            "seed_node": seed,
            "seed_name": self.G.nodes[seed].get("name", seed),
            "total_nodes": total,
            "failed_nodes": list(failed),
            "failed_count": len(failed),
            "cascade_steps": len(timeline),
            "affected_percentage": round(len(failed) / max(total, 1) * 100, 2),
            "critical_nodes": critical[:10],
            "timeline": timeline,
            "node_details": node_details
        }


# =========================================
# FLASK APP
# =========================================
water_app = Flask(__name__)

# =========================================
# API ENDPOINT
# =========================================
@water_app.route("/water/simulate", methods=["POST"])
def water_simulate():
    try:
        data = request.json or {}
        scenario = data.get("scenario", "WATER_WORKS_FAILURE")
        sim = WaterCascadeSimulator()
        result = sim.simulate(scenario)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================
# UI PAGE
# =========================================
WATER_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Water Network Cascade Simulator</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Outfit',sans-serif;background:#0a0e1a;color:#e2e8f0;min-height:100vh}
.glass{background:rgba(15,23,42,.75);backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.08);border-radius:16px}
nav{padding:18px 32px;border-bottom:1px solid rgba(255,255,255,.06);position:sticky;top:0;z-index:50;background:rgba(10,14,26,.9);backdrop-filter:blur(16px)}
nav .brand{display:flex;align-items:center;gap:10px}
nav .brand i{font-size:28px;color:#38bdf8}
nav h1{font-size:22px;font-weight:700}
nav h1 span{color:#38bdf8}
.badge{padding:4px 14px;font-size:11px;border-radius:9999px;font-weight:700;text-transform:uppercase;letter-spacing:2px}
.badge-blue{background:rgba(56,189,248,.15);color:#38bdf8;border:1px solid rgba(56,189,248,.3)}
main{max-width:1400px;margin:0 auto;padding:32px 24px;display:grid;grid-template-columns:320px 1fr;gap:28px}
@media(max-width:900px){main{grid-template-columns:1fr}}
.sidebar{display:flex;flex-direction:column;gap:16px}
.sidebar h2{font-size:17px;font-weight:600;display:flex;align-items:center;gap:8px;margin-bottom:4px}
.scenario-btn{width:100%;padding:16px 20px;border:none;border-radius:14px;cursor:pointer;text-align:left;font-family:inherit;font-size:14px;font-weight:600;transition:all .25s;display:flex;align-items:center;gap:14px;border:1px solid transparent}
.scenario-btn:hover{transform:translateY(-2px)}
.btn-works{background:rgba(239,68,68,.12);color:#fca5a5;border-color:rgba(239,68,68,.25)}
.btn-works:hover{background:rgba(239,68,68,.22);border-color:#ef4444}
.btn-reservoir{background:rgba(251,191,36,.12);color:#fde68a;border-color:rgba(251,191,36,.25)}
.btn-reservoir:hover{background:rgba(251,191,36,.22);border-color:#f59e0b}
.btn-tank{background:rgba(34,197,94,.12);color:#86efac;border-color:rgba(34,197,94,.25)}
.btn-tank:hover{background:rgba(34,197,94,.22);border-color:#22c55e}
.btn-icon{font-size:22px}
.btn-text small{display:block;font-weight:400;font-size:12px;opacity:.7;margin-top:2px}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
@media(max-width:700px){.stats-grid{grid-template-columns:repeat(2,1fr)}}
.stat-card{padding:16px;text-align:center;border-radius:14px}
.stat-card .label{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#94a3b8;margin-bottom:6px}
.stat-card .value{font-size:26px;font-weight:700}
.content{display:flex;flex-direction:column;gap:20px}
.placeholder{height:500px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#475569;border-radius:16px;border:1px dashed rgba(255,255,255,.08)}
.placeholder i{font-size:56px;margin-bottom:16px;opacity:.2}
.loader{display:none;position:absolute;inset:0;background:rgba(10,14,26,.85);z-index:10;border-radius:16px;flex-direction:column;align-items:center;justify-content:center}
.loader.active{display:flex}
.loader i{font-size:36px;color:#38bdf8;margin-bottom:12px}
.timeline-panel{max-height:180px;overflow-y:auto;padding:16px;font-size:13px}
.timeline-panel::-webkit-scrollbar{width:4px}
.timeline-panel::-webkit-scrollbar-thumb{background:#334155;border-radius:4px}
.tl-step{padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04);display:block;}
.tl-step:last-child{border:none}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:10px 12px;background:rgba(255,255,255,.04);color:#94a3b8;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:1px;position:sticky;top:0}
td{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.03)}
.node-table-wrap{max-height:400px;overflow-y:auto;border-radius:14px}
.node-table-wrap::-webkit-scrollbar{width:4px}
.node-table-wrap::-webkit-scrollbar-thumb{background:#334155;border-radius:4px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
.dot-failed{background:#ef4444}
.dot-stressed{background:#f59e0b}
.dot-stable{background:#22c55e}
.search-box{width:100%;padding:10px 14px;border-radius:10px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);color:#e2e8f0;font-family:inherit;font-size:13px;margin-bottom:12px;outline:none}
.search-box:focus{border-color:#38bdf8}
.hidden{display:none!important}
.sys-status{font-size:13px;padding:4px 12px;border-radius:8px;font-weight:600}
.sys-ok{background:rgba(34,197,94,.15);color:#86efac}
.sys-warn{background:rgba(251,191,36,.15);color:#fde68a}
.sys-crit{background:rgba(239,68,68,.15);color:#fca5a5}
.anim-bar{height:6px;border-radius:3px;background:rgba(255,255,255,.06);overflow:hidden;margin-top:8px}
.anim-bar-fill{height:100%;border-radius:3px;transition:width 1s ease}
</style>
</head>
<body>
<nav>
<div style="display:flex;justify-content:space-between;align-items:center;max-width:1400px;margin:0 auto">
  <div class="brand"><i class="fas fa-water"></i><h1>Aqua<span>Cascade</span></h1></div>
  <div style="display:flex;align-items:center;gap:12px">
    <span class="badge badge-blue"><i class="fas fa-tint"></i>&nbsp; Water Network</span>
    <span style="color:#64748b;font-size:13px">Bengaluru, IN</span>
  </div>
</div>
</nav>

<main>
  <div class="sidebar">
    <h2><i class="fas fa-bolt" style="color:#f59e0b"></i> Failure Scenarios</h2>

    <button class="scenario-btn btn-works" onclick="runSim('WATER_WORKS_FAILURE')">
      <span class="btn-icon">🏭</span>
      <span class="btn-text">Water Works Failure<small>Global supply disruption</small></span>
    </button>

    <button class="scenario-btn btn-reservoir" onclick="runSim('RESERVOIR_FAILURE')">
      <span class="btn-icon">🏗️</span>
      <span class="btn-text">Reservoir Failure<small>Storage buffer collapse</small></span>
    </button>

    <button class="scenario-btn btn-tank" onclick="runSim('TANK_FAILURE')">
      <span class="btn-icon">🪣</span>
      <span class="btn-text">Tank Failure<small>Local demand-side failure</small></span>
    </button>

    <div class="glass" style="padding:16px;margin-top:8px">
      <h2 style="font-size:14px;margin-bottom:10px"><i class="fas fa-info-circle" style="color:#38bdf8"></i> Model Info</h2>
      <p style="font-size:12px;color:#94a3b8;line-height:1.6">
        Water networks use <b>supply-stress propagation</b>, not traffic routing.
        Nodes fail when upstream inflow drops to zero or stress exceeds threshold.
        Storage nodes act as buffers delaying cascade.
      </p>
    </div>
  </div>

  <div class="content">
    <div id="stats" class="stats-grid hidden">
      <div class="stat-card glass"><p class="label">Total Nodes</p><p class="value" id="s-total">-</p></div>
      <div class="stat-card glass" style="border-left:3px solid #ef4444"><p class="label">Failed</p><p class="value" id="s-failed" style="color:#fca5a5">-</p></div>
      <div class="stat-card glass"><p class="label">Cascade Steps</p><p class="value" id="s-steps" style="color:#38bdf8">-</p></div>
      <div class="stat-card glass"><p class="label">System Status</p><p id="s-status" class="sys-status sys-ok">—</p>
        <div class="anim-bar"><div id="impact-bar" class="anim-bar-fill" style="width:0%;background:linear-gradient(90deg,#22c55e,#f59e0b,#ef4444)"></div></div>
      </div>
    </div>

    <div id="placeholder" class="placeholder glass">
      <i class="fas fa-faucet-drip"></i>
      <p>Select a failure scenario to begin simulation</p>
    </div>

    <div id="loader" class="loader glass">
      <i class="fas fa-spinner fa-spin"></i>
      <p style="color:#38bdf8;font-weight:500">Running cascade simulation...</p>
    </div>

    <div id="timeline-wrap" class="glass hidden">
      <h3 style="padding:14px 16px 0;font-size:15px;font-weight:600"><i class="fas fa-clock" style="color:#38bdf8"></i> Cascade Timeline</h3>
      <div id="timeline" class="timeline-panel"></div>
    </div>

    <div id="table-wrap" class="glass hidden" style="padding:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h3 style="font-size:15px;font-weight:600"><i class="fas fa-table" style="color:#38bdf8"></i> Node Status</h3>
        <select id="filter" onchange="applyFilter()" style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:#e2e8f0;padding:6px 10px;border-radius:8px;font-family:inherit;font-size:12px">
          <option value="all">All</option>
          <option value="failed">Failed</option>
          <option value="stressed">Stressed</option>
          <option value="stable">Stable</option>
        </select>
      </div>
      <input type="text" class="search-box" id="search" placeholder="Search by name or ID..." oninput="applyFilter()">
      <div class="node-table-wrap">
        <table><thead><tr><th>Status</th><th>ID</th><th>Name</th><th>Type</th><th>Stress</th><th>Inflow</th><th>Demand</th></tr></thead>
        <tbody id="tbody"></tbody></table>
      </div>
    </div>
  </div>
</main>

<script>
let allNodes = [];

async function runSim(scenario) {
  document.getElementById('placeholder').classList.add('hidden');
  document.getElementById('loader').classList.add('active');
  document.getElementById('stats').classList.add('hidden');
  document.getElementById('timeline-wrap').classList.add('hidden');
  document.getElementById('table-wrap').classList.add('hidden');

  try {
    const res = await fetch('/water/simulate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({scenario})
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    renderResults(data);
  } catch(e) {
    alert('Simulation failed: ' + e.message);
    document.getElementById('placeholder').classList.remove('hidden');
  } finally {
    document.getElementById('loader').classList.remove('active');
  }
}

function renderResults(data) {
  document.getElementById('stats').classList.remove('hidden');
  document.getElementById('s-total').textContent = data.total_nodes;
  document.getElementById('s-failed').textContent = data.failed_count;
  document.getElementById('s-steps').textContent = data.cascade_steps;

  const pct = data.affected_percentage;
  const bar = document.getElementById('impact-bar');
  bar.style.width = Math.min(pct, 100) + '%';

  const st = document.getElementById('s-status');
  if (pct > 50) { st.textContent = 'CRITICAL'; st.className = 'sys-status sys-crit'; }
  else if (pct > 20) { st.textContent = 'WARNING'; st.className = 'sys-status sys-warn'; }
  else { st.textContent = 'STABLE'; st.className = 'sys-status sys-ok'; }

  // Table data parsed first for ID -> Name mapping
  allNodes = data.node_details || [];
  const nodeMap = {};
  allNodes.forEach(n => nodeMap[n.id] = n.name || n.id);

  // Timeline
  const tlWrap = document.getElementById('timeline-wrap');
  const tl = document.getElementById('timeline');
  tlWrap.classList.remove('hidden');
  
  let tlHtml = `<div class="tl-step" style="border-left: 3px solid #ef4444; padding-left: 10px; margin-bottom: 8px;">
    <div style="font-size:11px; text-transform:uppercase; color:#ef4444; font-weight:700; letter-spacing:1px; margin-bottom:2px;"><i class="fas fa-bullseye"></i> Root Cause</div>
    <div style="color:#e2e8f0; font-size:14px; font-weight:600;">${data.seed_name} <span style="color:#64748b; font-size:12px; font-weight:400;">(${data.seed_node})</span></div>
  </div>`;
  
  tlHtml += data.timeline.map(t => {
    const failedNames = t.nodes.map(id => nodeMap[id] || id).join(', ');
    return `<div class="tl-step">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
        <span style="font-weight:600; color:#38bdf8;">Step ${t.step} <span style="color:#64748b; font-size:11px; font-weight:400;">(${t.total_failed} total)</span></span>
        <span style="color:#fca5a5; font-size:12px; font-weight:600;">+${t.new_failures} failed</span>
      </div>
      <div style="color:#94a3b8; font-size:12px; line-height:1.4;">
        <span style="opacity:0.7;">Propagated to:</span> <span style="color:#cbd5e1;">${failedNames}</span>
      </div>
    </div>`;
  }).join('');
  
  tl.innerHTML = tlHtml;

  // Table display
  document.getElementById('table-wrap').classList.remove('hidden');
  document.getElementById('filter').value = 'all';
  document.getElementById('search').value = '';
  renderTable(allNodes);
}

function renderTable(nodes) {
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = nodes.map(n => {
    const dotClass = n.status === 'failed' ? 'dot-failed' : n.status === 'stressed' ? 'dot-stressed' : 'dot-stable';
    return `<tr><td><span class="dot ${dotClass}"></span>${n.status}</td><td>${n.id}</td><td>${n.name}</td><td>${n.water_type}</td><td>${n.stress.toFixed(2)}</td><td>${n.inflow}</td><td>${n.demand}</td></tr>`;
  }).join('');
}

function applyFilter() {
  const f = document.getElementById('filter').value;
  const q = document.getElementById('search').value.toLowerCase();
  let filtered = allNodes;
  if (f !== 'all') filtered = filtered.filter(n => n.status === f);
  if (q) filtered = filtered.filter(n => n.id.toLowerCase().includes(q) || (n.name||'').toLowerCase().includes(q));
  renderTable(filtered);
}
</script>
</body>
</html>
"""


@water_app.route("/water/ui")
def water_ui():
    return render_template_string(WATER_UI_HTML)


# =========================================
# STANDALONE RUN
# =========================================
if __name__ == "__main__":
    print("=" * 50)
    print("  WATER CASCADE SIMULATOR")
    print(f"  Graph: {WATER_GRAPH_PATH}")
    print(f"  UI:    http://localhost:5001/water/ui")
    print("=" * 50)
    water_app.run(port=5001, debug=True)
