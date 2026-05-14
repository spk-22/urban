"""
osm_fetcher.py
===================================
Utility to download road network data from OpenStreetMap via the Overpass API.
The function returns a GeoJSON FeatureCollection of ways (highways) within a
bounding box. It can be used by RoadGraphBuilder to enrich the graph with real
road classes, which later map to capacity/speed defaults defined in
cascade.py.
"""
import json
import requests
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_road_geojson(bbox, output_path=None):
    """Fetch highway data from OSM within *bbox*.

    Parameters
    ----------
    bbox : tuple or list of four floats
        (south, west, north, east) – geographic bounding box.
    output_path : str or Path, optional
        If provided, the resulting GeoJSON will be written to this file.

    Returns
    -------
    dict
        GeoJSON FeatureCollection of highway ways.
    """
    south, west, north, east = bbox
    query = f"""
    [out:json][timeout:180];
    (
      way[\"highway\"]({south},{west},{north},{east});
    );
    out geom;
    """
    headers = {
        "User-Agent": "UrbanCascadeDetector/1.0 (Bengaluru Infrastructure Failure Research)"
    }
    response = requests.post(OVERPASS_URL, data={"data": query}, headers=headers)
    response.raise_for_status()
    data = response.json()
    features = []
    for element in data.get("elements", []):
        if element.get("type") != "way" or "geometry" not in element:
            continue
        coords = [(pt["lon"], pt["lat"]) for pt in element["geometry"]]
        feature = {
            "type": "Feature",
            "properties": {
                "id": element.get("id"),
                "name": element.get("tags", {}).get("name", ""),
                "highway": element.get("tags", {}).get("highway", ""),
                "class": element.get("tags", {}).get("highway", "")
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            }
        }
        features.append(feature)
    geojson = {"type": "FeatureCollection", "features": features}
    if output_path:
        Path(output_path).write_text(json.dumps(geojson, indent=2))
    return geojson

if __name__ == "__main__":
    bbox_bangalore = (12.945, 77.55, 13.02, 77.65)
    geo = fetch_road_geojson(bbox_bangalore, "bengaluru_roads.geojson")
    print(f"Fetched {len(geo['features'])} highway ways.")
