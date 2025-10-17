import json
import time
import random
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd

# Try to import pipeline from transformers
try:
    from transformers import pipeline
    transformers_available = True
except ImportError as e:
    st.error(f"Failed to import 'pipeline' from transformers: {e}. Using TextBlob as fallback.")
    transformers_available = False

# Fallback to TextBlob
try:
    from textblob import TextBlob
    textblob_available = True
except ImportError as e:
    st.error(f"Failed to import TextBlob: {e}. Install with 'pip install textblob'.")
    textblob_available = False

# Initialize sentiment analysis pipeline
@st.cache_resource
def load_sentiment_pipeline():
    if transformers_available:
        try:
            return pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")
        except Exception as e:
            st.warning(f"Failed to load multilingual model: {e}. Falling back to English model.")
            try:
                return pipeline("sentiment-analysis", model="finiteautomata/bertweet-base-sentiment-analysis")
            except Exception as fallback_e:
                st.error(f"Fallback model load failed: {fallback_e}. Using TextBlob.")
                return None
    elif textblob_available:
        st.warning("Using TextBlob for sentiment analysis.")
        return None
    else:
        st.error("No sentiment analysis available.")
        return None

def create_driver(headless=True):
    """Create a Chrome driver with improved options"""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument(f"--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

# Function to fetch posts from Twitter
@st.cache_data(ttl=300)
def fetch_twitter_posts(username, max_posts=100):
    driver = create_driver(headless=True)
    
    try:
        with open('cookies.json', 'r') as f:
            cookies = json.load(f)
        
        profile_url = f"https://x.com/{username}"
        driver.get(profile_url)
        time.sleep(random.uniform(3, 5))
        
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        
        driver.refresh()
        time.sleep(random.uniform(5, 7))
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
                )
                break
            except Exception as e:
                st.warning(f"Twitter fetch attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(5, 10))
                    driver.refresh()
                    continue
                raise
        
        posts = []
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while len(posts) < max_posts:
            articles = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            for article in articles[len(posts):]:
                try:
                    text_element = article.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]')
                    post_text = text_element.text.strip()
                    time_element = article.find_element(By.CSS_SELECTOR, 'time')
                    timestamp = time_element.get_attribute('datetime') if time_element else "Unknown"
                    if post_text:
                        posts.append({'text': post_text, 'timestamp': timestamp})
                    if len(posts) >= max_posts:
                        break
                except Exception:
                    continue
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 4))
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        return posts[:max_posts]
    finally:
        driver.quit()

