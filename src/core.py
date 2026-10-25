"""Theme marketplace engine for SigmaOS-theme-marketplace / theme-registry
(inspired by cinnamon-spices-themes, omarchy-theme-marketplace/registry).

Principles: pure registry parsing & search, plan-before-act for installs
(download/verify/extract steps are computed, never executed), local-only
ratings store, fail-fast on malformed registry entries.
"""
import argparse, json, os, re, sys

ENGINE = {
    "name": "sigma-theme-market",
    "summary": "Search, install-plan, rate and index themes",
    "language": "python",
    "verbs": ["search", "install-plan", "rate", "index"],
    "principles": ["Plan Before Act", "Information Hiding", "Fail-Fast",
                   "Defensive Programming", "KISS", "Deterministic Testing"],
}

cli_doc = """\
$ sigma-theme-market search dark --tag mint
mint-y-dark  Mint-Y-Dark  4.5 (120 votes)
$ sigma-theme-market install-plan registry.json mint-y-dark \\
    --installed mint-y=1.2.0 --target ~/.themes
fetch  https://themes.sigmaos.dev/mint-y-dark-2.0.0.tar.xz
verify sha256:<hash>
$ sigma-theme-market rate ratings.json mint-y-dark 5
$ sigma-theme-market index ./submitted --out registry.json
"""

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


class MarketError(ValueError):
    pass


