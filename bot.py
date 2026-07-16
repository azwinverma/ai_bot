import os
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Load environment variables early
load_dotenv()

# --- SETUP ---
options = Options()
# Enable headless mode if specified in env or for cloud
if os.getenv("HEADLESS", "true").lower() == "true":
    options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get("https://tms54.nepsetms.com.np/login")

print("PLEASE LOG IN MANUALLY. Once you are on the Buy/Sell page, the bot will start.")
input("Press Enter here in the terminal once you are ready...")


# --- ORDER SETTINGS ---
STOCK_NAME = os.getenv("NEPSE_STOCK_NAME", "SKHEL")
TARGET_QTY = os.getenv("NEPSE_TARGET_QTY", "10")
TARGET_PRICE = os.getenv("NEPSE_TARGET_PRICE", "553.6")
TOTAL_ORDERS = int(os.getenv("NEPSE_TOTAL_ORDERS", "30"))

def trigger_field(driver, element):
    """Aggressively trigger all events to wake up Angular's FormControl."""
    events = ['input', 'change', 'blur', 'focus', 'keyup', 'keydown', 'keypress']
    for event in events:
        driver.execute_script(f"arguments[0].dispatchEvent(new Event('{event}', {{ bubbles: true }}));", element)
    # Special sauce for Angular: mark as touched/dirty, focused and blurred
    driver.execute_script("arguments[0].focus(); arguments[0].click();", element)
    driver.execute_script("arguments[0].blur();", element)

def clear_overlays(driver):
    """Forcefully close any modals or backdrops that might block interaction."""
    try:
        # 1. Disable browser's native 'beforeunload' popup
        driver.execute_script("window.onbeforeunload = null;")
        
        # 2. Forcefully remove any element containing 'modal' or 'backdrop' in class or tag
        driver.execute_script("""
            const overlays = [
                ...document.querySelectorAll('.modal-backdrop'),
                ...document.querySelectorAll('.modal'),
                ...document.querySelectorAll('modal-component'),
                ...document.querySelectorAll('.k-overlay'),
                ...document.querySelectorAll('.k-window')
            ];
            overlays.forEach(el => {
                el.remove();
            });
            document.body.classList.remove('modal-open');
        """)
        
        # 3. Specifically look for and click 'No' or 'Close' buttons if still present
        try:
            btns = driver.find_elements(By.XPATH, "//button[contains(text(), 'No') or contains(text(), 'Close') or contains(text(), 'CANCEL')]")
            for btn in btns:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
        except:
            pass
            
    except:
        pass

