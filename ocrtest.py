import easyocr

allowed_chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
try:
    reader = easyocr.Reader(['en'], allowlist=allowed_chars, detail=1)
    print("EasyOCR reader created successfully!")
except TypeError as e:
    print(f"Error: {e}")
except Exception as e:
    print(f"Other error: {e}")