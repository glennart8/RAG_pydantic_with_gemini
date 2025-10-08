from fastapi import FastAPI, HTTPException
from rag_logic import perform_vector_search, run_gemini_query, list_all_unique_names, get_details_by_name


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

@app.get("/restaurants", summary="Hämtar en lista med alla unika restaurangnamn")
async def get_all_restaurant_names():
    try:
        unique_names = list_all_unique_names()
        
        if not unique_names:
            return {"names": []}
        
        return {"names": unique_names}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internt serverfel vid hämtning av namn.")
        
@app.get("/details", summary="Returnerar recensioner om vald restaurang")
async def get_restaurant_details(restaurant_name: str):
    try:
        restaurant_details = get_details_by_name(restaurant_name)
        
        if not restaurant_details:
            raise HTTPException(status_code=404, detail="Restaurang saknas i databasen.")
        
        return {"details": restaurant_details}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Kunde inte hämta detaljer.")
        
        
        

