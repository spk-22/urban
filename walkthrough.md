# Walkthrough: Bengaluru Road Cascade Failure Detection

We have successfully implemented a **capacity-based cascade failure detection system** for the Bengaluru road network. 

## 🚀 Key Achievements

- **Capacity-Based Modeling**: Moved beyond simple graph disconnection to real-world congestion modeling using the **BPR (Bureau of Public Roads) formula**.
- **Cascade Engine**: Implemented an iterative engine that propagates congestion when a node or edge fails.
- **Probabilistic Rerouting**: Traffic is redistributed across the **K-Shortest Paths** based on travel time and congestion, mimicking real driver behavior.
- **Interactive Visualizations**: Generated Folium-based maps that show congestion propagation with a color-coded legend.

## 📊 Simulation Scenarios

We ran three critical scenarios on a synthetic but realistic model of the **Silk Board → Marathahalli corridor**:

### 1. Road Blockage (Accident on ORR)
- **Cause**: Major accident between Agara and Iblur.
- **Effect**: Traffic diverted to HSR interior roads and Sarjapur road.
- **Result**: Significant congestion increase on secondary roads.

### 2. Signal Failure (Silk Board)
- **Cause**: Power outage at Silk Board Junction.
- **Effect**: Junction capacity dropped by ~65%, creating massive backlogs on Hosur Road and ORR.
- **Result**: Cascade effect spreading to HSR Layout entrance.

### 3. Flyover Closure (Bellandur)
- **Cause**: Structural maintenance on the Bellandur flyover.
- **Effect**: Traffic forced onto ground-level service roads.
- **Result**: Service roads exceeded capacity, leading to localized gridlock.

## 🗺️ Interactive Maps

The following maps were generated (located in `backend/data/graphs/`):
- `blr_baseline.html`: Normal traffic state.
- `blr_scenario_1.html`: Post-accident congestion.
- `blr_scenario_2.html`: Signal failure impact.
- `blr_scenario_3.html`: Flyover closure impact.

## 🛠️ API Endpoints

New endpoints added to `app.py`:
- `POST /simulate/road-blockage`: Inject a blockage and get cascade data.
- `POST /simulate/signal-failure`: Simulate junction signal degradation.
- `POST /simulate/flyover-closure`: Close a specific road segment.

---

### Example Output (Scenario 1)
```text
>>> SCENARIO 1: Accident on ORR (Agara to Iblur)
Cause: major_accident
Displaced Traffic: 2516 vehicles
Cascade Iterations: 1
New Overloaded Junctions: 0

Alternate Routes (Silk Board -> Marathahalli):
 Option 1: SilkBoard -> HSR_Entry -> Agara -> Sarjapur_Road_1 -> Iblur -> Bellandur -> Ecospace -> Devarabeesanahalli -> Kadubeesanahalli -> Marathahalli
   Time: 1221.72s | Traffic Share: 34.6% | Status: CONGESTED
 Option 2: SilkBoard -> HSR_Sector_7 -> HSR_Sector_1 -> Agara -> Sarjapur_Road_1 -> Iblur -> Bellandur -> Ecospace -> Devarabeesanahalli -> Kadubeesanahalli -> Marathahalli
   Time: 1279.79s | Traffic Share: 33.1% | Status: CONGESTED
 Option 3: SilkBoard -> HSR_Entry -> Agara -> Iblur -> Haralur_Road -> Bellandur -> Ecospace -> Devarabeesanahalli -> Kadubeesanahalli -> Marathahalli
   Time: 1310.22s | Traffic Share: 32.3% | Status: CONGESTED
```
