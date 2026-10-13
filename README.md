# Presupuestador · Top Redes Valencia

App de Streamlit que calcula el precio de una instalación a partir de:

- Material por metro lineal (11,29 €/ml) + material fijo por tramo (2,31 €, tensores)
- Horas de pareja en obra y de viaje (46,41 €/h)
- Kilometraje (0,26 €/km), con distancia y tiempo calculados por Google Maps
- Beneficio editable (40 % por defecto), sobre coste o sobre precio de venta
- IVA 21 %

Todos los valores se pueden cambiar en la barra lateral.

## Publicar en Streamlit Community Cloud

1. Crea un repositorio en GitHub (mejor privado) y sube estos archivos:
   `app.py`, `requirements.txt`, `.streamlit/config.toml`, `.gitignore`.
2. Entra en https://share.streamlit.io con tu cuenta de GitHub → **Create app**.
3. Elige el repositorio, rama `main` y archivo `app.py`.
4. En **Advanced settings → Secrets**, pega:
   ```
   GOOGLE_MAPS_API_KEY = "tu-clave"
   ```
5. Pulsa **Deploy**.
6. En **Settings → Sharing**, deja la app solo para las personas que invites,
   porque muestra vuestros costes y márgenes.

## Clave de Google Maps

1. https://console.cloud.google.com → crea un proyecto (p. ej. "Presupuestador").
2. Activa la facturación del proyecto (Google da crédito gratuito mensual;
   el uso de una empresa pequeña normalmente no llega a generar cargos).
3. En **APIs y servicios → Biblioteca**, activa:
   - **Places API (New)**
   - **Routes API**
4. En **Credenciales → Crear credenciales → Clave de API**.
5. Restringe la clave: en *Restricciones de API* marca solo Places API (New) y Routes API.
   No añadas restricción por sitio web (las llamadas salen del servidor de Streamlit).
6. Opcional: en **Cuotas** pon un límite diario de peticiones para evitar sorpresas.

Sin clave, la app funciona igual introduciendo los km y minutos a mano.

## Probar en local

```bash
pip install -r requirements.txt
mkdir -p .streamlit && cp .streamlit/secrets.toml.example .streamlit/secrets.toml  # y pon tu clave
streamlit run app.py
```
