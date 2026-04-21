"""
insert_yoast_seo.py 
=======================================================================
Inserts Yoast SEO details (Free + Premium) into WordPress pages via
the REST API, including keyphrase synonyms for Yoast Premium.
"""

import requests
from requests.auth import HTTPBasicAuth
import json

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — set these for your WordPress site
# Replace the placeholders below with your site's base URL, a username
# that has an application password, and the generated application password.
# ──────────────────────────────────────────────────────────────────────────────
WP_BASE_URL     = "https://your-wordpress-site.com"  # No trailing slash
WP_USERNAME     = "your-email@example.com"           # WordPress username (admin recommended)
WP_APP_PASSWORD = "your-application-password"        # Application Password (from WP Admin)

DEBUG = True   # Set False to silence raw API responses
# ──────────────────────────────────────────────────────────────────────────────

AUTH    = HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD)
HEADERS = {"Content-Type": "application/json"}

# ──────────────────────────────────────────────────────────────────────────────
# SEO DATA 
# ──────────────────────────────────────────────────────────────────────────────

# Use 'utf-8-sig' to gracefully handle files that include a UTF-8 BOM
with open('seo_data.json', 'r', encoding='utf-8-sig') as f:
    SEO_DATA = json.load(f)


# ──────────────────────────────────────────────────────────────────────────────
# REST API endpoint map per post type
# ──────────────────────────────────────────────────────────────────────────────
ENDPOINT_MAP = {
    "page":         f"{WP_BASE_URL}/wp-json/wp/v2/pages",
    "post":         f"{WP_BASE_URL}/wp-json/wp/v2/posts",
    "sfwd-lessons": f"{WP_BASE_URL}/wp-json/wp/v2/sfwd-lessons",
    "sfwd-courses": f"{WP_BASE_URL}/wp-json/wp/v2/sfwd-courses",
    "sfwd-topic":   f"{WP_BASE_URL}/wp-json/wp/v2/sfwd-topic",
    "lesson":       f"{WP_BASE_URL}/wp-json/wp/v2/lessons",
    "course":       f"{WP_BASE_URL}/wp-json/wp/v2/courses",
}


# ──────────────────────────────────────────────────────────────────────────────
# Build the Yoast meta payload for a page
# ──────────────────────────────────────────────────────────────────────────────
def build_yoast_meta(page: dict) -> dict:
    """
    Returns the full Yoast meta dict for a page entry.

    Key clarification:
      _yoast_wpseo_keywordsynonyms  → Synonyms for the PRIMARY focus keyphrase
                                      Format: JSON array of strings  e.g. ["syn1, syn2"]
                                      Index 0 = synonyms for the main keyphrase.

      _yoast_wpseo_focuskeywords    → Additional / related keyphrases (separate
                                      Yoast Premium feature).
                                      Format: JSON array of objects
                                      e.g. [{"keyword":"...", "synonyms":"..."}]
    """
    return {
        # ── Yoast FREE ───────────────────────────────────────────────────────
        "_yoast_wpseo_focuskw":    page["focus_keyphrase"],
        "_yoast_wpseo_title":      page["seo_title"],
        "_yoast_wpseo_metadesc":   page["meta_description"],
        "_yoast_wpseo_bctitle":    page["breadcrumb_title"],

        # ── Yoast PREMIUM: synonyms for the primary keyphrase ────────────────
        "_yoast_wpseo_keywordsynonyms": json.dumps([page["synonyms"]]),

        # ── Yoast PREMIUM: related/additional keyphrases ─────────────────────
        "_yoast_wpseo_focuskeywords": json.dumps([
            {
                "keyword":  page["focus_keyphrase"],
                "synonyms": page["synonyms"],
            }
        ]),
    }


