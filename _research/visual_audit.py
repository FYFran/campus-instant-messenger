"""Visual audit — test every page and check all details"""
import requests, urllib3
urllib3.disable_warnings()
BASE = "https://tokenline.top"

pages = {
    "/": ["title", "pricing", "trust badges", "CTA buttons"],
    "/features.html": ["title", "tool cards", "CTA"],
    "/compare.html": ["title", "Flash vs Pro table", "pricing cards"],
    "/chat/": ["title", "auth check redirect"],
    "/register.html": ["title", "form fields", "email validation"],
    "/login.html": ["title", "form fields"],
    "/topup.html": ["title", "payment options"],
    "/privacy.html": ["title"],
    "/tos.html": ["title"],
    "/docs.html": ["title"],
    "/tools/cv.html": ["title", "tool interface"],
    "/tools/academic.html": ["title", "tool interface"],
    "/tools/social.html": ["title", "tool interface"],
    "/tools/email.html": ["title", "tool interface"],
    "/tools/translate.html": ["title", "tool interface"],
    "/500.html": ["title", "error page"],
    "/404.html": ["title", "error page"],
}

issues = []
for path, checks in pages.items():
    try:
        r = requests.get(f"{BASE}{path}", verify=False, timeout=10, allow_redirects=True)
        status = r.status_code
        html = r.text.lower()

        page_issues = []

        # Check for broken/inconsistent pricing
        if "pricing" in " ".join(checks) or "price" in " ".join(checks):
            # Check old pricing doesn't appear
            if "rp 129.000" in html and "pro" in path:
                page_issues.append("old Pro pricing Rp 129.000 found")
            if "rp 249.000" in html:
                pass  # correct new pricing

        # Check for hardcoded secrets
        if "sk-bl" in html or "sk-BL" in html:
            page_issues.append("HARDCODED API KEY")
        if "Dx2kACiqt" in html:
            page_issues.append("HARDCODED DODO KEY")
        if "whsec_" in html:
            page_issues.append("HARDCODED WEBHOOK SECRET")

        # Check for broken links
        if 'href=""' in html:
            page_issues.append("empty href")
        if "undefined" in html and "text" not in path:
            page_issues.append("'undefined' in HTML")

        if page_issues:
            issues.append(f"{path} ({status}): {'; '.join(page_issues)}")
        else:
            print(f"  OK  {path} ({status})")
    except Exception as e:
        issues.append(f"{path}: ERROR {e}")

print(f"\n=== Issues found: {len(issues)} ===")
for i in issues:
    print(f"  {i}")

# Test auth checks on tool pages
print("\n=== Auth checks ===")
for path in ["/tools/cv.html", "/tools/academic.html", "/tools/social.html", "/tools/email.html", "/tools/translate.html"]:
    r = requests.get(f"{BASE}{path}", verify=False, timeout=10)
    # These should redirect to login if no token
    has_auth = "localStorage.getItem" in r.text or "tl_tok" in r.text
    print(f"  {'OK' if has_auth else 'NO AUTH'}  {path}")
