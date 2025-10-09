from fastapi import FastAPI, HTTPException
from rag_logic import perform_vector_search, list_all_unique_names, get_details_by_name, list_all_unique_cities, list_restaurants_by_city, add_restaurant, update_restaurant
from models import RestaurantReview

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Hello there hungry people in the world!"}

@app.get("/search")
async def search_restaurants(query: str, city: str):
    try:
        rag_result = perform_vector_search(query=query, city_filter=city)

        if not rag_result:
            raise HTTPException(status_code=404, detail="Hittade inga matchande restauranger.")

        return rag_result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internt serverfel vid sökning.")

@app.get("/restaurants", summary="Hämtar en lista med alla unika restaurangnamn")
async def get_all_restaurant_names():
    try:
        unique_names = list_all_unique_names()        
        return {"names": unique_names}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internt serverfel vid hämtning av namn.")
        
@app.get("/details", summary="Returnerar ett omdömme om vald restaurang")
async def get_restaurant_details(restaurant_name: str):
    try:
        restaurant_details = get_details_by_name(restaurant_name)
        
        if not restaurant_details:
            raise HTTPException(status_code=404, detail="Restaurang saknas i databasen.")
        
        return {"details": restaurant_details}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Kunde inte hämta detaljer.")
    
@app.get("/cities", summary="Hämtar en lista med alla städer")
async def get_all_cities():
    try:
        unique_cities = list_all_unique_cities()        
        return {"cities": unique_cities}
        
    except Exception as e:  
        raise HTTPException(status_code=500, detail="Kunde inte hämta städer.")
        
        
@app.get("/restaurants_by_city")
async def get_restaurants_by_city(city_name: str):
    try:
        restaurant_names_by_city = list_restaurants_by_city(city_name)
        return {"names": restaurant_names_by_city}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Kunde inte hämta restaurangnamn.")

@app.post("/add_restaurant", summary="Lägger till en ny restaurangrecension")
async def post_new_restaurant(review: RestaurantReview):
    # FastAPI mappar automatiskt den inkommande JSON-datan till 'review'-objektet
    success = add_restaurant(
        restaurant_name=review.name,  
        restaurant_city=review.city,  
        review=review.text            
    )
    
    if success:
        return {"message": f"Recension för {review.name} i {review.city} sparad och vektoriserad."}
    else:
        raise HTTPException(status_code=500, detail="Kunde inte spara recensionen. Kontrollera serverloggar.")

@app.put("/edit", summary="Uppdaterar en restaurangrecension")
async def update_restaurant_review(restaurant_name: str, review: RestaurantReview):    
    try:
        updated = update_restaurant(
            restaurant_name=restaurant_name,
            restaurant_city=review.city,
            review=review.text
        )
            
        if updated:
            return {"message": f"Recensionen för {restaurant_name} har uppdaterats."}
        else:
            raise HTTPException(status_code=500, detail="Kunde inte uppdatera recensionen. Kontrollera serverloggar.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internt serverfel vid uppdatering: {e}")
    
    