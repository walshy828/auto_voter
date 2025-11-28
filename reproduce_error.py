from bs4 import BeautifulSoup

html = "<html><body>No title here</body></html>"
soup = BeautifulSoup(html, 'html.parser')

try:
    print(soup.title.string)
except AttributeError as e:
    print(f"Caught expected error: {e}")

try:
    if soup.title:
        print(soup.title.string)
    else:
        print("Title is None, handled safely")
except Exception as e:
    print(f"Unexpected error: {e}")