# ──────────────────────────────────────────────────────────────────────────────
# STEP 0 — Verify authentication
# ──────────────────────────────────────────────────────────────────────────────
def verify_auth() -> bool:
    url = f"{WP_BASE_URL}/wp-json/wp/v2/users/me"
    r = requests.get(url, auth=AUTH, timeout=15)
    if r.status_code == 200:
        print(f"  ✔  Authenticated as: {r.json().get('name', 'unknown')}")
        return True
    print(f"  ✗  Authentication failed — HTTP {r.status_code}: {r.text[:200]}")
    return False


# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 — Find post ID by slug
# ──────────────────────────────────────────────────────────────────────────────
def find_post_id(slug: str, post_type: str):
    endpoints = [ENDPOINT_MAP.get(post_type, ENDPOINT_MAP["page"])]
    if ENDPOINT_MAP["page"] not in endpoints:
        endpoints.append(ENDPOINT_MAP["page"])

    for endpoint in endpoints:
        try:
            r = requests.get(endpoint, params={"slug": slug, "per_page": 1},
                             auth=AUTH, timeout=15)
            if r.status_code == 200 and r.json():
                return r.json()[0]["id"], endpoint
        except requests.RequestException as e:
            print(f"    ⚠  Network error: {e}")
    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — Fetch existing post data (title + content)
#           We re-send these back so WordPress fires the full save_post hook,
#           which is what triggers Yoast's server-side analysis engine.
# ──────────────────────────────────────────────────────────────────────────────
def fetch_post_data(post_id: int, base_endpoint: str) -> dict | None:
    r = requests.get(
        f"{base_endpoint}/{post_id}",
        params={"context": "edit"},
        auth=AUTH, timeout=15
    )
    if r.status_code != 200:
        print(f"    ⚠  Could not fetch post data: HTTP {r.status_code}")
        return None
 
    data = r.json()
 
    # Check Yoast meta fields are registered
    meta = data.get("meta", {})
    if DEBUG:
        yoast_keys = [k for k in meta if "yoast" in k]
        print(f"    ℹ  Yoast keys visible: {yoast_keys or 'NONE — plugin not active!'}")
 
    return {
        "title":   data.get("title", {}).get("raw", ""),
        "content": data.get("content", {}).get("raw", ""),
        "status":  data.get("status", "publish"),
        "meta":    meta,
    }
 
 
# ──────────────────────────────────────────────────────────────────────────────
# STEP 3 — Full save: meta + content + title in one payload
#           Including title/content forces WordPress to fire save_post,
#           which triggers Yoast's analysis and clears "Not analysed".
# ──────────────────────────────────────────────────────────────────────────────
def full_save_with_yoast_meta(post_id: int, base_endpoint: str,
                               page: dict, existing: dict) -> bool:
    payload = {
        "title":   existing["title"],    # re-send existing title unchanged
        "content": existing["content"],  # re-send existing content unchanged
        "status":  existing["status"],   # keep current publish status
        "meta":    build_yoast_meta(page),
    }
 
    r = requests.post(
        f"{base_endpoint}/{post_id}",
        json=payload, auth=AUTH, headers=HEADERS, timeout=30
    )
 
    if DEBUG:
        print(f"    ℹ  Full save status: {r.status_code}")
        if r.status_code not in (200, 201):
            print(f"    ℹ  Body: {r.text[:400]}")
 
    return r.status_code in (200, 201)
 
 
