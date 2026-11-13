"""The Daily Thread: a fashion trend radar built on live search data, plus a mindful wardrobe.

Run:  python app.py   ->  http://localhost:5004
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, session, url_for

from thread.colours import nearest_family
from thread.radar import get_radar, sparkline
from thread.trends import METHODOLOGY_VERSION

ROOT = Path(__file__).resolve().parent
KINDS = ["Top", "Bottom", "Dress", "Outerwear", "Shoes", "Accessory"]
ORDER = ["Rising", "Emerging", "Peaking", "Stable", "Fading", "Out"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS wardrobe (
  id INTEGER PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL,
  colour TEXT NOT NULL, term TEXT, added TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checks (
  id INTEGER PRIMARY KEY, owner TEXT NOT NULL, item TEXT NOT NULL, term TEXT,
  score INTEGER NOT NULL, verdict TEXT NOT NULL, created TEXT NOT NULL);
"""


def secret_key(instance_path: str) -> str:
    """SECRET_KEY from the environment, else one generated once and kept in instance/secret_key.

    The key signs the session cookie that links a browser to its wardrobe. A new random key on
    every start (the old behaviour) made every reader's wardrobe vanish after a restart.
    """
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    path = Path(instance_path) / "secret_key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def nice_date(iso: str | None) -> str:
    """'2026-11-01' -> '1 Nov 2026'."""
    if not iso:
        return "unknown"
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d:%b %Y}"


def create_app(db_path: str | None = None, snapshots: Path | None = None, instance_path: str | None = None) -> Flask:
    app = Flask(__name__, instance_path=instance_path)
    app.config["SECRET_KEY"] = secret_key(app.instance_path)
    app.config["DB"] = db_path or str(ROOT / "data" / "thread.db")
    app.config["SNAPSHOTS"] = snapshots or ROOT / "data" / "snapshots"
    app.config["BACKTEST"] = ROOT / "data" / "backtest.json"
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.jinja_env.filters["pct"] = lambda v: "n/a" if v is None else f"{v:+.0%}".replace("-", "−")
    app.jinja_env.filters["nice_date"] = nice_date

    def db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB"])
            g.db.row_factory = sqlite3.Row
            g.db.executescript(SCHEMA)
        return g.db

    @app.teardown_appcontext
    def close_db(_exc) -> None:
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    def owner() -> str:
        # Anonymous per-browser id; the wardrobe itself lives in SQLite, not in the cookie.
        if "owner" not in session:
            session["owner"] = uuid.uuid4().hex
            session.permanent = True
        return session["owner"]

    def radar():
        r = get_radar(app.config["SNAPSHOTS"])
        if r is None:
            abort(503, "No trend snapshot yet. Run python scripts/refresh_trends.py")
        return r

    @app.context_processor
    def globals_():
        r = get_radar(app.config["SNAPSHOTS"])
        return {"as_of": r.as_of if r else None, "data_to": r.data_to if r else None,
                "missing": r.missing if r else [], "endpoint": request.endpoint}

    # ------------------------------------------------------------------ radar
    @app.route("/")
    def front():
        r = radar()
        cat = request.args.get("category", "")
        items = [i for i in r.items if not cat or i["category"] == cat]
        groups = {lab: [i for i in items if i["label"] == lab] for lab in ORDER}
        solid = [i for i in items if not i["low_volume"] and i["yoy"] is not None]
        lead = max(solid, key=lambda x: x["yoy"], default=None)
        falling = min(solid, key=lambda x: x["yoy"], default=None)
        coverage = {"shown": len(r.items), "tracked": len(r.terms), "missing": r.missing,
                    "carried": sum(1 for i in r.items if i["carried_from"])}
        return render_template("front.html", groups=groups, lead=lead, falling=falling,
                               categories=r.categories(), category=cat, total=len(items), coverage=coverage)

    @app.route("/trend/<term_slug>")
    def trend(term_slug: str):
        r = radar()
        item = r.item(term_slug)
        if item is None:
            abort(404)
        s = r.series(item["term"])
        entry = r.dictionary.by_slug[term_slug]
        related = [r.dictionary.by_id[x] for x in entry.related]
        has_data = {i["slug"] for i in r.items}
        w, h, n = 760, 220, len(s["values"])
        years = [(i * w / max(1, n - 1), d[:4]) for i, d in enumerate(s["dates"])
                 if i and d[:4] != s["dates"][i - 1][:4]]
        recent_x = (n - 12) * w / max(1, n - 1)
        prior_x = (n - 64) * w / max(1, n - 1)
        return render_template("trend.html", item=item, path=sparkline(s["values"], w, h), years=years,
                               recent_x=recent_x, prior_x=prior_x, band=12 * w / max(1, n - 1),
                               first=s["dates"][0], last=s["dates"][-1], peak=max(s["values"]),
                               entry=entry, category_path=" / ".join(r.dictionary.path(entry.category)), related=related,
                               has_data=has_data)

    @app.route("/dictionary")
    def dictionary():
        r = radar()
        d = r.dictionary
        q = request.args.get("q", "").strip()[:60]
        found = d.search(q) if q else d.terms
        order = list(d.categories)

        def grouped(status: str) -> dict:
            groups: dict = {}
            for t in sorted((t for t in found if t.status == status), key=lambda t: (order.index(t.category), t.name)):
                groups.setdefault(" / ".join(d.path(t.category)), []).append(t)
            return groups

        groups, proposed = grouped("active"), grouped("proposed")
        return render_template("dictionary.html", groups=groups, proposed=proposed, q=q,
                               count=sum(map(len, groups.values())), proposed_count=sum(map(len, proposed.values())),
                               radar={i["slug"]: i for i in r.items})

    @app.route("/colours")
    def colours():
        return render_template("colours.html", story=radar().colour_story())

    @app.route("/method")
    def method():
        r = get_radar(app.config["SNAPSHOTS"])
        run = r.snap.get("run") if r else None
        failed = sorted((tag.split(":", 1) + [why] for tag, why in (run or {}).get("failed", {}).items()))
        bt_path = Path(app.config["BACKTEST"])
        backtest = json.loads(bt_path.read_text(encoding="utf-8")) if bt_path.exists() else None
        return render_template("method.html", run=run, failed=failed, version=METHODOLOGY_VERSION, bt=backtest)

    # --------------------------------------------------------------- wardrobe
    @app.route("/wardrobe", methods=["GET", "POST"])
    def wardrobe():
        r = radar()
        me = owner()
        error = None
        if request.method == "POST":
            name = request.form.get("name", "").strip()[:80]
            kind = request.form.get("kind", "")
            colour = request.form.get("colour", "").strip().upper()
            term = request.form.get("term", "") or None
            if not name or kind not in KINDS or len(colour) != 7 or not colour.startswith("#"):
                error = "Give the item a name, a type and a colour."
            elif term and r.item(term) is None:
                error = "Pick a style from the list, or leave it blank."
            else:
                db().execute("INSERT INTO wardrobe (owner, name, kind, colour, term, added) VALUES (?,?,?,?,?,?)",
                             (me, name, kind, colour, term, date.today().isoformat()))
                db().commit()
                return redirect(url_for("wardrobe"))
        rows = db().execute("SELECT * FROM wardrobe WHERE owner = ? ORDER BY id DESC", (me,)).fetchall()
        season = r.colour_story()["now"]
        season_words = {row["family"] for row in season["rows"]} if season else set()
        items = []
        for row in rows:
            fam, _ = nearest_family(row["colour"])
            items.append({**dict(row), "family": fam, "in_season": fam in season_words,
                          "trend": r.item(row["term"]) if row["term"] else None})
        return render_template("wardrobe.html", items=items, kinds=KINDS, styles=r.items, error=error,
                               season=season), (400 if error else 200)

    @app.route("/wardrobe/<int:item_id>/delete", methods=["POST"])
    def delete_item(item_id: int):
        db().execute("DELETE FROM wardrobe WHERE id = ? AND owner = ?", (item_id, owner()))
        db().commit()
        return redirect(url_for("wardrobe"))

    @app.route("/check", methods=["GET", "POST"])
    def check():
        r = radar()
        me = owner()
        result = None
        if request.method == "POST":
            f = request.form
            item = f.get("item", "").strip()[:80] or "this piece"
            term = f.get("term") or None
            trend = r.item(term) if term else None
            owned = db().execute("SELECT COUNT(*) FROM wardrobe WHERE owner = ? AND kind = ?",
                                 (me, f.get("kind", ""))).fetchone()[0]
            result = mindful_score(f, trend, owned)
            result["item"] = item
            db().execute("INSERT INTO checks (owner, item, term, score, verdict, created) VALUES (?,?,?,?,?,?)",
                         (me, item, term, result["score"], result["verdict"],
                          datetime.now().isoformat(timespec="seconds")))
            db().commit()
        history = db().execute("SELECT * FROM checks WHERE owner = ? ORDER BY id DESC LIMIT 6", (me,)).fetchall()
        return render_template("check.html", styles=r.items, kinds=KINDS, result=result, history=history)

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", message="That page isn't in this edition."), 404

    @app.errorhandler(503)
    def unavailable(e):
        return render_template("error.html", message=e.description), 503

    return app


