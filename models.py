# Installera och fixa miljö. 
# Definiera en enkel Pydantic-modell (schema) för agentens output. 
# Skapa en Agent som använder modellen som output_type (så PydanticAI validerar och parse:ar åt mig). 
# Testa offline med TestModel för att undvika API-nycklar
# Visa hur du kör mot en riktig modell (miljövariabler, försiktighetsåtgärder). 
# Kort om verktyg (tools), retry/validering och vanliga fallgropar. 


from pydantic import BaseModel

class Restaurant(BaseModel):
    name: str
    address: str
    rating: float
    cuisines: list[str]


