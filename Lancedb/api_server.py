from fastapi import FastAPI, HTTPException
from rag_logic import perform_vector_search, run_gemini_query


app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Hello World"}

@app.get("/search")
async def search_data(query: str, city: str):
    # Anropar RAG-funktionen med input från URL:en
    rag_result = perform_vector_search(query=query, city_filter=city)

    if rag_result is None:
        raise HTTPException(status_code=404, detail="Hittade inga matchande restauranger.")
    
    return rag_result # Detta är rådata just nu