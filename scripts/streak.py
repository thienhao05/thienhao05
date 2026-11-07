#!/usr/bin/env python3
"""Tạo ảnh SVG thống kê streak (chuỗi đóng góp) từ GitHub GraphQL API.

Dùng:  GITHUB_TOKEN=... python3 scripts/streak.py <username> <output.svg>
Chỉ dùng thư viện chuẩn của Python, không cần cài thêm gói nào.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

API = "https://api.github.com/graphql"


def gql(query, token):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]["user"]


def fetch_days(login, token):
    """Trả về dict {date: số_đóng_góp} cho toàn bộ thời gian của tài khoản."""
    created = gql('query{user(login:"%s"){createdAt}}' % login, token)["createdAt"]
    first_year = int(created[:4])
    this_year = datetime.now(timezone.utc).year
    parts = []
    for y in range(first_year, this_year + 1):
        parts.append(
            f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y}-12-31T23:59:59Z")'
            "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}"
        )
    user = gql('query{user(login:"%s"){%s}}' % (login, " ".join(parts)), token)
    days = {}
    for coll in user.values():
        for week in coll["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[date.fromisoformat(d["date"])] = d["contributionCount"]
    return days


def compute(days, today):
    """Tính tổng, streak hiện tại và streak dài nhất."""
    total = sum(days.values())
    active = sorted(d for d, c in days.items() if c > 0 and d <= today)

    # Streak dài nhất
    best_len, best_start, best_end = 0, None, None
    run_len, run_start, prev = 0, None, None
    for d in active:
        if prev is not None and d - prev == timedelta(days=1):
            run_len += 1
        else:
            run_len, run_start = 1, d
        if run_len > best_len:
            best_len, best_start, best_end = run_len, run_start, d
        prev = d

    # Streak hiện tại: tính ngược từ hôm nay (hoặc hôm qua nếu hôm nay chưa có)
    active_set = set(active)
    cur_end = today if today in active_set else today - timedelta(days=1)
    cur_len, cur_start = 0, None
    d = cur_end
    while d in active_set:
        cur_len += 1
        cur_start = d
        d -= timedelta(days=1)
    if cur_len == 0:
        cur_start = cur_end = None

    first_day = min(days) if days else today
    return {
        "total": total,
        "first_day": first_day,
        "cur": (cur_len, cur_start, cur_end),
        "best": (best_len, best_start, best_end),
    }


def fmt(d):
    return d.strftime("%b %-d, %Y") if d else "—"


def fmt_range(start, end, today):
    if start is None:
        return "No streak yet"
    if start == end:
        return fmt(start)
    label_end = "Present" if end >= today - timedelta(days=1) else fmt(end)
    return f"{fmt(start)} - {label_end}"


def render(stats, today):
    bg, border = "#1F222E", "#3a3f55"
    title, num, accent, muted = "#4B8DC9", "#F8D866", "#F8D866", "#9aa3b5"
    cur_len, cur_s, cur_e = stats["cur"]
    best_len, best_s, best_e = stats["best"]
    total_range = f"{fmt(stats['first_day'])} - Present"
    cur_range = fmt_range(cur_s, cur_e, today)
    best_range = fmt_range(best_s, best_e, today)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195" role="img" aria-label="GitHub streak stats">
  <style>
    text {{ font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif; }}
    .big {{ font-size: 28px; font-weight: 700; fill: {num}; }}
    .cur {{ font-size: 32px; font-weight: 800; fill: {accent}; }}
    .lbl {{ font-size: 14px; font-weight: 600; fill: {title}; }}
    .lblc {{ font-size: 15px; font-weight: 700; fill: {accent}; }}
    .rng {{ font-size: 12px; fill: {muted}; }}
  </style>
  <rect x="0.5" y="0.5" width="494" height="194" rx="4.5" fill="{bg}" stroke="{border}"/>
  <line x1="165" y1="35" x2="165" y2="160" stroke="{border}"/>
  <line x1="330" y1="35" x2="330" y2="160" stroke="{border}"/>

  <g text-anchor="middle">
    <text x="82.5" y="82" class="big">{stats['total']:,}</text>
    <text x="82.5" y="112" class="lbl">Total Contributions</text>
    <text x="82.5" y="135" class="rng">{total_range}</text>

    <circle cx="247.5" cy="72" r="38" fill="none" stroke="{accent}" stroke-width="5"/>
    <text x="247.5" y="83" class="cur">{cur_len}</text>
    <text x="247.5" y="132" class="lblc">Current Streak</text>
    <text x="247.5" y="153" class="rng">{cur_range}</text>

    <text x="412.5" y="82" class="big">{best_len}</text>
    <text x="412.5" y="112" class="lbl">Longest Streak</text>
    <text x="412.5" y="135" class="rng">{best_range}</text>
  </g>
</svg>
"""


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: streak.py <username> <output.svg>")
    login, out = sys.argv[1], sys.argv[2]
    token = os.environ["GITHUB_TOKEN"]
    today = datetime.now(timezone.utc).date()
    stats = compute(fetch_days(login, token), today)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(stats, today))
    print(f"total={stats['total']} current={stats['cur'][0]} longest={stats['best'][0]}")


if __name__ == "__main__":
    main()