def _read(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def parse_registry(text):
    """Parse and validate the marketplace registry JSON."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise MarketError(f"registry is not valid JSON: {e}") from e
    if not isinstance(data, list):
        raise MarketError("registry must be a JSON list of themes")
    seen = set()
    for entry in data:
        for field in ("id", "name", "version", "author", "tags", "sha256"):
            if field not in entry:
                raise MarketError(
                    f"registry entry missing {field!r}: {entry!r}")
        if not _SLUG_RE.match(entry["id"]):
            raise MarketError(f"bad theme id: {entry['id']!r}")
        if entry["id"] in seen:
            raise MarketError(f"duplicate theme id: {entry['id']}")
        seen.add(entry["id"])
        if not _VERSION_RE.match(entry["version"]):
            raise MarketError(f"bad version for {entry['id']}: "
                              f"{entry['version']!r}")
        if not _SHA_RE.match(entry["sha256"]):
            raise MarketError(f"bad sha256 for {entry['id']}")
        if not isinstance(entry["tags"], list) or \
                not all(isinstance(t, str) for t in entry["tags"]):
            raise MarketError(f"bad tags for {entry['id']}")
        entry.setdefault("rating", 0.0)
        entry.setdefault("downloads", 0)
    return sorted(data, key=lambda e: e["id"])


def search(registry, query, tag=None, sort="rating"):
    """Case-insensitive AND search over id/name/tags; stable ordering."""
    if sort not in ("rating", "downloads", "name"):
        raise MarketError(f"bad sort key: {sort!r}")
    tokens = [t for t in query.lower().split() if t]
    hits = []
    for entry in registry:
        hay = " ".join([entry["id"], entry["name"],
                        " ".join(entry["tags"])]).lower()
        if tag is not None and tag.lower() not in \
                [t.lower() for t in entry["tags"]]:
            continue
        if all(t in hay for t in tokens):
            hits.append(entry)
    key = {"rating": lambda e: (-float(e["rating"]), e["id"]),
           "downloads": lambda e: (-int(e["downloads"]), e["id"]),
           "name": lambda e: (e["name"].lower(), e["id"])}[sort]
    return sorted(hits, key=key)


def _parse_installed(specs):
    installed = {}
    for spec in specs:
        if "=" not in spec:
            raise MarketError(f"--installed needs ID=VERSION, got {spec!r}")
        tid, _, version = spec.partition("=")
        if not _SLUG_RE.match(tid) or not _VERSION_RE.match(version):
            raise MarketError(f"bad --installed spec: {spec!r}")
        installed[tid] = version
    return installed


def install_plan(registry, theme_id, installed, target):
    """Pure install plan; download/extract steps are never executed."""
    by_id = {e["id"]: e for e in registry}
    if theme_id not in by_id:
        raise MarketError(f"unknown theme {theme_id!r} "
                          f"(known: {', '.join(sorted(by_id)) or 'none'})")
    entry = by_id[theme_id]
    dest = os.path.join(target, entry["name"])
    if installed.get(theme_id) == entry["version"]:
        return {"status": "already-installed", "entry": entry,
                "dest": dest, "steps": []}
    status = "install"
    if theme_id in installed:
        status = "upgrade" if installed[theme_id] < entry["version"] \
            else "downgrade"
    return {
        "status": status,
        "entry": entry,
        "dest": dest,
        "steps": [
            f"fetch  https://themes.sigmaos.dev/{theme_id}-"
            f"{entry['version']}.tar.xz",
            f"verify sha256:{entry['sha256']}",
            f"extract --strip-components=1 -> {dest}",
            f"register {theme_id}@{entry['version']} in installed.json",
            f"post-install: {theme_id}/install.sh" if entry.get("has_script")
            else "post-install: none",
        ],
    }


def rate(store_path, theme_id, score):
    """Append a local rating (1-5) to a JSON store; returns the summary."""
    if not _SLUG_RE.match(theme_id):
        raise MarketError(f"bad theme id: {theme_id!r}")
    if isinstance(score, bool) or not isinstance(score, int) \
            or not 1 <= score <= 5:
        raise MarketError(f"rating must be an integer 1..5, got {score!r}")
    store = {}
    if os.path.exists(store_path):
        try:
            store = json.loads(_read(store_path))
        except json.JSONDecodeError as e:
            raise MarketError(f"corrupt ratings store: {e}") from e
        if not isinstance(store, dict):
            raise MarketError("corrupt ratings store: expected an object")
    scores = list(store.get(theme_id, []))
    scores.append(score)
    store[theme_id] = scores
    with open(store_path, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=2, sort_keys=True)
    return {"id": theme_id, "votes": len(scores),
            "average": round(sum(scores) / len(scores), 2)}


def build_index(themes_dir):
    """Build a registry index from submitted theme directories."""
    if not os.path.isdir(themes_dir):
        raise MarketError(f"no such directory: {themes_dir!r}")
    entries = []
    for name in sorted(os.listdir(themes_dir)):
        manifest = os.path.join(themes_dir, name, "theme.json")
        if not os.path.isfile(manifest):
            continue
        try:
            data = json.loads(_read(manifest))
        except json.JSONDecodeError as e:
            raise MarketError(f"{name}/theme.json: bad JSON: {e}") from e
        data.setdefault("id", name)
        entries.append(data)
    if not entries:
        raise MarketError(f"no theme.json manifests under {themes_dir!r}")
    # validate the whole set at once (catches duplicates too)
    return parse_registry(json.dumps(entries))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"],
                                description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    se = sub.add_parser("search", help="search the registry")
    se.add_argument("registry_file")
    se.add_argument("query", nargs="+")
    se.add_argument("--tag", default=None)
    se.add_argument("--sort", choices=["rating", "downloads", "name"],
                    default="rating")
    ip = sub.add_parser("install-plan", help="plan a theme install (dry run)")
    ip.add_argument("registry_file")
    ip.add_argument("theme_id")
    ip.add_argument("--installed", action="append", default=[],
                    metavar="ID=VERSION")
    ip.add_argument("--target", default=os.path.expanduser("~/.themes"))
    ra = sub.add_parser("rate", help="record a local rating")
    ra.add_argument("store_file")
    ra.add_argument("theme_id")
    ra.add_argument("score", type=int)
    ix = sub.add_parser("index", help="build a registry index from a directory")
    ix.add_argument("themes_dir")
    ix.add_argument("--out", default=None)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "index":
            registry = build_index(args.themes_dir)
            blob = json.dumps(registry, indent=2, sort_keys=True)
            if args.out:
                with open(args.out, "w", encoding="utf-8") as fh:
                    fh.write(blob + "\n")
                print(f"indexed {len(registry)} theme(s) -> {args.out}")
            else:
                print(blob)
            return 0
        if args.cmd == "rate":
            summary = rate(args.store_file, args.theme_id, args.score)
            print(f"{summary['id']}: {summary['average']} "
                  f"({summary['votes']} vote(s))")
            return 0
        registry = parse_registry(_read(args.registry_file))
        if args.cmd == "search":
            hits = search(registry, " ".join(args.query), tag=args.tag,
                          sort=args.sort)
            if not hits:
                print("no themes matched")
            for e in hits:
                print(f"{e['id']:<20} {e['name']:<24} "
                      f"{e['rating']} ({e['downloads']} downloads)")
        elif args.cmd == "install-plan":
            plan = install_plan(registry, args.theme_id,
                                _parse_installed(args.installed),
                                args.target)
            print(f"status: {plan['status']}")
            for step in plan["steps"]:
                print(f"  {step}")
        return 0
    except MarketError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    import hashlib, tempfile
    registry_text = json.dumps([
        {"id": "mint-y-dark", "name": "Mint-Y-Dark", "version": "2.0.0",
         "author": "SigmaOS", "tags": ["dark", "mint"], "rating": 4.5,
         "downloads": 1200,
         "sha256": hashlib.sha256(b"a").hexdigest()},
        {"id": "aether-light", "name": "Aether Light", "version": "1.1.0",
         "author": "Aether Team", "tags": ["light", "aether"], "rating": 4.9,
         "downloads": 300,
         "sha256": hashlib.sha256(b"b").hexdigest()},
        {"id": "mint-y", "name": "Mint-Y", "version": "1.2.0",
         "author": "SigmaOS", "tags": ["mint", "neutral"], "rating": 4.0,
         "downloads": 5000,
         "sha256": hashlib.sha256(b"c").hexdigest(),
         "has_script": True},
    ])
    registry = parse_registry(registry_text)
    assert [e["id"] for e in registry] == \
        ["aether-light", "mint-y", "mint-y-dark"]

    hits = search(registry, "dark")
    assert [e["id"] for e in hits] == ["mint-y-dark"]
    assert [e["id"] for e in search(registry, "", tag="mint",
                                    sort="downloads")] == \
        ["mint-y", "mint-y-dark"]
    assert [e["id"] for e in search(registry, "aether", sort="name")] == \
        ["aether-light"]
    assert search(registry, "nonexistent") == []
    for bad_query_sort in ("size",):
        try:
            search(registry, "x", sort=bad_query_sort)
        except MarketError:
            pass
        else:
            raise AssertionError("bad sort accepted")

    installed = _parse_installed(["mint-y=1.2.0"])
    plan = install_plan(registry, "mint-y", installed, "/tmp/themes")
    assert plan["status"] == "already-installed" and plan["steps"] == []
    plan = install_plan(registry, "mint-y-dark", installed, "/tmp/themes")
    assert plan["status"] == "install"
    assert plan["steps"][0].endswith("mint-y-dark-2.0.0.tar.xz")
    assert plan["steps"][1] == "verify sha256:" + \
        hashlib.sha256(b"a").hexdigest()
    assert plan["dest"] == "/tmp/themes/Mint-Y-Dark"
    plan = install_plan(registry, "mint-y", {"mint-y": "1.0.0"}, "/t")
    assert plan["status"] == "upgrade"
    plan = install_plan(registry, "mint-y", {"mint-y": "9.9.9"}, "/t")
    assert plan["status"] == "downgrade"
    assert any("install.sh" in s for s in install_plan(
        registry, "mint-y", {}, "/t")["steps"])
    for bad in (lambda: install_plan(registry, "ghost", {}, "/t"),
                lambda: _parse_installed(["noversion"])):
        try:
            bad()
        except MarketError:
            pass
        else:
            raise AssertionError("expected MarketError")

    # registry validation failures
    broken = json.loads(registry_text)
    for mutate, fragment in (
        (lambda r: r[0].pop("sha256"), "missing 'sha256'"),
        (lambda r: r[0].update(id="Bad_ID"), "bad theme id"),
        (lambda r: r[0].update(version="2.0"), "bad version"),
        (lambda r: r[0].update(sha256="xyz"), "bad sha256"),
        (lambda r: r.append(dict(r[0])), "duplicate theme id"),
    ):
        mutate(broken)
        try:
            parse_registry(json.dumps(broken))
        except MarketError as e:
            assert fragment in str(e), (fragment, str(e))
        else:
            raise AssertionError(f"broken registry accepted: {fragment}")
        broken = json.loads(registry_text)   # reset for next mutation
    try:
        parse_registry("{\"not\": \"a list\"}")
    except MarketError:
        pass
    else:
        raise AssertionError("non-list registry accepted")

    with tempfile.TemporaryDirectory() as d:
        # ratings store
        store = os.path.join(d, "ratings.json")
        s1 = rate(store, "mint-y-dark", 5)
        s2 = rate(store, "mint-y-dark", 4)
        assert (s1["votes"], s1["average"]) == (1, 5.0)
        assert (s2["votes"], s2["average"]) == (2, 4.5)
        for bad in (lambda: rate(store, "mint-y-dark", 0),
                    lambda: rate(store, "mint-y-dark", 6),
                    lambda: rate(store, "Bad Id", 3)):
            try:
                bad()
            except MarketError:
                pass
            else:
                raise AssertionError("bad rating accepted")

        # index building from submissions
        sub = os.path.join(d, "submitted")
        os.makedirs(os.path.join(sub, "zeta"))
        with open(os.path.join(sub, "zeta", "theme.json"), "w") as fh:
            json.dump({"id": "zeta", "name": "Zeta", "version": "0.1.0",
                       "author": "me", "tags": ["new"],
                       "sha256": hashlib.sha256(b"z").hexdigest()}, fh)
        os.makedirs(os.path.join(sub, "ignored-no-manifest"))
        built = build_index(sub)
        assert [e["id"] for e in built] == ["zeta"]
        out = os.path.join(d, "index.json")
        with open(out, "w") as fh:
            fh.write(json.dumps(built))
        assert parse_registry(open(out).read()) == built
        try:
            build_index(os.path.join(d, "ghost"))
        except MarketError:
            pass
        else:
            raise AssertionError("missing dir accepted")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
