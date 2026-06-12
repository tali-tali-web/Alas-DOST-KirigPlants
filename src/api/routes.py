from fastapi import FastAPI

router = FastAPI()

@router.post("/data")
def first_example():
    return {"message" : "Hello World! "}

@router.get("/dashboard")
def request_dashboard():
    return{"tree" : "yes"}