# Function to fetch posts from LinkedIn - IMPROVED
@st.cache_data(ttl=300)
def fetch_linkedin_posts(url, max_posts=100):
    driver = create_driver(headless=True)
    
    try:
        try:
            with open('linkedin_cookies.json', 'r') as f:
                cookies = json.load(f)
                st.info(f"Loaded {len(cookies)} LinkedIn cookies")
                
                # Check for critical li_at cookie
                has_li_at = any(c.get('name') == 'li_at' for c in cookies)
                if not has_li_at:
                    st.error("❌ Critical 'li_at' cookie missing! Regenerate linkedin_cookies.json")
                    return []
                st.success("✓ Found 'li_at' authentication cookie")
                
        except FileNotFoundError:
            st.error("linkedin_cookies.json not found. Run generate_linkedin_cookies.py first!")
            return []
        
        # Navigate to LinkedIn homepage first
        st.info("Step 1: Loading LinkedIn homepage...")
        driver.get("https://www.linkedin.com")
        time.sleep(2)
        
        # Add cookies with better handling
        cookies_added = 0
        for cookie in cookies:
            try:
                # Clean cookie data
                if 'sameSite' in cookie:
                    if cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                        cookie['sameSite'] = 'None'
                if 'expiry' in cookie:
                    cookie['expiry'] = int(cookie['expiry'])
                
                driver.add_cookie(cookie)
                cookies_added += 1
            except Exception as e:
                continue
        
        st.info(f"Step 2: Added {cookies_added}/{len(cookies)} cookies")
        
        # Refresh to apply cookies
        driver.refresh()
        time.sleep(3)
        
        # Verify login by checking current URL
        current_url = driver.current_url
        st.info(f"Step 3: Current URL: {current_url[:50]}...")
        
        if "authwall" in current_url or "login" in current_url:
            st.error("❌ Not logged in! Cookies are expired or invalid.")
            st.info("🔄 Run generate_linkedin_cookies.py to create fresh cookies")
            return []
        
        st.success("✓ Successfully authenticated!")
        
        # Navigate to the target URL
        st.info(f"Step 4: Navigating to {url}...")
        driver.get(url)
        time.sleep(random.uniform(5, 7))
        
        # Check if redirected to login
        if "authwall" in driver.current_url or "login" in driver.current_url:
            st.error("❌ Redirected to login. Session invalid.")
            return []
        
        # Try to go to posts section
        posts_url = url.rstrip('/') + '/posts/'
        st.info(f"Step 5: Loading posts from {posts_url}...")
        driver.get(posts_url)
        time.sleep(random.uniform(6, 9))
        
        # Multiple strategies to find posts
        st.info("Step 6: Looking for posts on page...")
        
        # Try multiple selectors
        post_selectors = [
            'div.feed-shared-update-v2',
            'div[data-urn*="activity"]',
            'div.feed-shared-update-v2__description-wrapper',
            'div[class*="feed-shared-update"]'
        ]
        
        posts_found = False
        for selector in post_selectors:
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, selector)) > 0
                )
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if len(elements) > 0:
                    st.success(f"✓ Found {len(elements)} posts using selector: {selector}")
                    posts_found = True
                    break
            except TimeoutException:
                continue
        
        if not posts_found:
            st.error("❌ No posts found on page. Possible reasons:")
            st.warning("1. LinkedIn UI changed (selectors outdated)")
            st.warning("2. Profile/company has no recent posts")
            st.warning("3. Posts are restricted/private")
            st.info(f"Current page URL: {driver.current_url}")
            
            # Take screenshot for debugging
            try:
                driver.save_screenshot("linkedin_debug.png")
                st.info("💾 Saved screenshot as linkedin_debug.png for debugging")
            except:
                pass
            
            return []
        
        posts = []
        last_height = driver.execute_script("return document.body.scrollHeight")
        no_new_posts_count = 0
        
        while len(posts) < max_posts and no_new_posts_count < 3:
            # Multiple selectors for LinkedIn posts
            articles = driver.find_elements(By.CSS_SELECTOR, 'div.feed-shared-update-v2')
            if not articles:
                articles = driver.find_elements(By.CSS_SELECTOR, 'div[data-urn*="activity"]')
            
            initial_count = len(posts)
            
            for article in articles:
                if len(posts) >= max_posts:
                    break
                    
                try:
                    # Scroll element into view
                    driver.execute_script("arguments[0].scrollIntoView(true);", article)
                    time.sleep(0.5)
                    
                    # Try to click "see more" button
                    try:
                        see_more_buttons = article.find_elements(By.CSS_SELECTOR, 'button.feed-shared-inline-show-more-text__see-more-less-toggle, button[aria-label*="see more"]')
                        for btn in see_more_buttons:
                            try:
                                driver.execute_script("arguments[0].click();", btn)
                                time.sleep(0.5)
                            except:
                                pass
                    except:
                        pass
                    
                    # Extract post text with multiple methods
                    post_text = ""
                    
                    # Method 1: Look for specific text containers
                    text_selectors = [
                        'div.feed-shared-update-v2__description span[dir="ltr"]',
                        'div.feed-shared-text span[dir="ltr"]',
                        'div.update-components-text span',
                        'span.break-words'
                    ]
                    
                    for selector in text_selectors:
                        try:
                            elements = article.find_elements(By.CSS_SELECTOR, selector)
                            for elem in elements:
                                text = elem.text.strip()
                                if text and text not in post_text:
                                    post_text += text + " "
                        except:
                            continue
                    
                    # Clean up the text
                    post_text = post_text.strip()
                    
                    # Extract timestamp
                    timestamp = "Unknown"
                    try:
                        time_selectors = ['time', 'span.feed-shared-actor__sub-description']
                        for selector in time_selectors:
                            try:
                                time_elem = article.find_element(By.CSS_SELECTOR, selector)
                                timestamp = time_elem.get_attribute('datetime') or time_elem.text.strip()
                                if timestamp:
                                    break
                            except:
                                continue
                    except:
                        pass
                    
                    # Only add if we got meaningful text
                    if post_text and len(post_text) > 20:
                        # Check for duplicates
                        if not any(p['text'] == post_text for p in posts):
                            posts.append({'text': post_text, 'timestamp': timestamp})
                            st.success(f"✓ Fetched post {len(posts)}/{max_posts}")
                
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    continue
            
            # Check if we got new posts
            if len(posts) == initial_count:
                no_new_posts_count += 1
            else:
                no_new_posts_count = 0
            
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(3, 5))
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                no_new_posts_count += 1
            last_height = new_height
        
        st.success(f"Successfully fetched {len(posts)} LinkedIn posts")
        return posts[:max_posts]
    
    except Exception as e:
        st.error(f"Error fetching LinkedIn posts: {str(e)}")
        return []
    finally:
        driver.quit()

