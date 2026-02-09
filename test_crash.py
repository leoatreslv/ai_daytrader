from notification import NotificationManager
print("Import successful")
try:
    n = NotificationManager()
    print("Instantiation successful")
except Exception as e:
    print(f"Crash: {e}")
    import traceback
    traceback.print_exc()
