# ... existing code ...
                st.success("🤖 Analizando historial y datos maestros con Inteligencia Artificial...")
                
                contexto = f"DATOS ENCONTRADOS:\n{datos_equipo.to_string()}\n"
                instruccion = f"""
                Eres mi copiloto experto en planificación de mantenimiento de equipos pesados.
                El usuario necesita un reporte rápido del equipo: '{equipo_a_buscar}'.
                
                REGLAS ESTRICTAS:
                1. NO incluyas tu proceso de pensamiento. NO uses inglés.
                2. Responde ÚNICAMENTE con el resultado final en español.
                3. Ve directo al grano. Usa esta estructura exacta con emojis:
                
                🚜 1. Datos Básicos del Equipo:
                - (Extrae marca, modelo, PPU, año, VIN, etc. de la Base de Datos).
                
                📅 2. Estado de Planificación y OT:
                - (Indica la actividad más reciente/próxima a realizar, fecha proyectada y estatus de la OT).
                
                📍 3. Ubicación y Faena:
                - (Indica la ubicación actual o faena reportada más reciente).
                
                DATOS DE RESPALDO EXTRAÍDOS DEL EXCEL:
                {contexto}
                """
                
                try:
                    respuesta = None
# ... existing code ...
```eof

### ¿Cómo aplicarlo?
1. Ve a tu archivo `app.py` en GitHub.
2. Busca la variable `instruccion = f""" ... """` (está más o menos en la línea 75).
3. Borra esa instrucción vieja y pega esta nueva que te acabo de dar, que es mucho más estricta.
4. Dale a **Commit changes**.
5. Ve a tu app, actualiza la página y vuelve a buscar el `Quadra-1049`.

Vas a notar dos cosas de inmediato: **te va a responder en un par de segundos** (porque ya no escribirá testamentos) y el formato será **exactamente como tú y yo conversamos**, limpio y ordenado para tu celular. ¡Pruébalo y me confirmas!