# Function to fetch posts from Instagram - IMPROVED
@st.cache_data(ttl=300)
def fetch_instagram_posts(username, max_posts=100):
    driver = create_driver(headless=False)  # Non-headless for better compatibility
    
    try:
        try:
            with open('instagram_cookies.json', 'r') as f:
                cookies = json.load(f)
                st.success(f"Loaded {len(cookies)} Instagram cookies")
        except FileNotFoundError:
            st.error("instagram_cookies.json not found. Generate it using Cookie-Editor on Instagram.")
            return []
        
        # Navigate to Instagram
        driver.get("https://www.instagram.com")
        time.sleep(3)
        
        # Add cookies
        for cookie in cookies:
            try:
                if 'sameSite' in cookie:
                    if cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                        cookie['sameSite'] = 'None'
                driver.add_cookie(cookie)
            except Exception:
                pass
        
        # Refresh to apply cookies
        driver.refresh()
        time.sleep(5)
        
        # Navigate to profile
        profile_url = f"https://www.instagram.com/{username}/"
        st.info(f"Navigating to {profile_url}")
        driver.get(profile_url)
        time.sleep(7)
        
        # Check if logged in
        if "login" in driver.current_url.lower():
            st.error("Instagram login required. Cookies expired. Please regenerate instagram_cookies.json")
            return []
        
        # Close any popups
        try:
            not_now_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Not Now')] | //button[contains(text(), 'Not now')]")
            for btn in not_now_buttons:
                try:
                    btn.click()
                    time.sleep(1)
                except:
                    pass
        except:
            pass
        
        # Wait for posts
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/p/"], a[href*="/reel/"]'))
            )
        except TimeoutException:
            st.error("Could not load Instagram posts. Profile may be private or cookies expired.")
            return []
        
        posts = []
        post_links = set()
        
        # Scroll to collect post links
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 15
        
        while len(post_links) < max_posts and scroll_attempts < max_scroll_attempts:
            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/p/"], a[href*="/reel/"]')
            for link in links:
                href = link.get_attribute('href')
                if href and ('/p/' in href or '/reel/' in href):
                    post_links.add(href)
                if len(post_links) >= max_posts:
                    break
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 4))
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scroll_attempts += 1
        
        post_links = list(post_links)[:max_posts]
        st.info(f"Found {len(post_links)} post links. Extracting captions...")
        
        # Visit each post
        for idx, post_link in enumerate(post_links):
            try:
                driver.get(post_link)
                time.sleep(random.uniform(3, 5))
                
                # Wait for page load
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, 'article'))
                    )
                except:
                    pass
                
                post_text = ""
                
                # Method 1: Look for h1 tags (username and caption)
                try:
                    h1_elements = driver.find_elements(By.TAG_NAME, 'h1')
                    for h1 in h1_elements:
                        text = h1.text.strip()
                        # Skip if it's just the username
                        if text and text.lower() != username.lower() and len(text) > len(username) + 2:
                            # Remove username from beginning if present
                            if text.lower().startswith(username.lower()):
                                text = text[len(username):].strip()
                            post_text = text
                            break
                except:
                    pass
                
                # Method 2: Look for span elements with specific classes
                if not post_text:
                    try:
                        span_selectors = [
                            'span._ap3a._aaco._aacu._aacx._aad7._aade',
                            'span.x1lliihq',
                            'span[style*="line-height"]',
                            'div.x1lliihq span'
                        ]
                        for selector in span_selectors:
                            try:
                                spans = driver.find_elements(By.CSS_SELECTOR, selector)
                                for span in spans:
                                    text = span.text.strip()
                                    if text and len(text) > 10 and text.lower() != username.lower():
                                        post_text = text
                                        break
                                if post_text:
                                    break
                            except:
                                continue
                    except:
                        pass
                
                # Method 3: Get all text from article and extract meaningful parts
                if not post_text:
                    try:
                        article = driver.find_element(By.TAG_NAME, 'article')
                        full_text = article.text
                        lines = [line.strip() for line in full_text.split('\n')]
                        # Filter out common Instagram UI elements
                        meaningful_lines = []
                        skip_words = ['like', 'likes', 'comment', 'comments', 'share', 'save', 'follow', 'following', 'followers']
                        for line in lines:
                            if len(line) > 15 and not any(word in line.lower() for word in skip_words):
                                if line.lower() != username.lower():
                                    meaningful_lines.append(line)
                        if meaningful_lines:
                            post_text = ' '.join(meaningful_lines[:2])  # Take first 2 meaningful lines
                    except:
                        pass
                
                # Get timestamp
                timestamp = "Unknown"
                try:
                    time_element = driver.find_element(By.CSS_SELECTOR, 'time[datetime]')
                    timestamp = time_element.get_attribute('datetime')
                except:
                    try:
                        time_element = driver.find_element(By.XPATH, "//time")
                        timestamp = time_element.get_attribute('title') or time_element.get_attribute('datetime') or time_element.text
                    except:
                        pass
                
                post_text = post_text.strip()
                if post_text:
                    posts.append({'text': post_text, 'timestamp': timestamp})
                    st.success(f"✓ Post {idx+1}/{len(post_links)}: {len(post_text)} chars")
                else:
                    posts.append({'text': '[Image/Video post - No caption available]', 'timestamp': timestamp})
                    st.info(f"ℹ Post {idx+1}/{len(post_links)}: No caption")
                
            except Exception as e:
                st.warning(f"⚠ Error on post {idx+1}: {str(e)[:100]}")
                continue
        
        st.success(f"Extracted {len(posts)} Instagram posts")
        return posts
    
    except Exception as e:
        st.error(f"Instagram error: {str(e)}")
        return []
    finally:
        driver.quit()

