import streamlit as st
import requests
import json

BASE_URL = "http://localhost:8000"

st.header("Restaurants with RAG")

query = st.text_input("Beskriv vad du söker: ")
city = st.text_input("Stad: ")

if st.button("Sök"):
    
    if not query or not city:
        st.error("⚠️ Vänligen fyll i både sökfråga och stad.")
    else:
        st.info(f"🔎 Söker efter '{query}' i {city}...")
        
        response = requests.get(f"{BASE_URL}/search?query={query}&city={city}")
        
        if response.status_code == 200:
            json_data = response.json()
            st.success("Hittade resultat!")
            
            # st.write(json_data)
            st.dataframe(json_data['results'])
        else:
            st.warning("Hittade inga resultat för den sökningen")

