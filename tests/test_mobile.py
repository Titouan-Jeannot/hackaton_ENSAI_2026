"""Version mobile : l’application est installable (manifeste, icônes, service worker)."""
import json


def test_installable_app(world):
    c = world.client()
    page = c.get("/").text
    assert 'rel="manifest" href="manifest.webmanifest"' in page and "apple-touch-icon" in page
    assert 'id="tabs"' in page and "viewport-fit=cover" in page
    r = c.get("/manifest.webmanifest")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/manifest+json")
    manifest = json.loads(r.text)
    assert manifest["display"] == "standalone" and manifest["start_url"].startswith("./")
    sizes = {i["sizes"] for i in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes and any(i["purpose"] == "maskable" for i in manifest["icons"])
    for icon in manifest["icons"] + [{"src": "static/icons/apple-touch-icon.png"}]:
        assert c.get("/" + icon["src"]).headers["content-type"] == "image/png"
    sw = c.get("/sw.js")
    assert sw.status_code == 200 and "javascript" in sw.headers["content-type"]
    assert 'startsWith("api/")' in sw.text          # les données de l’API ne sont jamais mises en cache
    for asset in ("static/app.css", "static/app.js", "static/common.js"):
        assert f'"{asset}"' in sw.text and c.get("/" + asset).status_code == 200
