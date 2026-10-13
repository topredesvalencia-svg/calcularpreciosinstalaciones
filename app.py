"""
Presupuestador de instalaciones · Top Redes Valencia
Calcula el precio de una instalación a partir de costes directos:
material por metro lineal, horas de pareja, desplazamiento y beneficio.
"""

from datetime import date
from urllib.parse import quote_plus

import requests
import streamlit as st

st.set_page_config(
    page_title="Presupuestador · Top Redes Valencia",
    page_icon="🐾",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Valores por defecto (editables desde la barra lateral)
# ---------------------------------------------------------------------------
DEF = {
    "eur_ml": 11.29,       # material por metro lineal (9,29 + 2 € de varios)
    "eur_tramo": 2.31,     # 2 tensores por tramo
    "eur_h_pareja": 46.41, # coste hora de la pareja (2 operarios)
    "eur_km": 0.26,        # coste por km de furgoneta
    "beneficio": 40.0,     # % de beneficio
    "iva": 10.0,
    "sueldo_admin": 1700.0,  # salario líquido mensual del administrativo
    "pct_admin": 80.0,       # % de ese salario que se imputa a instalaciones
    "inst_mes": 20,          # instalaciones al mes para repartir la gestión
    "origen": "Bétera, Valencia",
}

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

st.markdown(
    """
    <style>
      .tr-total {background:#E01B7D; color:#fff; border-radius:14px;
                 padding:1.1rem 1.4rem; margin:.6rem 0 1rem 0;}
      .tr-total .lbl {font-size:.95rem; opacity:.9;}
      .tr-total .big {font-size:2.3rem; font-weight:700; line-height:1.15;}
      .tr-total .sub {font-size:1rem; margin-top:.2rem;}
      div[data-testid="stMetricValue"] {font-size:1.35rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def eur(x: float) -> str:
    """Formato 1.234,56 €"""
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def num(x: float, dec: int = 1) -> str:
    s = f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def api_key():
    try:
        return st.secrets["GOOGLE_MAPS_API_KEY"]
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_lugares(texto: str, key: str):
    """Busca direcciones o lugares con Places API (New)."""
    r = requests.post(
        PLACES_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress",
        },
        json={
            "textQuery": texto,
            "languageCode": "es",
            "regionCode": "ES",
            # Prioriza resultados cerca de Valencia sin excluir Castellón o Alicante
            "locationBias": {
                "circle": {
                    "center": {"latitude": 39.47, "longitude": -0.38},
                    "radius": 50000.0,
                }
            },
        },
        timeout=10,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Google Places respondió {r.status_code}: {r.text[:300]}")
    lugares = []
    for p in r.json().get("places", []):
        lugares.append(
            {
                "id": p["id"],
                "nombre": p.get("displayName", {}).get("text", ""),
                "direccion": p.get("formattedAddress", ""),
            }
        )
    return lugares


@st.cache_data(ttl=3600, show_spinner=False)
def calcular_ruta(origen: str, destino_place_id: str, key: str):
    """Distancia (km) y tiempo (min) de un trayecto en coche con Routes API."""
    r = requests.post(
        ROUTES_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
        },
        json={
            "origin": {"address": origen},
            "destination": {"placeId": destino_place_id},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_UNAWARE",
            "languageCode": "es-ES",
            "units": "METRIC",
        },
        timeout=10,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Google Routes respondió {r.status_code}: {r.text[:300]}")
    rutas = r.json().get("routes", [])
    if not rutas:
        return None
    km = rutas[0].get("distanceMeters", 0) / 1000
    minutos = int(str(rutas[0].get("duration", "0s")).rstrip("s")) / 60
    return km, minutos


# ---------------------------------------------------------------------------
# Barra lateral: parámetros de coste
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Parámetros")

    st.subheader("Beneficio")
    beneficio = st.number_input(
        "Beneficio (%)", min_value=0.0, max_value=300.0,
        value=DEF["beneficio"], step=1.0,
    )
    modo_beneficio = st.radio(
        "Cómo se aplica",
        ["Sobre el coste", "Sobre el precio de venta"],
        help=(
            "Sobre el coste: precio = coste × (1 + %). Con 40 %, 100 € de coste → 140 €.\n\n"
            "Sobre el precio de venta: el % es la parte del precio que queda de beneficio. "
            "Con 40 %, 100 € de coste → 166,67 €."
        ),
    )

    st.subheader("Costes")
    eur_ml = st.number_input("Material por metro lineal (€/ml)", 0.0, value=DEF["eur_ml"], step=0.10, format="%.2f")
    eur_tramo = st.number_input("Material fijo por tramo (€/tramo)", 0.0, value=DEF["eur_tramo"], step=0.10, format="%.2f",
                                help="Tensores: 2 por tramo recto.")
    eur_h = st.number_input("Hora de pareja (€/h)", 0.0, value=DEF["eur_h_pareja"], step=0.50, format="%.2f",
                            help="2 operarios, base 1.833,26 € + SS empresa, con un 25 % de tiempo no imputable.")
    eur_km = st.number_input("Coste por km (€/km)", 0.0, value=DEF["eur_km"], step=0.01, format="%.2f")
    iva = st.number_input(
        "IVA (%)", 0.0, 100.0, value=DEF["iva"], step=1.0,
        help=("10 %: obras en vivienda de un particular, si el material no supera el 40 % "
              "de la base imponible. 21 %: empresas, locales o comunidades."),
    )

    st.subheader("Gestión administrativa")
    sueldo_admin = st.number_input("Salario líquido administrativo (€/mes)", 0.0,
                                   value=DEF["sueldo_admin"], step=50.0, format="%.2f")
    pct_admin = st.number_input("Parte imputada a instalaciones (%)", 0.0, 100.0,
                                value=DEF["pct_admin"], step=5.0)
    inst_mes = st.number_input("Instalaciones al mes", min_value=1, value=DEF["inst_mes"], step=1,
                               help="El coste de gestión del mes se reparte entre estas instalaciones.")
    eur_gestion = sueldo_admin * pct_admin / 100 / inst_mes
    st.caption(f"Gestión por instalación: **{eur(eur_gestion)}** "
               f"({eur(sueldo_admin * pct_admin / 100)} al mes / {inst_mes})")

    st.subheader("Salida")
    origen = st.text_input("Punto de salida", value=DEF["origen"])


# ---------------------------------------------------------------------------
# Cabecera
# ---------------------------------------------------------------------------
st.title("Presupuestador de instalaciones")
st.caption("Top Redes Valencia · precio a partir de material, horas de pareja y desplazamiento")

cliente = st.text_input("Cliente o referencia", placeholder="Ej.: Eduardo, ático Benaguasil")

# ---------------------------------------------------------------------------
# 1. Instalación
# ---------------------------------------------------------------------------
st.subheader("Instalación")
c1, c2, c3 = st.columns(3)
metros = c1.number_input("Metros lineales", min_value=0.0, value=6.0, step=0.5, format="%.1f")
tramos = c2.number_input("Tramos rectos", min_value=0, value=1, step=1,
                         help="Cada cambio de dirección es un tramo nuevo (lleva sus tensores).")
horas_inst = c3.number_input("Horas de pareja en obra", min_value=0.0, value=4.0, step=0.5, format="%.1f")

# ---------------------------------------------------------------------------
# 2. Desplazamiento
# ---------------------------------------------------------------------------
st.subheader("Desplazamiento")
key = api_key()
modos = ["Buscar en Google Maps", "Introducir a mano"] if key else ["Introducir a mano"]
if not key:
    st.info(
        "La búsqueda en Google Maps está desactivada porque falta la clave "
        "GOOGLE_MAPS_API_KEY en los secretos de la app. Mientras tanto, introduce los km y minutos a mano."
    )
modo = st.radio("Distancia", modos, horizontal=True, label_visibility="collapsed")

km_ida, min_ida, destino_txt = 0.0, 0.0, ""

if modo == "Buscar en Google Maps":
    with st.form("buscar", border=False):
        b1, b2 = st.columns([4, 1])
        texto = b1.text_input("Dirección o lugar de la obra",
                              placeholder="Ej.: Calle Mayor 12, Benaguasil",
                              label_visibility="collapsed")
        buscar = b2.form_submit_button("Buscar", use_container_width=True)
    if buscar and texto.strip():
        try:
            with st.spinner("Buscando…"):
                st.session_state["lugares"] = buscar_lugares(texto.strip(), key)
        except Exception as e:
            st.session_state["lugares"] = []
            st.error(f"No se pudo buscar la dirección. {e}")

    lugares = st.session_state.get("lugares", [])
    if lugares:
        etiquetas = [f"{l['nombre']} — {l['direccion']}" if l["nombre"] not in l["direccion"]
                     else l["direccion"] for l in lugares]
        idx = st.selectbox("Selecciona la ubicación", range(len(lugares)),
                           format_func=lambda i: etiquetas[i])
        destino = lugares[idx]
        destino_txt = destino["direccion"]
        try:
            with st.spinner("Calculando ruta…"):
                ruta = calcular_ruta(origen, destino["id"], key)
            if ruta:
                km_ida, min_ida = ruta
                maps_link = (
                    "https://www.google.com/maps/dir/?api=1"
                    f"&origin={quote_plus(origen)}"
                    f"&destination={quote_plus(destino_txt)}"
                    f"&destination_place_id={destino['id']}&travelmode=driving"
                )
                st.success(
                    f"Ida desde {origen}: **{num(km_ida)} km** y **{num(min_ida, 0)} min**. "
                    f"[Ver ruta en Google Maps]({maps_link})"
                )
            else:
                st.warning("Google no encontró ruta en coche hasta esa ubicación. Introduce los datos a mano.")
        except Exception as e:
            st.error(f"No se pudo calcular la ruta. {e}")
    elif not buscar:
        st.caption("Escribe la dirección de la obra y pulsa Buscar.")
else:
    m1, m2 = st.columns(2)
    km_ida = m1.number_input("Km de ida", min_value=0.0, value=20.0, step=1.0, format="%.1f")
    min_ida = m2.number_input("Minutos de ida", min_value=0.0, value=25.0, step=5.0, format="%.0f")
    destino_txt = st.text_input("Población o dirección (opcional)")

d1, d2 = st.columns(2)
viajes = d1.number_input("Días de desplazamiento", min_value=0, value=1, step=1,
                         help="Si la instalación dura 2 días, son 2 viajes de ida y vuelta.")
ida_vuelta = d2.toggle("Contar ida y vuelta", value=True)

# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------
factor = (2 if ida_vuelta else 1) * viajes
km_total = km_ida * factor
horas_viaje = (min_ida * factor) / 60
horas_total = horas_inst + horas_viaje

c_material_ml = metros * eur_ml
c_material_tramo = tramos * eur_tramo
c_material = c_material_ml + c_material_tramo
c_mo_obra = horas_inst * eur_h
c_mo_viaje = horas_viaje * eur_h
c_km = km_total * eur_km
c_gestion = eur_gestion
coste = c_material + c_mo_obra + c_mo_viaje + c_km + c_gestion

if modo_beneficio == "Sobre el coste":
    precio = coste * (1 + beneficio / 100)
else:
    if beneficio >= 100:
        st.error("Con el beneficio aplicado sobre el precio de venta, el porcentaje tiene que ser menor de 100 %.")
        st.stop()
    precio = coste / (1 - beneficio / 100)

ganancia = precio - coste
supera_40 = iva == 10 and precio > 0 and c_material / precio > 0.40
cuota_iva = precio * iva / 100
total = precio + cuota_iva

# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------
st.subheader("Presupuesto")

st.markdown(
    f"""
    <div class="tr-total">
      <div class="lbl">Precio para el cliente (IVA incluido)</div>
      <div class="big">{eur(total)}</div>
      <div class="sub">{eur(precio)} + IVA {num(iva, 0)} % ({eur(cuota_iva)})</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if supera_40:
    st.warning(
        f"El material supone el {num(c_material / precio * 100, 0)} % del precio sin IVA. "
        "Con más del 40 % no se puede aplicar el IVA del 10 %: cambia el IVA al 21 %."
    )

k1, k2, k3 = st.columns(3)
k1.metric("Coste total", eur(coste))
k2.metric("Beneficio", eur(ganancia), f"{num(ganancia / precio * 100 if precio else 0, 1)} % del precio",
          delta_color="off")
k3.metric("Precio por metro", eur(precio / metros) if metros else "—", "sin IVA", delta_color="off")

filas = [
    ("Material por metro", f"{num(metros)} ml × {eur(eur_ml)}", c_material_ml),
    ("Material por tramo", f"{tramos} × {eur(eur_tramo)}", c_material_tramo),
    ("Horas en obra (pareja)", f"{num(horas_inst)} h × {eur(eur_h)}", c_mo_obra),
    ("Horas de viaje (pareja)", f"{num(horas_viaje, 2)} h × {eur(eur_h)}", c_mo_viaje),
    ("Kilometraje", f"{num(km_total)} km × {eur(eur_km)}", c_km),
    ("Gestión administrativa", f"{num(pct_admin, 0)} % de {eur(sueldo_admin)} / {inst_mes} inst.", c_gestion),
]
tabla = "| Partida | Cálculo | Importe |\n|---|---|---:|\n"
tabla += "\n".join(f"| {a} | {b} | {eur(c)} |" for a, b, c in filas)
tabla += f"\n| **Coste total** | | **{eur(coste)}** |"
tabla += f"\n| Beneficio | {num(beneficio, 0)} % {modo_beneficio.lower()} | {eur(ganancia)} |"
tabla += f"\n| **Precio sin IVA** | | **{eur(precio)}** |"
tabla += f"\n| IVA | {num(iva, 0)} % | {eur(cuota_iva)} |"
tabla += f"\n| **Total con IVA** | | **{eur(total)}** |"

with st.expander("Desglose de costes", expanded=True):
    st.markdown(tabla)
    st.caption(f"Horas totales de pareja: {num(horas_total, 2)} h (obra + viaje).")

# Resumen para copiar o descargar
resumen = "\n".join(
    [
        "PRESUPUESTO · TOP REDES VALENCIA",
        f"Fecha: {date.today():%d/%m/%Y}",
        f"Cliente: {cliente or '-'}",
        f"Ubicación: {destino_txt or '-'}",
        "",
        f"Metros lineales: {num(metros)} ml en {tramos} tramo(s)",
        f"Horas en obra (pareja): {num(horas_inst)} h",
        f"Desplazamiento: {num(km_total)} km, {num(horas_viaje, 2)} h ({viajes} día/s)",
        "",
        f"Material: {eur(c_material)}",
        f"Mano de obra: {eur(c_mo_obra + c_mo_viaje)}",
        f"Kilometraje: {eur(c_km)}",
        f"Gestión administrativa: {eur(c_gestion)}",
        f"Coste total: {eur(coste)}",
        f"Beneficio ({num(beneficio, 0)} % {modo_beneficio.lower()}): {eur(ganancia)}",
        "",
        f"Precio sin IVA: {eur(precio)}",
        f"IVA {num(iva, 0)} %: {eur(cuota_iva)}",
        f"TOTAL: {eur(total)}",
    ]
)

with st.expander("Resumen para copiar"):
    st.code(resumen, language=None)

nombre = (cliente or "presupuesto").strip().replace(" ", "_")[:40]
st.download_button(
    "Descargar resumen (.txt)",
    data=resumen.encode("utf-8"),
    file_name=f"{nombre}_{date.today():%Y%m%d}.txt",
    mime="text/plain",
)
