from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

def debug_order_book():
    # Setup Chrome
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    print("Browser started.")
    print("PLEASE LOG IN MANUALLY.")
    print("Navigate to 'Order Management > Daily Order Book'.")
    print("Ensure you have at least one OPEN/PENDING order visible if possible.")
    
    # Wait for user to be ready
    input("Press Enter here in the terminal once you are on the Daily Order Book page...")

    try:
        print("Capturing page details...")
        time.sleep(3) # Wait for page stability

        # 1. Log Context
        print(f"Current URL: {driver.current_url}")
        print(f"Current Title: {driver.title}")

        # 2. Robust Source Capture
        src = driver.page_source
        if src:
            with open("order_book_source.html", "w", encoding="utf-8") as f:
                f.write(src)
            print(f"Saved 'order_book_source.html' ({len(src)} bytes).")
        else:
            print("ERROR: driver.page_source is None/Empty!")

        # 3. List Buttons with detail
        print("\n--- BUTTONS ---")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for i, btn in enumerate(buttons):
            try:
                txt = btn.text.strip()
                cls = btn.get_attribute("class")
                bid = btn.get_attribute("id")
                title = btn.get_attribute("title")
                # Highlight modification related buttons
                is_modify = "modify" in txt.lower() or "edit" in cls.lower() or "fa-pencil" in cls.lower()
                prefix = ">>> MODIFY CANDIDATE <<< " if is_modify else ""
                print(f"{prefix}Button {i}: Text='{txt}', Id='{bid}', Class='{cls}', Title='{title}'")
            except:
                pass

        # 4. List Links that might be buttons
        print("\n--- LINKS (A tags) ---")
        links = driver.find_elements(By.TAG_NAME, "a")
        for i, link in enumerate(links):
            try:
                txt = link.text.strip()
                cls = link.get_attribute("class")
                title = link.get_attribute("title")
                # Filter out navigation
                if txt and len(txt) < 30:
                     print(f"Link {i}: Text='{txt}', Class='{cls}', Title='{title}'")
            except:
                pass

        # 5. List Icons (fa-edit, etc.)
        print("\n--- ICONS ---")
        icons = driver.find_elements(By.CSS_SELECTOR, "i[class*='edit'], i[class*='pencil'], span[class*='edit']")
        for i, icon in enumerate(icons):
             print(f"Icon {i}: Class='{icon.get_attribute('class')}', Parent='{icon.find_element(By.XPATH, '..').tag_name}'")

        print("\nCapture complete. You can close the browser.")

    except Exception as e:
        print(f"Global Error: {e}")
    finally:
        print("Done.")

if __name__ == "__main__":
    debug_order_book()
