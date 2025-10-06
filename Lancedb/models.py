from pydantic import BaseModel, Field
from typing import List

class Restaurant(BaseModel):
    name: str = Field(description="Restaurangens namn.")
    address: str = Field(description="Den fysiska gatuadressen.")
    rating: float = Field(..., ge=1.0, le=5.0, description="Restaurangbetyg på en skala 1.0 till 5.0")
    cuisines: List[str] = Field(description="En lista med specifika typer av mat, t.ex. 'Kinesisk', 'Szichuan'.")
    
    
class RestaurantList(BaseModel):
    """
    Modell för att hålla en lista av restaurangobjekt.
    """
    results: List[Restaurant] = Field(
        description="En lista som innehåller de mest relevanta restaurangobjekten extraherade från kontexten."
    )