import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

print("=" * 60)
print("Instagram Cookie Generator")
print("=" * 60)

chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    driver.get("https://www.instagram.com")
    print("\n📱 Instagram login page opened in browser")
    print("\n⚠️  IMPORTANT STEPS:")
    print("1. Log in to your Instagram account manually")
    print("2. Wait until you see your feed/homepage")
    print("3. Make sure you're fully logged in")
    print("4. Press Enter here in the terminal to save cookies...")
    
    input("\n👉 Press Enter after logging in: ")
    
    # Wait a bit more to ensure everything is loaded
    time.sleep(3)
    
    cookies = driver.get_cookies()
    
    with open('instagram_cookies.json', 'w') as f:
        json.dump(cookies, f, indent=2)
    
    print(f"\n✅ Success! Saved {len(cookies)} cookies to 'instagram_cookies.json'")
    print(f"📁 File location: {os.path.abspath('instagram_cookies.json')}")
    print("\n⚠️  Cookie details:")
    
    # Show important cookies
    important_cookies = ['sessionid', 'ds_user_id', 'csrftoken']
    found_cookies = []
    for cookie in cookies:
        if cookie['name'] in important_cookies:
            found_cookies.append(cookie['name'])
    
    if len(found_cookies) >= 2:
        print(f"✓ Found essential cookies: {', '.join(found_cookies)}")
    else:
        print("⚠️  Warning: Some essential cookies may be missing. Try logging in again.")
    
    print("\n🔒 These cookies will expire. Regenerate them if you get login errors.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("Please try again or check your internet connection.")

finally:
    print("\nClosing browser...")
    driver.quit()
    print("Done! You can now use app.py to scrape Instagram posts.")

import os  # Add this at top if not present