# PASO 1: Enriquecer la consulta
pregunta_expandida = expand_user_query(pregunta)

# PASO 2: Vectorizar el texto enriquecido
embeddings = list(embedding_model.embed([pregunta_expandida]))