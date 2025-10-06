import json
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from models import Restaurant

# 1) skapa TestModel
m = TestModel()
# ge TestModel en rå JSON-sträng
m.custom_output_text = '{"name":"Gröna Hörnet","address":"Vasagatan 1, Göteborg","rating":4.6,"cuisines":["Vegetariskt","Skandinaviskt"]}'

# 2) skapa agent utan output_type
agent = Agent(model=m)

# 3) kör agent
result = agent.run_sync("Beskriv en mysig vegetarisk restaurang i Göteborg.")

# 4) parse JSON-strängen till dict
output_dict = json.loads(result.output)

# 5) validera med Pydantic
restaurant = Restaurant.model_validate(output_dict)
print(restaurant.model_dump())
