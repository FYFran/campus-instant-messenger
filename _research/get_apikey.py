"""Click country code +91 and change to +86 for China"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("47.82.103.247", username="root", password="ROOT_PASSWORD_CHANGED_20260615", timeout=15, look_for_keys=False, allow_agent=False)

script = '''
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        print("1. Login...")
        await page.goto("https://console.messagecentral.com/", timeout=45000)
        await page.wait_for_timeout(5000)
        await page.locator("text=Log in").first.click()
        await page.wait_for_timeout(3000)
        await page.locator('input[type="email"]').first.fill("3170474192@qq.com")
        await page.locator('input[type="password"]').first.fill("ROOT_PASSWORD_CHANGED_20260615")
        await page.locator('button:has-text("Log in"), button:has-text("Login")').first.click()
        await page.wait_for_timeout(10000)
        print("   URL:", page.url)

        await page.screenshot(path="/tmp/mc_before.png")
        body = await page.inner_text("body")

        # The country code is shown as text "+91". Let's find the clickable element.
        # It's likely an input or div that opens a dropdown
        print("2. Looking for country code selector...")
        await page.wait_for_timeout(2000)

        # Try clicking on the "+91" text directly
        plus91 = page.locator("text=+91").first
        if await plus91.count() > 0:
            print("   Clicking +91...")
            await plus91.click()
            await page.wait_for_timeout(2000)

            # Now look for +86 in the dropdown
            plus86 = page.locator("text=+86").first
            cn = page.locator("text=China").first
            if await plus86.count() > 0:
                print("   Found +86, clicking...")
                await plus86.click()
                await page.wait_for_timeout(1000)
            elif await cn.count() > 0:
                print("   Found China, clicking...")
                await cn.click()
                await page.wait_for_timeout(1000)
            else:
                # Type +86 as search in dropdown
                search = page.locator('input[placeholder*="Search"], input[placeholder*="search"]').first
                if await search.count() > 0:
                    await search.fill("China")
                    await page.wait_for_timeout(1000)
                    await page.locator("text=China").first.click()
                    await page.wait_for_timeout(1000)
                    print("   Searched and clicked China")
        else:
            print("   No +91 text found, body:", body[:500])

        await page.screenshot(path="/tmp/mc_country.png")

        # Now try to find phone input and fill
        phone = page.locator('input[type="tel"], input[name*="mobile"], input[name*="phone"]').first
        count = await phone.count()
        print(f"3. Phone inputs: {count}")

        # Click on the phone input area to focus
        if count == 0:
            # Look for any input that is NOT email/password
            all_inputs = await page.query_selector_all("input")
            for inp in all_inputs:
                t = await inp.get_attribute("type")
                pl = await inp.get_attribute("placeholder") or ""
                nm = await inp.get_attribute("name") or ""
                val = await inp.input_value()
                print(f"   Input: type={t} val={val} placeholder={pl} name={nm}")
                if t not in ["email", "password"] and val == "":
                    await inp.click()
                    await inp.fill("18896691078")
                    print(f"   Filled unknown input with phone")
                    break

        # Click send OTP
        await page.wait_for_timeout(1000)
        send_btn = page.locator('button:has-text("Send OTP"), button:has-text("Verify"), button:has-text("Next")').first
        if await send_btn.count() > 0:
            print(f"4. Clicking send OTP...")
            await send_btn.click()
            await page.wait_for_timeout(8000)
            print("   URL:", page.url)
            print("   Body:", (await page.inner_text("body"))[:600])

        await page.screenshot(path="/tmp/mc_sent.png")
        await browser.close()

asyncio.run(main())
'''

stdin, stdout, stderr = c.exec_command("cat > /tmp/verify2.py << 'PYEOF'\n" + script + "\nPYEOF\npython3 /tmp/verify2.py 2>&1", timeout=120)
out = stdout.read().decode(errors='replace')
err = stderr.read().decode(errors='replace')
print(out)
if err: print("ERR:", err[:500])

for f in ["/tmp/mc_before.png", "/tmp/mc_country.png", "/tmp/mc_sent.png"]:
    try:
        sftp = c.open_sftp()
        sftp.get(f, f.replace("/tmp/", "f:/ClaudeFiles/_research/"))
        sftp.close()
    except:
        pass

c.close()