# ──────────────────────────────────────────────────────────────────────────────
# STEP 4 — Verify: check meta saved AND linkdex score is now set
#           _yoast_wpseo_linkdex = SEO analysis score (0–100)
#           If it's set (even 0), it means Yoast ran its analysis.
# ──────────────────────────────────────────────────────────────────────────────
def verify_update(post_id: int, base_endpoint: str, page: dict) -> bool:
    r = requests.get(
        f"{base_endpoint}/{post_id}",
        params={"context": "edit"},
        auth=AUTH, timeout=15
    )
    if r.status_code != 200:
        return False
 
    meta = r.json().get("meta", {})
 
    checks = {
        "_yoast_wpseo_focuskw":         page["focus_keyphrase"],
        "_yoast_wpseo_title":           page["seo_title"],
        "_yoast_wpseo_metadesc":        page["meta_description"],
        "_yoast_wpseo_bctitle":         page["breadcrumb_title"],
        "_yoast_wpseo_keywordsynonyms": json.dumps([page["synonyms"]]),
    }
 
    all_ok = True
    for key, expected in checks.items():
        saved = meta.get(key, "")
        if saved == expected:
            if DEBUG:
                print(f"    ✔  {key}")
        else:
            print(f"    ✗  MISMATCH: {key}")
            if DEBUG:
                print(f"         saved:    {str(saved)[:80]}")
                print(f"         expected: {expected[:80]}")
            all_ok = False
 
    # Check Yoast analysis score — present means analysis ran successfully
    linkdex = meta.get("_yoast_wpseo_linkdex", None)
    if linkdex is not None and linkdex != "":
        print(f"    ✔  Yoast SEO analysis score: {linkdex} (analysis ran ✓)")
    else:
        print(f"    ⚠  _yoast_wpseo_linkdex is empty — analysis may not have run yet.")
        print(f"       Open the page once in WP editor to trigger browser-side analysis.")
 
    return all_ok
 
 
# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 68)
    print("  Yoast SEO Bulk Updater v1.0")
    print("=" * 68)
 
    print("\n[Auth Check]")
    if not verify_auth():
        print("\n  Aborting — fix credentials and retry.")
        return
 
    success_count = 0
    fail_count    = 0
    plugin_warned = False
 
    for i, page in enumerate(SEO_DATA, start=1):
        slug      = page["slug"]
        post_type = page["post_type"]
        print(f"\n[{i:1d}/{len(SEO_DATA)}] {slug}")
 
        # 1 — Find post
        post_id, base_endpoint = find_post_id(slug, post_type)
        if not post_id:
            print(f"    ✗  Page NOT FOUND. Check slug or post_type.")
            fail_count += 1
            continue
        print(f"    ✔  Post ID: {post_id}")
 
        # 2 — Fetch existing content (needed to trigger save_post hook)
        existing = fetch_post_data(post_id, base_endpoint)
        if not existing:
            print(f"    ✗  Could not fetch existing post data. Skipping.")
            fail_count += 1
            continue
 
        if not existing["meta"] and not plugin_warned:
            print("\n  ┌──────────────────────────────────────────────────────────┐")
            print("  │  ⚠  Yoast meta NOT visible via REST API.                 │")
            print("  │     Install & activate: enable-yoast-rest-api.php v2.0   │")
            print("  │     Then re-run this script.                             │")
            print("  └──────────────────────────────────────────────────────────┘\n")
            plugin_warned = True
 
        # 3 — Full save (meta + existing content = triggers save_post hook)
        print(f"    ℹ  Saving meta + content to trigger Yoast analysis...")
        updated = full_save_with_yoast_meta(post_id, base_endpoint, page, existing)
        if not updated:
            print(f"    ✗  Save failed.")
            fail_count += 1
            continue
 
        # 4 — Verify
        if verify_update(post_id, base_endpoint, page):
            success_count += 1
        else:
            print("    ✗  Verification failed.")
            fail_count += 1
 
    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 68)
    print(f"  Done!  ✔ {success_count} pages updated   ✗ {fail_count} failed")
    print("=" * 68)
 
    print("""
  NOTE — About "Not analysed":
  ─────────────────────────────────────────────────────────────────
  This script triggers Yoast's SERVER-SIDE analysis by re-saving
  post content. However, Yoast also runs a BROWSER-SIDE analysis
  (readability, keyword density) when you open the page in the
  WordPress block editor.
 
  After running this script:
    ✔  Focus keyphrase, SEO title, meta, synonyms  → saved via API
    ✔  Server-side Yoast hooks                     → triggered
    ⚠  Full green analysis bullets in editor       → open each page
       once in WP Admin → Pages and click Update.
       This completes the browser-side analysis.
    """)
 
 
if __name__ == "__main__":
    main()
 
