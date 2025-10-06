import lancedb
import pandas as pd
from sentence_transformers import SentenceTransformer
from restaurant_data import RAW_RESTAURANT_DATA 

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' 
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME) 
DB_PATH = "my_restaurant_db"
db = lancedb.connect(DB_PATH)

data = RAW_RESTAURANT_DATA

df = pd.DataFrame(data)

# 3. Vektorisera och spara i LanceDB
print(f"Skapar vektorer och sparar i LanceDB...")
df["vector"] = df["text"].apply(lambda x: embedding_model.encode(x).tolist())

table = db.create_table(
    "restaurants_db", 
    data=df, 
    mode="overwrite" 
)

print(f"LanceDB-tabellen 'restaurants_db' uppdaterad med 'city'-kolumnen.")