def mindful_score(form, trend: dict | None, owned_same_kind: int) -> dict:
    """Score a planned purchase out of 100. Each rule adds or removes points and says why."""
    score, reasons = 50, []
    try:
        wears = int(form.get("wears", 0) or 0)
    except ValueError:
        wears = 0
    if wears >= 4:
        score += 20
        reasons.append(f"You expect to wear it {wears} times a month.")
    elif wears <= 1:
        score -= 15
        reasons.append("You expect to wear it once a month or less.")
    if form.get("pairs") == "yes":
        score += 10
        reasons.append("It works with at least three things you own.")
    else:
        score -= 10
        reasons.append("It doesn't go with much you already own.")
    if form.get("gap") == "yes":
        score += 15
        reasons.append("It fills a real gap.")
    if owned_same_kind >= 5:
        score -= 10
        reasons.append(f"Your wardrobe already has {owned_same_kind} items of this type.")
    if form.get("hype") == "yes":
        score -= 10
        reasons.append("Part of the pull is that it's trending.")
    if trend:
        lab, term = trend["label"], trend.get("name", trend["term"]).lower()
        if lab == "Rising":
            score -= 10
            reasons.append(f"The radar says {term} is rising fast: buying near the top of the hype is a risk.")
        elif lab == "Emerging":
            score -= 5
            reasons.append(f"The radar shows early signs that {term} is rising; it may or may not take off.")
        elif lab in ("Fading", "Out"):
            score -= 5
            reasons.append(f"The radar says {term} is {lab.lower()}: fine if you love it, not if it's for the trend.")
        elif lab == "Stable":
            score += 5
            reasons.append(f"Interest in {term} has held steady for a year: a safer buy.")
    score = max(0, min(100, score))
    verdict = "Mindful buy" if score >= 65 else "Sleep on it" if score >= 40 else "Probably skip"
    return {"score": score, "verdict": verdict, "reasons": reasons}


app = create_app()

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5004)), debug=False)
