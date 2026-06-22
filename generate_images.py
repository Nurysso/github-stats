import os
import csv
import json
import traceback
from datetime import datetime, timedelta
from github import Github, Auth

DATA_DIR     = "data"
SUMMARY_FILE = os.path.join(DATA_DIR, "clones_summary.json")
os.makedirs(DATA_DIR, exist_ok=True)

# How many days the GitHub API returns — keep ALL of them to prevent double-counting
WINDOW_DAYS = 14


def load_historical_data():
    if os.path.exists(SUMMARY_FILE):
        try:
            with open(SUMMARY_FILE) as f:
                data = json.load(f)
            return {
                "cumulative_totals": data.get("cumulative_totals", {}),
                "daily_records":     data.get("daily_records", {}),
            }
        except Exception:
            pass
    return {"cumulative_totals": {}, "daily_records": {}}


def get_clone_stats():
    token    = os.environ.get("ACCESS_TOKEN")
    username = os.environ.get("GITHUB_USERNAME")
    if not token or not username:
        raise ValueError("ACCESS_TOKEN and GITHUB_USERNAME must be set")

    g    = Github(auth=Auth.Token(token))
    user = g.get_user(username)
    print(f"✓ Authenticated as: {user.login}")

    clone_data = []
    ok = fail = 0
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today      = datetime.now().strftime("%Y-%m-%d")

    for repo in user.get_repos():
        try:
            traffic = repo.get_clones_traffic()
            daily   = {
                day.timestamp.strftime("%Y-%m-%d"): {
                    "count":   day.count,
                    "uniques": day.uniques,
                }
                for day in traffic.clones
            }
            clone_data.append({
                "timestamp":       timestamp,
                "date":            today,
                "repo_name":       repo.name,
                "period_clones":   traffic.count,
                "period_unique":   traffic.uniques,
                "daily_breakdown": daily,
            })
            print(f"  ✓ {repo.name}: {traffic.count} clones ({traffic.uniques} unique)")
            ok += 1
        except Exception as e:
            print(f"  ✗ {repo.name}: {e}")
            fail += 1

    print(f"\n✓ {ok} succeeded  ✗ {fail} failed")
    return clone_data, timestamp, today


def calculate_cumulative_totals(clone_data, historical_data):
    """
    Dedup by storing a daily_records map of every day we've already counted.
    We keep WINDOW_DAYS + 1 days of records — enough to cover the full API
    window on every run — so no day ever gets double-counted.
    """
    cumulative   = {k: dict(v) for k, v in historical_data["cumulative_totals"].items()}
    daily_records = {k: dict(v) for k, v in historical_data["daily_records"].items()}

    cutoff = (datetime.now() - timedelta(days=WINDOW_DAYS + 1)).strftime("%Y-%m-%d")

    for repo in clone_data:
        name = repo["repo_name"]
        cumulative.setdefault(name, {"total_clones": 0, "total_unique": 0})
        daily_records.setdefault(name, {})

        for day_str, stats in repo["daily_breakdown"].items():
            if day_str in daily_records[name]:
                continue  # already counted this day → skip
            daily_records[name][day_str] = stats
            cumulative[name]["total_clones"] += stats["count"]
            print(f"  + {stats['count']} clones on {day_str} for {name}")

        # Prune old records outside the API window (saves space, still safe)
        daily_records[name] = {
            d: s for d, s in daily_records[name].items() if d >= cutoff
        }

        # Unique cloners: take the max seen across any period window
        cumulative[name]["total_unique"] = max(
            cumulative[name]["total_unique"],
            repo["period_unique"],
        )
        cumulative[name]["last_updated"] = repo["timestamp"]

    return cumulative, daily_records


def update_summary(clone_data, cumulative_totals, daily_records):
    period_clones = sum(r["period_clones"] for r in clone_data)
    period_unique = sum(r["period_unique"] for r in clone_data)

    all_cum_clones = sum(v["total_clones"] for v in cumulative_totals.values())
    all_cum_unique = sum(v["total_unique"] for v in cumulative_totals.values())

    top_period = sorted(
        [{"name": r["repo_name"], "period_clones": r["period_clones"], "period_unique": r["period_unique"]}
         for r in clone_data],
        key=lambda x: x["period_clones"], reverse=True,
    )[:10]

    top_cumulative = sorted(
        [{"name": n, "total_clones": v["total_clones"], "total_unique": v["total_unique"]}
         for n, v in cumulative_totals.items()],
        key=lambda x: x["total_clones"], reverse=True,
    )[:10]

    # ── only the three fields you want ──────────────────────────────────────
    summary = {
        "period_stats": {
            "total_clones":        period_clones,
            "total_unique_clones": period_unique,
            "repos_tracked":       len(clone_data),
            "repos_with_clones":   sum(1 for r in clone_data if r["period_clones"] > 0),
        },
        "top_repositories": top_period,
        "cumulative_stats": {
            "total_clones":        all_cum_clones,
            "total_unique_clones": all_cum_unique,
            "repos_tracked":       len(cumulative_totals),
            "repos_with_clones":   sum(1 for v in cumulative_totals.values() if v["total_clones"] > 0),
            "top_repositories":    top_cumulative,
        },
        # internal dedup state — not shown in README but needed across runs
        "cumulative_totals": cumulative_totals,
        "daily_records":     daily_records,
    }

    with open(SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n✓ {SUMMARY_FILE} updated")
    print(f"  Period  : {period_clones} clones / {period_unique} unique")
    print(f"  All-time: {all_cum_clones} clones / {all_cum_unique} unique")
    print(f"\nTop 5 (all-time):")
    for i, r in enumerate(top_cumulative[:5], 1):
        print(f"  {i}. {r['name']}: {r['total_clones']} ({r['total_unique']} unique)")


def main():
    try:
        historical = load_historical_data()
        print(f"Loaded history for {len(historical['cumulative_totals'])} repos\n")

        clone_data, timestamp, today = get_clone_stats()
        if not clone_data:
            print("⚠ No clone data collected — check token scopes (needs classic token + repo scope)")
            return

        cumulative, daily_records = calculate_cumulative_totals(clone_data, historical)
        update_summary(clone_data, cumulative, daily_records)
        print("\n=== Done ===")

    except Exception as e:
        print(f"\n✗ Fatal: {e}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
