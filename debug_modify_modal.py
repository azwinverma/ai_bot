from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def debug_modify_modal():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    print("Browser started.")
    print("PLEASE LOG IN MANUALLY.")
    print("Navigate to 'Order Management > Daily Order Book'.")
    
    input("Press Enter once you are on the Daily Order Book page with at least one OPEN order...")

    try:
        # Find the modify button
        print("Looking for Modify button...")
        # Try finding by the icon class we saw: nf-table-edit inside table--edit
        # xpath: //span[contains(@class, 'table--edit')]
        modify_btns = driver.find_elements(By.XPATH, "//span[contains(@class, 'table--edit')]")
        
        if not modify_btns:
            print("No Modify buttons found! Are there any open orders?")
            return

        print(f"Found {len(modify_btns)} modify buttons. Clicking the first one...")
        modify_btns[0].click()
        
        print("Clicked! Waiting for modal...")
        time.sleep(2) # Wait for animation

        # Capture source again
        with open("modify_modal_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Saved 'modify_modal_source.html'.")

        # List inputs in the modal (assuming modal has class 'modal' or similar)
        # We'll just list ALL visible inputs to be safe
        print("\n--- VISIBLE INPUTS ---")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            try:
                if inp.is_displayed():
                    print(f"Input: id='{inp.get_attribute('id')}', name='{inp.get_attribute('name')}', placeholder='{inp.get_attribute('placeholder')}', class='{inp.get_attribute('class')}', value='{inp.get_attribute('value')}'")
            except:
                pass

        print("\n--- VISIBLE BUTTONS ---")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
             try:
                if btn.is_displayed():
                    print(f"Button: text='{btn.text}', class='{btn.get_attribute('class')}'")
             except:
                pass

    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Done. Closing in 5 mins (or close manually).")
        time.sleep(300)

if __name__ == "__main__":
    debug_modify_modal()
