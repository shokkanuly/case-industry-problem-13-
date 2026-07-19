"""One-shot: rebuild case_registry.json merging pipeline schema + engine metadata."""
import json
import os

from app.cases import registry

# Per-case pipeline wiring (device/asset/zone) — case 13 kept exactly as it was.
WIRING = {
    1:  ("dev_survey_drone",    "asset_survey_grid",   "Survey Grid North",       "exploration_field", "report",  False),
    2:  ("dev_spec_analyzer",   "asset_core_analyzer", "Portable Core Analyzer",  "field_lab",         "report",  False),
    3:  ("dev_ore_grade_sensor","asset_conveyor_b",    "Conveyor Belt Section 2", "concentrator",      "setpoint",False),
    4:  ("dev_cv_shortcircuit", "asset_electrolysis",  "Electrolysis Hall A",     "tankhouse",         "status",  False),
    5:  ("dev_slope_radar",     "asset_pit_wall_w",    "Pit Wall West Sector",    "open_pit",          "status",  False),
    6:  ("dev_truck_edge",      "asset_haul_fleet",    "Haul Truck Fleet",        "haul_road_b",       "status",  False),
    7:  ("dev_furnace_pi",      "asset_vanyukov",      "Vanyukov Furnace 1",      "smelter",           "report",  False),
    8:  ("dev_vib_sensor",      "asset_flot_pump",     "Flotation Pump P-204",    "concentrator",      "status",  False),
    9:  ("dev_camera_trap",     "asset_balkhash",      "Balkhash Shore Station",  "environment",       "report",  False),
    10: ("dev_mesh_gateway",    "asset_tunnel_mesh",   "Underground Mesh Segment","tunnel_level_3",    "status",  True),
    11: ("dev_power_meter",     "asset_energy_bus",    "Plant Energy Bus",        "utilities",         "report",  False),
    12: ("dev_cab_ir_cam",     "asset_driver_cab",    "Haul Truck Cab 07",       "haul_road_b",       "status",  False),
    13: ("dev_cv_safety",       "haul_road_zone_b",    "Haul Road Zone B",        "haul_road_b",       "status",  False),
    14: ("dev_wagon_cam",       "asset_wagon_rear",    "Shunting Wagon Rear",     "rail_yard",         "status",  False),
    15: ("dev_construction_ndt","asset_core_lot",      "Construction Core Lot",   "construction_site", "report",  False),
}

cases = []
for e in registry.all():
    d = e.describe()
    dev, asset, asset_name, zone, output, underground = WIRING[d["case_id"]]
    cases.append({
        "case_id": d["case_id"],
        "slug": d["slug"],
        "name": d["name"],
        "category": d["category"],
        "stage": d["stage"],
        "algorithm": d["algorithm"],
        "device_id": dev,
        "asset_id": asset,
        "asset_name": asset_name,
        "zone_id": zone,
        "output_type": output,
        "underground": underground,
    })

out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "case_registry.json")
with open(out_path, "w") as f:
    json.dump({"cases": cases}, f, indent=2, ensure_ascii=False)
print("wrote", len(cases), "cases to", out_path)
