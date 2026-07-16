from bs4 import BeautifulSoup

def parse_order_book():
    with open("order_book_source.html", "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Find the table
    # Usually has class 'k-grid' or similar in Kendo UI which TMS uses, or just Find all <tr class='ng-star-inserted'>
    rows = soup.find_all('tr', class_='ng-star-inserted')
    
    print(f"Found {len(rows)} potential rows.")
    
    for i, row in enumerate(rows):
        # Extract text from cells
        cells = row.find_all('td')
        cell_texts = [c.get_text(strip=True) for c in cells]
        
        # Check for modify icon
        modify_icon = row.select_one('.table--edit, .nf-table-edit')
        has_modify = "YES" if modify_icon else "NO"
        
        if cell_texts:
            print(f"Row {i}: Modify={has_modify} | Text={cell_texts}")
            
            if has_modify == "YES":
                print(f"  -> Modify Button HTML: {modify_icon}")
                # Print parent of icon to see if it's a button or link
                print(f"  -> Parent HTML: {modify_icon.parent}")

if __name__ == "__main__":
    parse_order_book()
