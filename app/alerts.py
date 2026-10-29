"""Triggered alerts. Thresholds are caller-supplied so the investor decides what 'unusual' means."""


def price_volume_alerts(signal_map, vol_mult=2.0, pct=3.0):
    out = []
    for sym, s in signal_map.items():
        if not s:
            continue
        reasons = []
        if s["vol_ratio"] is not None and s["vol_ratio"] >= vol_mult:
            reasons.append({"kind": "volume", "detail": f"Volume {s['vol_ratio']}x 20-day average"})
        if abs(s["pct"]) >= pct:
            reasons.append({"kind": "price", "detail": f"{s['pct']:+.2f}% on {s['date']}"})
        if reasons:
            out.append({"symbol": sym, **s, "reasons": reasons})
    out.sort(key=lambda a: (len(a["reasons"]), abs(a["pct"])), reverse=True)
    return out


def announcement_alerts(items, types):
    types = set(types)
    return [i for i in items if i["category"] in types]
