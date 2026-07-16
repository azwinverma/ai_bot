from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

def debug_buy_confirm():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    print("Browser started.")
    print("PLEASE LOG IN MANUALLY.")
    print("Navigate to the 'Order Management > Buy/Sell' page.")
    
    input("Press Enter once you are on the Buy/Sell page...")

    print("Please manually fill in the Symbol, Quantity, and Price for a DUMMY order.")
    print("DO NOT CLICK BUY YET.")
    
    input("Press Enter once form is filled...")

    try:
        # Script clicks Buy
        print("Clicking Buy button...")
        # Use the selector we found earlier or a very generic one to be safe
        # Try multiple strategies to find Buy button
        buy_btns = driver.find_elements(By.XPATH, "//button[contains(text(), 'Buy')]")
        if not buy_btns:
             buy_btns = driver.find_elements(By.CSS_SELECTOR, "button.btn-primary")
        
        clicked = False
        for btn in buy_btns:
            if btn.is_displayed() and "buy" in btn.text.lower():
                btn.click()
                clicked = True
                break
        
        if not clicked and buy_btns:
            buy_btns[0].click() # Fallback

        print("Clicked Buy. Waiting for Confirm Popup...")
        time.sleep(3)
        
        print(f"Current URL: {driver.current_url}")
        
        # Robust capture
        src = driver.page_source
        if src:
            with open("confirm_popup_source.html", "w", encoding="utf-8") as f:
                f.write(src)
            print("Saved 'confirm_popup_source.html'.")
        else:
             print("Source is None!")

        # Traverse frames if necessary (though usually these are bootstrap modals)
        
        # Look for Confirm button specifically by partial text and classes
        print("\n--- CONFIRM BUTTON CANDIDATES ---")
        # Common text for confirm buttons
        candidates = driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'confirm')] | //button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'yes')] | //button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok')]")
        
        for btn in candidates:
             try:
                if btn.is_displayed():
                    print(f"candidate: Text='{btn.text}', Class='{btn.get_attribute('class')}', ID='{btn.get_attribute('id')}'")
             except:
                pass

    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Done. Closing in 5 mins.")
        time.sleep(300)

if __name__ == "__main__":
    debug_buy_confirm()