# Function to fetch posts from Facebook - IMPROVED
@st.cache_data(ttl=300)
def fetch_facebook_posts(page_url, max_posts=100):
    driver = create_driver(headless=True)
    
    try:
        try:
            with open('facebook_cookies.json', 'r') as f:
                cookies = json.load(f)
                st.info(f"Loaded {len(cookies)} Facebook cookies")
        except FileNotFoundError:
            st.error("facebook_cookies.json not found. Generate it using Cookie-Editor on Facebook.")
            return []
        
        driver.get("https://www.facebook.com")
        time.sleep(3)
        
        for cookie in cookies:
            try:
                if 'sameSite' in cookie:
                    if cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                        cookie['sameSite'] = 'None'
                driver.add_cookie(cookie)
            except:
                pass
        
        driver.refresh()
        time.sleep(5)
        
        driver.get(page_url)
        time.sleep(random.uniform(5, 8))
        
        # Check login
        if "login" in driver.current_url.lower():
            st.error("Facebook login required. Cookies expired. Refresh facebook_cookies.json.")
            return []
        
        posts = []
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 25
        
        while len(posts) < max_posts and scroll_attempts < max_scroll_attempts:
            # Multiple selectors for Facebook posts
            post_selectors = [
                'div[data-ad-preview="message"]',
                'div.userContent',
                'div[data-ad-comet-preview="message"]',
                'div[dir="auto"][style*="text-align"]'
            ]
            
            post_elements = []
            for selector in post_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                post_elements.extend(elements)
            
            for post_elem in post_elements:
                if len(posts) >= max_posts:
                    break
                
                try:
                    # Try to expand "See More"
                    try:
                        see_more_selectors = [
                            'div[role="button"]',
                            'div.see_more_link',
                            '[aria-label*="See more"]',
                            '[aria-label*="See More"]'
                        ]
                        for selector in see_more_selectors:
                            try:
                                see_more = post_elem.find_element(By.CSS_SELECTOR, selector)
                                if "see more" in see_more.text.lower():
                                    driver.execute_script("arguments[0].click();", see_more)
                                    time.sleep(1)
                                    break
                            except:
                                continue
                    except:
                        pass
                    
                    post_text = post_elem.text.strip()
                    
                    # Get timestamp
                    timestamp = "Unknown"
                    try:
                        time_selectors = ['abbr', 'span[id*="date"]', 'a[href*="posts"]']
                        for selector in time_selectors:
                            try:
                                time_elem = post_elem.find_element(By.CSS_SELECTOR, selector)
                                timestamp = time_elem.get_attribute('data-utime') or time_elem.get_attribute('title') or time_elem.text
                                if timestamp:
                                    break
                            except:
                                continue
                    except:
                        pass
                    
                    if post_text and len(post_text) > 20:
                        # Check for duplicates
                        if not any(p['text'] == post_text for p in posts):
                            posts.append({'text': post_text, 'timestamp': timestamp})
                            st.success(f"✓ Fetched Facebook post {len(posts)}/{max_posts}")
                
                except:
                    continue
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(3, 6))
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            last_height = new_height
        
        st.success(f"Fetched {len(posts)} Facebook posts")
        return posts
    
    except Exception as e:
        st.error(f"Facebook error: {str(e)}")
        return []
    finally:
        driver.quit()

