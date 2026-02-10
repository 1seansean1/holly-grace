Set-Location "c:\Users\seanp\Workspace\forge-console\backend"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8060
