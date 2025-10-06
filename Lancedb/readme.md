# RAG Agent: 
---

Strukturerad Dataextraktion (LanceDB + Gemini)

Detta projekt demonstrerar en robust **Retrieval-Augmented Generation** (RAG)-pipeline. 
Syftet är att hämta, indexera och strukturerat extrahera information från en lokal databas med ostrukturerade textbeskrivningar om restauranger i Göteborg och Uddevalla.

Projektet omvandlar ostrukturerad text (som beskrivningar och recensioner) till maskinläsbar JSON genom att använda en stor språkmodell (Gemeni) tvingad till ett specifikt schema.

Med denna struktur kan man själv fylla på med restaurangbesök, recensera för att sedan emd hjälp av LLM få ut datan för adress, rate osv.