# Analyze sentiment
def analyze_sentiment(text, sentiment_pipeline):
    sentiment = "Unknown"
    confidence = "0.00"
    
    try:
        if sentiment_pipeline:
            if transformers_available:
                result = sentiment_pipeline(text[:512])[0]
                label = result['label'].lower()
                score = result['score']
                
                if 'star' in label:
                    if label in ['1 star', '2 stars']:
                        sentiment = 'Negative'
                    elif label == '3 stars':
                        sentiment = 'Neutral'
                    elif label in ['4 stars', '5 stars']:
                        sentiment = 'Positive'
                else:
                    if label in ['neg', 'negative']:
                        sentiment = 'Negative'
                    elif label in ['neu', 'neutral']:
                        sentiment = 'Neutral'
                    elif label in ['pos', 'positive']:
                        sentiment = 'Positive'
                confidence = f"{score:.2f}"
            elif textblob_available:
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity
                if polarity > 0.1:
                    sentiment = 'Positive'
                elif polarity < -0.1:
                    sentiment = 'Negative'
                else:
                    sentiment = 'Neutral'
                confidence = f"{abs(polarity):.2f}"
    except Exception as e:
        st.warning(f"Error analyzing text: {e}")
    
    return sentiment, confidence

# Streamlit App
st.title("🔍 Social Media Sentiment Analyzer")
st.write("Select a platform, enter the username/URL, and fetch posts to analyze sentiment.")

