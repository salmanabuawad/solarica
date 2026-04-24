import re

def extract_dccb(text_blocks):
    devices = []

    for t in text_blocks:
        match = re.match(r"DCCB_[\d\.]+", t.get("text", ""))
        if match:
            devices.append({
                "type": "dccb",
                "name": match.group(),
                "x": t.get("x"),
                "y": t.get("y"),
            })

    return devices


def infer_inverters_from_dccb(dccb_list):
    groups = {}

    for d in dccb_list:
        parts = d["name"].split("_")[1].split(".")
        inv = parts[0]

        if inv not in groups:
            groups[inv] = []

        groups[inv].append(d)

    inverters = []

    for inv, items in groups.items():
        avg_x = sum(i["x"] for i in items if i["x"]) / len(items)
        avg_y = sum(i["y"] for i in items if i["y"]) / len(items)

        inverters.append({
            "type": "inverter",
            "name": f"INV_{inv}",
            "x": avg_x,
            "y": avg_y
        })

    return inverters