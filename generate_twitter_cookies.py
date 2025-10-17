from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import json
import time

def generate_twitter_cookies():
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        print("Opening Twitter login page...")
        driver.get("https://x.com/login")
        time.sleep(5)
        
        print("Manually log in to Twitter (handle CAPTCHA/2FA), then press Enter...")
        input()
        time.sleep(5)
        
        cookies = driver.get_cookies()
        with open("cookies.json", "w") as f:
            json.dump(cookies, f, indent=2)
        
        print(f"Cookies saved to cookies.json ({len(cookies)} cookies exported).")
        
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    generate_twitter_cookies()
    