platform = st.selectbox("Select Platform", ["Twitter", "LinkedIn", "Instagram", "Facebook"])

if platform == "Twitter":
    identifier = st.text_input("Enter Twitter Username (without @)", value="")
    fetch_func = fetch_twitter_posts
elif platform == "LinkedIn":
    identifier = st.text_input("Enter LinkedIn Company/Profile URL", 
                               value="",
                               help="e.g., https://www.linkedin.com/company/microsoft/")
    fetch_func = fetch_linkedin_posts
elif platform == "Instagram":
    identifier = st.text_input("Enter Instagram Username (without @)", value="")
    fetch_func = fetch_instagram_posts
elif platform == "Facebook":
    identifier = st.text_input("Enter Facebook Page URL", 
                               value="",
                               help="e.g., https://www.facebook.com/microsoft")
    fetch_func = fetch_facebook_posts

max_posts = st.slider("Max number of posts to fetch", min_value=1, max_value=100, value=20)

if st.button("Fetch Posts") and identifier:
    with st.spinner(f"Fetching and analyzing posts from {platform}..."):
        posts = fetch_func(identifier, max_posts)
        
        if not posts:
            st.error("No posts fetched. Check identifier or cookies.")
        else:
            sentiment_pipeline = load_sentiment_pipeline()
            analyzed_posts = []
            
            progress_bar = st.progress(0)
            for idx, post in enumerate(posts):
                sentiment, confidence = analyze_sentiment(post['text'], sentiment_pipeline)
                analyzed_posts.append({
                    **post,
                    'sentiment': sentiment,
                    'confidence': confidence
                })
                progress_bar.progress((idx + 1) / len(posts))
            
            st.subheader(f"📊 Fetched {len(analyzed_posts)} Posts from {identifier}")
            df = pd.DataFrame(analyzed_posts)
            
            # Display table with colored sentiment
            for index, row in df.iterrows():
                sentiment = row['sentiment']
                color = "green" if sentiment == "Positive" else "red" if sentiment == "Negative" else "blue"
                st.markdown(f"<div style='color: white; background-color: {color}; padding: 10px; margin-bottom: 10px; border-radius: 5px;'>"
                            f"<strong>Text:</strong> {row['text'][:200]}{'...' if len(row['text']) > 200 else ''} <br>"
                            f"<strong>Timestamp:</strong> {row['timestamp']} <br>"
                            f"<strong>Sentiment:</strong> {sentiment} (Confidence: {row['confidence']})</div>", unsafe_allow_html=True)
            
            # Sentiment summary
            sentiment_counts = df['sentiment'].value_counts()
            st.subheader("📈 Sentiment Summary")
            st.bar_chart(sentiment_counts)
            
            # Download CSV
            csv = df.to_csv(index=False)
            st.download_button(
                label="⬇️ Download Results as CSV",
                data=csv,
                file_name=f"{platform.lower()}_sentiment_analysis.csv",
                mime="text/csv"
            )

st.write("---")
st.info("💡 **Important Cookie Setup Instructions:**\n\n"
        "1. Install Cookie-Editor browser extension\n"
        "2. Login to the platform (LinkedIn/Instagram/Facebook)\n"
        "3. Click Cookie-Editor icon and export cookies as JSON\n"
        "4. Save as `linkedin_cookies.json`, `instagram_cookies.json`, or `facebook_cookies.json`\n"
        "5. Place the file in the same directory as this script\n"
        "6. Cookies expire - regenerate them if you get login errors")