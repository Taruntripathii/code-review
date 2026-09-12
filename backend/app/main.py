import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home() -> dict[str, str]:
    return {"message": "This is the home page of your code review bot"}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

