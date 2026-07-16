from bs4 import BeautifulSoup

def parse_popup():
    try:
        with open("confirm_popup_source.html", "r", encoding="utf-8") as f:
            html = f.read()

        soup = BeautifulSoup(html, 'html.parser')
        
        print("--- ALL BUTTONS ---")
        buttons = soup.find_all('button')
        for btn in buttons:
            print(f"Button: Text='{btn.get_text(strip=True)}', Class='{btn.get('class')}', ID='{btn.get('id')}', Type='{btn.get('type')}'")
            print(f"   Inner HTML: {btn.encode_contents()}")
            
        
        print("\n--- SIBLINGS OF 'CANCEL' BUTTON ---")
        cancel_btn = soup.find('button', string=lambda s: s and 'CANCEL' in s.upper())
        if cancel_btn:
             parent = cancel_btn.find_parent()
             print(f"Parent Class: {parent.get('class')}")
             for child in parent.find_all(recursive=False):
                 print(f"Child Tag: {child.name}, Text: '{child.get_text(strip=True)}', Class: {child.get('class')}, Inner: {child.encode_contents()}")
        else:
             print("CANCEL button not found via string search.")
             
        print("\n--- PARENT HTML OF 'No' BUTTON ---")
        no_btn = soup.find('button', string=lambda s: s and 'No' in s)
        if no_btn:
             parent = no_btn.find_parent()
             print(parent.prettify())
        
        print("\n--- PARENT HTML OF '-' BUTTON ---")
        dash_btn = soup.find('button', string=lambda s: s and s.strip() == '-')
        if dash_btn:
             parent = dash_btn.find_parent()
             print(parent.prettify())
             
        print("\n--- ALL INPUTS ---")
        all_inputs = soup.find_all('input')
        for inp in all_inputs:
             print(f"Input: Type='{inp.get('type')}', Name='{inp.get('name')}', ID='{inp.get('id')}', Class='{inp.get('class')}'")

        print("\n--- ELEMENTS WITH 'CHECK' IN CLASS ---")
        check_elems = soup.find_all(lambda tag: tag.get('class') and any('check' in c.lower() for c in tag.get('class')))
        for elem in check_elems:
             print(f"Element: Tag='{elem.name}', Class='{elem.get('class')}', Text='{elem.get_text(strip=True)}'")
             # print(f"   Inner: {elem.encode_contents()[:100]}")

        print("\n--- CHECKBOXES NEAR BUTTON GROUP ---")
        btn_grp = soup.find('div', class_=lambda c: c and 'order__form--btngrp' in c)
        if btn_grp:
             print("Found button group.")
             # Go up to the form or modal container
             container = btn_grp.find_parent('form') or btn_grp.find_parent('div', class_='modal-content') or btn_grp.find_parent('div', class_='box')
             
             if container:
                 print(f"Container: {container.name} class='{container.get('class')}'")
                 # Find np__check inside this container
                 checks = container.find_all(lambda tag: tag.name in ['label', 'div', 'span'] and tag.get('class') and any('np__check' in c for c in tag.get('class')))
                 for chk in checks:
                     print(f"  Checkbox Candidate: Tag='{chk.name}', Class='{chk.get('class')}', Text='{chk.get_text(strip=True)}'")
                     print(f"    Inner: {chk.encode_contents()}")
        print("\n--- BUY LABEL CONTEXT ---")
        buy_label = soup.find('label', class_='order__options--buy')
        if buy_label:
             print(buy_label.prettify())
             parent = buy_label.find_parent()
             print("\nParent of Buy Label:")
             print(parent.prettify())
        else:
             print("Label order__options--buy not found.")


    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parse_popup()
