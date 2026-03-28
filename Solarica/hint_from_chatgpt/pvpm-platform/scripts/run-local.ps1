# Start backend, local reader, and web in separate terminals manually.
Write-Host "Backend: uvicorn app.main:app --reload --port 9000"
Write-Host "Reader:  uvicorn app.main:app --reload --port 8100"
Write-Host "Web:     npm run dev"
