"""Auto-register Message Central from HK server using Playwright"""
import paramiko, time, json

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

# Write the playwright script to server
script = '''
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Go to console signup
        print("Opening signup page...")
        await page.goto("https://console.messagecentral.com/signup", timeout=30000)
        await page.wait_for_timeout(3000)
        print("Page title:", await page.title())

        # Try to find and fill email field
        inputs = await page.query_selector_all("input")
        print(f"Found {len(inputs)} input fields")
        for i, inp in enumerate(inputs):
            name = await inp.get_attribute("name")
            id_ = await inp.get_attribute("id")
            typ = await inp.get_attribute("type")
            placeholder = await inp.get_attribute("placeholder")
            print(f"  Input {i}: name={name} id={id_} type={typ} placeholder={placeholder}")

        # Try to fill the form
        email_field = await page.query_selector('input[type="email"]') or await page.query_selector('input[name="email"]') or await page.query_selector('input[id="email"]')
        if email_field:
            await email_field.fill("3170474192@qq.com")
            print("Filled email")

        pw_field = await page.query_selector('input[type="password"]') or await page.query_selector('input[name="password"]')
        if pw_field:
            await pw_field.fill("ROOT_PASSWORD_CHANGED_20260615")
            print("Filled password")

        # Try to find and click signup button
        btn = await page.query_selector('button[type="submit"]') or await page.query_selector('button:has-text("Sign")') or await page.query_selector('button:has-text("Register")') or await page.query_selector('button:has-text("Create")')
        if btn:
            print(f"Found button: {await btn.text_content()}")
            await btn.click()
            await page.wait_for_timeout(5000)
            print("Clicked signup, current URL:", page.url)

        # Screenshot for debugging
        await page.screenshot(path="/tmp/mc_signup.png")
        print("Screenshot saved to /tmp/mc_signup.png")

        # Get page content
        content = await page.content()
        print("Page text:", (await page.inner_text("body"))[:1000])

        await browser.close()

asyncio.run(main())
'''

# Write script to server and run
stdin, stdout, stderr = c.exec_command("cat > /tmp/reg.py << 'PYEOF'\n" + script + "\nPYEOF\npython3 /tmp/reg.py 2>&1", timeout=60)
out = stdout.read().decode(errors='replace')
err = stderr.read().decode(errors='replace')
print(out)
if err: print("STDERR:", err[:500])

# Also copy screenshot back
try:
    sftp = c.open_sftp()
    sftp.get("/tmp/mc_signup.png", "f:/ClaudeFiles/_research/mc_signup.png")
    sftp.close()
    print("\nScreenshot downloaded to mc_signup.png")
except Exception as e:
    print(f"Screenshot download failed: {e}")

c.close()