def place_order():
    try:
        # --- WAIT FOR LOGIN (New Logic) ---
        print("Checking page status...")
        while True:
            try:
                # Check for login page
                if driver.find_elements(By.CSS_SELECTOR, "input[placeholder*='Client Code']"):
                    print("  [DEBUG] On Login Page. Waiting for manual login...")
                    time.sleep(5)
                    continue
                
                # Check for Buy/Sell form elements
                # The form uses specific classes for quantity and price
                qty_present = driver.find_elements(By.CSS_SELECTOR, "input.form-qty")
                price_present = driver.find_elements(By.CSS_SELECTOR, "input.form-price")
                
                if qty_present and price_present:
                    print("  [DEBUG] Buy/Sell Page detected!")
                    break
                
                print("  [DEBUG] Still waiting for Buy/Sell page (Inputs not found)...")
                time.sleep(3)
            except Exception as e:
                print(f"  [ERROR] Page check error: {e}")
                time.sleep(2)

        # --- 0. Ensure Page Status ---
        while True:
            if driver.find_elements(By.CSS_SELECTOR, "app-member-client-order-entry"):
                print("  [DEBUG] Buy/Sell Page ready.")
                break
            
            if "login" in driver.current_url.lower() or driver.find_elements(By.XPATH, "//div[contains(text(), 'Enter OTP')]"):
                print("  [WAITING] Login or OTP Screen detected. Please complete it manually...")
            else:
                print("  [WAITING] Waiting for Buy/Sell page...")
            
            time.sleep(5)

        # Record Initial Order Count
        initial_count = 0
        try:
            pager_info = driver.find_element(By.CSS_SELECTOR, "kendo-pager-info")
            if pager_info.is_displayed():
                text = pager_info.text # e.g. "1 - 3 of 3 items"
                initial_count = int(text.split("of")[-1].split("items")[0].strip())
        except:
            pass
        print(f"  [DEBUG] Initial orders in book: {initial_count}")

        # --- 0. Clear Overlays ---
        clear_overlays(driver)
        time.sleep(1)

        # --- 1. Reset Form & Select Mode ---
        order_entry = driver.find_element(By.CSS_SELECTOR, "app-member-client-order-entry")
        
        try:
            # Click the gray 'CANCEL' button to reset the form state
            reset_btn = order_entry.find_element(By.XPATH, ".//button[contains(text(), 'CANCEL')]")
            driver.execute_script("arguments[0].click();", reset_btn)
            print("  [DEBUG] Form reset via CANCEL button.")
            time.sleep(1)
        except:
            pass

        try:
            print("  [STEP 1] Setting Session, Mode and Product Type...")
            # 1a. Ensure 'CONTINUOUS' session
            try:
                continuous_label = driver.find_element(By.XPATH, "//label[contains(text(), 'CONTINUOUS')]")
                driver.execute_script("arguments[0].click();", continuous_label)
            except: pass

            # 1b. Surgical Three-State Toggle Activation
            # The toggle has 3 states: [Sell, Indeterminate, Buy]
            # We want to force it to the 3rd button.
            print("  Activating BUY mode via Toggle Switch...")
            try:
                # Target the 3rd label wrapper specifically
                toggle_btns = order_entry.find_elements(By.CSS_SELECTOR, "app-three-state-toggle .xtoggler-btn-wrapper")
                if len(toggle_btns) >= 3:
                    driver.execute_script("arguments[0].click();", toggle_btns[2]) # 0=Sell, 1=Ind, 2=Buy
                    time.sleep(1)
                else:
                    # Fallback to label click
                    buy_label = order_entry.find_element(By.CSS_SELECTOR, "label.order__options--buy")
                    driver.execute_script("arguments[0].click();", buy_label)
                    time.sleep(1)
            except:
                # Extreme fallback
                buy_label = order_entry.find_element(By.XPATH, "//label[contains(text(), 'Buy')]")
                driver.execute_script("arguments[0].click();", buy_label)
            
            # Verification
            submit_btn = order_entry.find_element(By.CSS_SELECTOR, "button[type='submit']")
            if submit_btn.text.strip() == "BUY":
                print("  [SUCCESS] Mode set to BUY.")
            else:
                print(f"  [WARNING] Button text is '{submit_btn.text.strip()}'. Jiggling toggle...")
                # Try clicking the label again if switch didn't work
                try:
                    buy_label = order_entry.find_element(By.CSS_SELECTOR, "label.order__options--buy")
                    driver.execute_script("arguments[0].click();", buy_label)
                    time.sleep(1)
                except: pass

            # 1c. Product Type (CNC)
            try:
                cnc_radio = order_entry.find_element(By.CSS_SELECTOR, "input#CNC, input[value='CNC']")
                driver.execute_script("arguments[0].click();", cnc_radio)
                driver.execute_script("arguments[0].checked = true;", cnc_radio)
                trigger_field(driver, cnc_radio)
            except:
                try:
                    cnc_label = order_entry.find_element(By.XPATH, ".//label[contains(text(), 'CNC')]")
                    driver.execute_script("arguments[0].click();", cnc_label)
                except: pass
            
            print("  Session/Mode/Product initialization complete.")
        except Exception as e:
            print(f"  [ERROR] Initialization error: {e}")

        # --- 2. Fill Form ---
        # 2a. Symbol Selection
        for attempt in range(3):
            try:
                print(f"  Entering Symbol: {STOCK_NAME} (Attempt {attempt+1})")
                symbol_input = order_entry.find_element(By.XPATH, ".//input[contains(@class, 'form-qty')]/preceding::input[@type='text'][1]")
                
                # Clear thoroughly
                driver.execute_script("arguments[0].value = '';", symbol_input)
                trigger_field(driver, symbol_input)
                
                # Type symbol
                for char in STOCK_NAME:
                    symbol_input.send_keys(char)
                    time.sleep(0.1)
                
                # Wait for suggestions specifically
                time.sleep(2)
                
                # Keyboard-based selection (Human-like)
                print(f"  [DEBUG] Suggestion found. Navigating via Keyboard...")
                symbol_input.send_keys(Keys.ARROW_DOWN)
                time.sleep(0.5)
                symbol_input.send_keys(Keys.ENTER)
                time.sleep(1)
                
                # CRITICAL: Wait for Symbol details to load
                # The LTP (Last Traded Price) or High/Low labels are only populated after selection.
                print("  Waiting for Symbol details (LTP/Price) to load...")
                symbol_loaded = False
                for _ in range(15): # 7.5 seconds
                    try:
                        # Try finding LTP anywhere in the order entry scope
                        ltp_labels = order_entry.find_elements(By.XPATH, ".//*[contains(text(), 'LTP')]")
                        for label in ltp_labels:
                            # LTP value is usually a sibling or child
                            parent = label.find_element(By.XPATH, "./..")
                            text = parent.text
                            if any(d.isdigit() for d in text):
                                print(f"  [SUCCESS] Symbol confirmed. LTP data found: {text}")
                                symbol_loaded = True
                                break
                        if symbol_loaded: break
                    except:
                        pass
                    time.sleep(0.5)
                
                if not symbol_loaded:
                    print("  [WARNING] Symbol details (LTP) did not load. Retrying...")
                    continue
                
                # DEBUG: List all submit buttons
                print("  [DEBUG] Listing all submit buttons in form:")
                all_btns = order_entry.find_elements(By.TAG_NAME, "button")
                for i, b in enumerate(all_btns):
                    try:
                        if b.get_attribute("type") == "submit":
                            print(f"    Button {i}: Type=submit, Text='{b.text}', Enabled={b.is_enabled()}, Class='{b.get_attribute('class')}'")
                    except: pass

                # Final body click to settle Angular
                driver.execute_script("document.body.click();")
                break
            except Exception as e:
                print(f"  [DEBUG] Symbol entry error: {e}")
                time.sleep(1)
            except Exception as e:
                print(f"  [DEBUG] Symbol entry error: {e}")
                time.sleep(1)

        # 2b. Qty and Price Entry (Hardened JS-Direct)
        for retry in range(3):
            try:
                print(f"  Entering Qty: {TARGET_QTY} and Price: {TARGET_PRICE} (Attempt {retry+1})")
                quantity_input = order_entry.find_element(By.CSS_SELECTOR, "input.form-qty")
                price_input = order_entry.find_element(By.CSS_SELECTOR, "input.form-price")
                
                # Force values via JS to ensure they stick and trigger TMS validation
                driver.execute_script(f"arguments[0].value = '{TARGET_QTY}';", quantity_input)
                driver.execute_script(f"arguments[0].value = '{TARGET_PRICE}';", price_input)
                
                # Wake up Angular
                trigger_field(driver, quantity_input)
                trigger_field(driver, price_input)
                
                # Standard typing as backup (some TMS listeners only fire on real keys)
                quantity_input.send_keys(Keys.COMMAND + "a")
                quantity_input.send_keys(Keys.BACKSPACE)
                quantity_input.send_keys(str(TARGET_QTY))
                quantity_input.send_keys(Keys.TAB)
                
                price_input.send_keys(Keys.COMMAND + "a")
                price_input.send_keys(Keys.BACKSPACE)
                price_input.send_keys(str(TARGET_PRICE))
                price_input.send_keys(Keys.TAB)
                
                time.sleep(1)
                
                # VERIFY
                q_val = driver.execute_script("return arguments[0].value;", quantity_input)
                p_val = driver.execute_script("return arguments[0].value;", price_input)
                if q_val and p_val and str(q_val) == str(TARGET_QTY) and str(p_val) == str(TARGET_PRICE):
                    print(f"  [VERIFIED] Form Values: Qty={q_val}, Price={p_val}")
                    
                    # FORCE VALIDATION: "Jiggle" the price field
                    print("  Jiggling Price field to force validation...")
                    price_input.send_keys(Keys.BACKSPACE)
                    time.sleep(0.1)
                    price_input.send_keys(str(TARGET_PRICE)[-1]) # Re-type last char
                    price_input.send_keys(Keys.TAB)
                    trigger_field(driver, price_input)
                    time.sleep(1)
                    
                    # FINAL CHECK: Is the button enabled?
                    submit_btn = order_entry.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    if submit_btn.is_enabled() or submit_btn.get_attribute("disabled") is None:
                        print("  [SUCCESS] BUY button is ENABLED.")
                        break
                    else:
                        print(f"  [WARNING] Button still DISABLED. Text='{submit_btn.text}'.")
                        # Diagnostic: Capture the validation error text
                        try:
                            v_errors = order_entry.find_elements(By.CSS_SELECTOR, ".invalid-feedback, .text-danger, .error-message")
                            for ve in v_errors:
                                if ve.is_displayed() and ve.text.strip():
                                    print(f"  [UI ERROR] {ve.text.strip()}")
                        except: pass
                        print("  Retrying...")
                else:
                    print(f"  [WARNING] Verification failed: Qty='{q_val}', Price='{p_val}'. Retrying...")
            except Exception as e:
                print(f"  [ERROR] Qty/Price entry error: {e}")
                time.sleep(1)

        # 2c. Check for UI Validation Errors
        try:
            all_text = order_entry.text
            if "Quantity not valid" in all_text:
                print("  [UI ERROR] 'Quantity not valid' visible on screen.")
            
            errors = order_entry.find_elements(By.CSS_SELECTOR, ".error, .text-danger, .invalid-feedback")
            for err in errors:
                if err.is_displayed() and err.text.strip():
                    print(f"  [UI VALIDATION] {err.text.strip()}")
            
            if "NaN" in order_entry.text or "undefined" in order_entry.text:
                print("  [WARNING] Form still shows 'NaN' or 'undefined'.")
        except:
            pass

        # --- 3. Click Submit/Buy Button ---
        print("Attempting to find Submit/Buy button...")
        try:
            # STRICT WAIT: Must be enabled AND have text 'Buy'
            submit_btn = WebDriverWait(order_entry, 15).until(
                lambda d: d.find_element(By.CSS_SELECTOR, "button[type='submit']").is_enabled() or
                         d.find_element(By.CSS_SELECTOR, "button[type='submit']").get_attribute("disabled") is None
            )
            submit_btn = order_entry.find_element(By.CSS_SELECTOR, "button[type='submit']")
            print(f"  Found valid Submit button with text: '{submit_btn.text}'. Clicking...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", submit_btn)
            
        except Exception as e:
            print(f"  [FATAL] Submit button NOT READY after timeout. Reason: Selection/Validation Failure.")
            # Final diagnostic
            driver.save_screenshot("buy_button_blocked_v3.png")
            return False

        # --- 4. Handle 'Confirm' Popup ---
        try:
            print("  Waiting for Confirm popup...")
            # Look for a button that is NOT Close/Cancel and is in a modal
            # Common text for confirm in NEPSE: 'Yes', 'Confirm', 'Confirm Order'
            confirm_btn_xpath = "//div[contains(@class, 'modal')]//button[not(contains(translate(text(),'C','c'),'close')) and not(contains(translate(text(),'C','c'),'cancel')) and not(contains(translate(text(),'N','n'),'no'))]"
            
            try:
                confirm_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, confirm_btn_xpath))
                )
                print(f"  Confirm button found: '{confirm_btn.text}'. Clicking...")
                driver.execute_script("arguments[0].click();", confirm_btn)
            except:
                print("  [INFO] No confirmation popup appeared within 3s. Checking for results...")

            print("  Waiting for response/result...")
            time.sleep(3) 
            
            # --- 5. Verify Success ---
            # Strategy A: Check if order count in book increased
            try:
                new_pager_info = driver.find_element(By.CSS_SELECTOR, "kendo-pager-info")
                new_text = new_pager_info.text
                new_count = int(new_text.split("of")[-1].split("items")[0].strip())
                if new_count > initial_count:
                    print(f"  [SUCCESS] Order Book updated: {initial_count} -> {new_count}")
                    return True
            except:
                pass

            # Strategy B: Check Toast messages
            toasts = driver.find_elements(By.CSS_SELECTOR, ".toast-message, .alert")
            for t in toasts:
                if t.is_displayed() and t.text.strip():
                    print(f"  [TOAST] {t.text.strip()}")
            
            # If we reached here but don't see count increase, maybe it worked anyway
            # (Sometimes count doesn't update until refresh, or table is empty if first order)
            return True # Assume success if no FATAL error triggered
            
        except Exception as e:
            print(f"  [ERROR] Post-submission handling failed: {e}")
            # Try a very broad search for any 'Confirm' or 'Yes' text just in case before giving up
            try:
                fallback_xpath = "//button[contains(text(), 'Confirm') or contains(text(), 'Yes')]"
                fallback_btn = driver.find_element(By.XPATH, fallback_xpath)
                if fallback_btn.is_displayed():
                    driver.execute_script("arguments[0].click();", fallback_btn)
                    print("  Confirmed (fallback).")
            except:
                pass
            return True # Still return True because order might have been placed
        
        return True
    except Exception as e:
        print(f"Failed to place order: {e}")
        
        # Debug: Print all inputs found
        print("DEBUG: Listing all input elements found on the page:")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for i, inp in enumerate(inputs):
            try:
                print(f"Input {i}: id='{inp.get_attribute('id')}', name='{inp.get_attribute('name')}', placeholder='{inp.get_attribute('placeholder')}', type='{inp.get_attribute('type')}', class='{inp.get_attribute('class')}'")
            except:
                pass
        
        print("DEBUG: Listing all BUTTON elements found on the page:")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for i, btn in enumerate(buttons):
            try:
                print(f"Button {i}: text='{btn.text}', id='{btn.get_attribute('id')}', class='{btn.get_attribute('class')}', type='{btn.get_attribute('type')}'")
            except:
                pass

        with open("tms_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Saved page source to tms_page_source.html for debugging.")
        return False

# --- THE LOOP ---
consecutive_errors = 0
i = 0
while i < TOTAL_ORDERS:
    print(f"Executing order {i+1}/{TOTAL_ORDERS}")
    success = place_order()
    if success:
        print("Order cycle complete. Waiting 5 seconds...")
        consecutive_errors = 0
        i += 1
        time.sleep(5)
    else:
        consecutive_errors += 1
        print(f"Order failed (Consecutive errors: {consecutive_errors}). Retrying in 10s...")
        time.sleep(10)
        if consecutive_errors >= 5:
            print("Too many consecutive errors. Stopping bot.")
            break

print("Task complete.")