# import der packages
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import openmeteo_requests
import requests_cache
from retry_requests import retry
import datetime

# website config
st.set_page_config(page_title="Wetter-Dashboard", layout="wide")

# ortsauswahl
orte = st.secrets["ort_verzeichnis"]


ausgewaehlter_ort = st.sidebar.selectbox("Wähle einen Ort:", list(orte.keys()))
coords = orte[ausgewaehlter_ort]

# Titel dynamisch anpassen
st.title(f"🌦️ Wetter-Dashboard für {ausgewaehlter_ort}")

# api abfrage von open-meteo 
@st.cache_data(ttl=3600)
def get_weather_data(lat, lon): 
    # frag den cache ab falls es welchen gibt
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    # sonst frag an
    openmeteo = openmeteo_requests.Client(session = retry_session)

    url = "https://api.open-meteo.com/v1/forecast"

    # nimmt das icon d2 modell für die parameter
    params = {
        "latitude": lat, 
        "longitude": lon, 
        "models": "icon_d2",
        "hourly": ["temperature_2m", "relative_humidity_2m", "rain", "wind_speed_10m", "snow_depth", "pressure_msl", 
                   "wind_direction_10m", "wind_gusts_10m", "soil_temperature_0cm", "snowfall", "shortwave_radiation", "cloud_cover", "is_day"],
        "timezone": "Europe/Berlin",
        "forecast_days": 2,
    }
    # api abfrage von open-meteo
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    # stündliche daten
    hourly = response.Hourly()
    hourly_data = {
        "date": pd.date_range(
            start = pd.to_datetime(hourly.Time() + response.UtcOffsetSeconds(), unit = "s"),
            end = pd.to_datetime(hourly.TimeEnd() + response.UtcOffsetSeconds(), unit = "s"),
            freq = pd.Timedelta(seconds = hourly.Interval()),
            inclusive = "left"
        ),
        "Temperatur (°C)": hourly.Variables(0).ValuesAsNumpy().round(3),
        "Feuchtigkeit (%)": hourly.Variables(1).ValuesAsNumpy().round(3),
        "Regen (mm)": hourly.Variables(2).ValuesAsNumpy().round(3),
        "Windgeschwindigkeit (km/h)": hourly.Variables(3).ValuesAsNumpy().round(3),
        "Schneehöhe (cm)": hourly.Variables(4).ValuesAsNumpy() * 100,
        "Luftdruck (hPa)": hourly.Variables(5).ValuesAsNumpy().round(3),
        "Windrichtung (°)": hourly.Variables(6).ValuesAsNumpy().round(3),
        "Windböen (km/h)": hourly.Variables(7).ValuesAsNumpy().round(3),
        "Bodentemperatur (°C)": hourly.Variables(8).ValuesAsNumpy().round(3),
        "Schneefall (mm)": hourly.Variables(9).ValuesAsNumpy().round(3),
        "Solarstrahlung (W/m2)" : hourly.Variables(10).ValuesAsNumpy().round(3),
        "UV-Index": (hourly.Variables(10).ValuesAsNumpy() / 90).round(1),
        "Wolkenbedeckung (%)" : hourly.Variables(11).ValuesAsNumpy().round(3),
        "Tag/Nacht" : hourly.Variables(12).ValuesAsNumpy().round(3)
    }
    return pd.DataFrame(data = hourly_data)

# koordinaten übergabe für die daten
df = get_weather_data(coords["lat"], coords["lon"])

# aktuelle zeit
jetzt = datetime.datetime.now()

# absolute Differenz zwischen 'jetzt' und allen Zeitstempeln im df
# .idxmin() gibt Index der Zeile mit der kleinsten Differenz
aktueller_index = (df['date'] - jetzt).abs().idxmin()

# daten für genau diesen Zeitpunkt extrahieren
aktueller_stand = df.loc[aktueller_index]


##############################################################################################
##############################################################################################
###################### Aktuelle Bedingungen ##################################################
##############################################################################################
##############################################################################################

st.write(f"### Aktuelle Bedingungen (Stand: {aktueller_stand['date'].strftime('%H:%M')} Uhr)")

col1, col2, col3, col4 = st.columns(4)

# anzeige der aktuellen daten
col1.metric("Temperatur", f"{aktueller_stand['Temperatur (°C)']:.1f} °C")
col2.metric("Windgeschwindigkeit", f"{aktueller_stand['Windgeschwindigkeit (km/h)']:.1f} km/h")
col3.metric("Feuchtigkeit", f"{int(aktueller_stand['Feuchtigkeit (%)'])} %")
col4.metric("Luftdruck", f"{aktueller_stand['Luftdruck (hPa)']:.0f} hPa")

# bodentemperatur als kleine Info darunter
st.caption(f"Bodentemperatur aktuell: {aktueller_stand['Bodentemperatur (°C)']:.1f} °C")

# nur Daten ab der aktuellen Stunde für die Warnungen berücksichtigen
df_zukunft = df[df['date'] >= jetzt]

# prüfen des df auf regen, schnee, wind, glätte etc
hat_regen = df_zukunft["Regen (mm)"].sum() > 0.5
hat_schnee = df_zukunft["Schneefall (mm)"].max() > 0.1
starker_wind = df_zukunft["Windböen (km/h)"].max() > 40
glaette_gefahr = df_zukunft["Bodentemperatur (°C)"].min() <= 0
uv_gefahr = df_zukunft["UV-Index"].max()

st.write("---")


##############################################################################################
##############################################################################################
###################### Kurzer Ausblick 48h  ##################################################
##############################################################################################
##############################################################################################


st.subheader("Ausblick & Warnungen (nächste 48h)")

# icons und texte basierend auf der Logik
warn_cols = st.columns(4)

with warn_cols[0]:
    if hat_regen:
        regen_summe = str(df_zukunft['Regen (mm)'].sum().round(2))[0:3]
        st.info(f"🌧️ **Regen erwartet:** In den nächsten 48h werden {regen_summe}l Regen erwartet. Schirm nicht vergessen!")
    else:
        st.success("☀️ **Trocken:** Kein nennenswerter Regen in Sicht.")

with warn_cols[1]:
    if hat_schnee:
        schnee_summe = str(df_zukunft['Schneefall (mm)'].sum().round(2))[0:3]
        st.warning(f"❄️ **Schneefall:** Es ist mit {schnee_summe}cm Schnee zu rechnen! Glättegefahr!")
    elif glaette_gefahr:
        st.error("⚠️ **Glättegefahr:** Bodentemperaturen unter 0°C! Vorsicht auf den Straßen.")
    else:
        st.success("✅ Keine Glättegefahr durch Bodenfrost.")

with warn_cols[2]:
    if starker_wind:
        wind_max = str(df_zukunft['Windböen (km/h)'].max().round(2))[0:4]
        st.warning(f"💨 **Windwarnung:** Böen bis zu {wind_max} km/h erwartet.")
    else:
        wind_max = str(df_zukunft['Windböen (km/h)'].max().round(2))[0:4]
        st.success(f"🍃 Kein Sturm, Windgeschwindigkeiten bis {wind_max} km/h erwartet.")

with warn_cols[3]:
    uv_max = float(df_zukunft["UV-Index"].max())
    
    if pd.isna(uv_max) or uv_max < 0.1:
        st.success("🌙 Kein UV-Index (Nacht/Abend).")
    elif uv_max < 3:
        st.success(f"☁️ Maximaler UV-Index: {uv_max:.0f}. Keine Gefahr.")
    elif 3 <= uv_max <= 5:
        st.warning(f"☀️ UV-Index {uv_max:.0f} (Mäßig). Schutz empfohlen.")
    elif 6 <= uv_max <= 7:
        st.warning(f"⚠️ UV-Index {uv_max:.0f} (Hoch). Sonnencreme nutzen!")
    elif 8 <= uv_max <= 10:
        st.error(f"🔥 UV-Index {uv_max:.0f} (Sehr hoch). Gefahr!")
    else:
        st.error(f"🚫 UV-Index {uv_max:.0f} (Extrem). Schatten suchen!")

st.write("---")


##############################################################################################
##############################################################################################
###################### 3h Zweitagesausblick ##################################################
##############################################################################################
##############################################################################################

# --- 3-STÜNDLICHE VORHERSAGE-LEISTE ---
st.subheader("Kurzfristiger Zweitagesausblick (dreistündlich)")

# gruppieren der nächsten 36h
df_resampled = df_zukunft.set_index('date').resample('3h').agg({
    'Temperatur (°C)': 'mean',
    'Regen (mm)': 'sum',
    'Schneefall (mm)': 'sum',
    'Wolkenbedeckung (%)': 'mean',
    'Tag/Nacht': 'mean'
}).head(12)

# erstelle spalten für die symbole
cols = st.columns(len(df_resampled))

for i, (timestamp, row) in enumerate(df_resampled.iterrows()):
    with cols[i]:
        st.write(f"**{timestamp.strftime('%H:%M')}**")
        
        wolken = row['Wolkenbedeckung (%)']
        regen = row['Regen (mm)']
        schnee = row['Schneefall (mm)']
        # falls es überwiegend hell ist
        ist_tag = row['Tag/Nacht'] > 0.5

        # Logik-Hierarchie
        if schnee > 0.1:
            icon = "❄️" # Schnee
        elif regen > 0.5:
            icon = "🌧️" # Starkregen
        elif regen > 0.1:
            # Bei Regen: Mix-Icon nur tagsüber, nachts eher Wolke+Regen
            icon = "🌦️" if ist_tag else "🌧️"
        elif wolken > 80:
            icon = "☁️" # Ganz bedeckt
        elif wolken > 50:
            icon = "🌥️" if ist_tag else "☁️" # Wolken dominieren
        elif wolken > 20:
            icon = "🌤️" if ist_tag else "☁️" # Leicht bewölkt
        else:
            # Klarer Himmel (< 20% Wolken)
            icon = "☀️" if ist_tag else "🌙"

        st.write(f"## {icon}")
        st.write(f"{row['Temperatur (°C)']:.0f}°C")

st.write("---")


##############################################################################################
##############################################################################################
###################### Detaillierte 48h Vorhersage ###########################################
##############################################################################################
##############################################################################################

# wettervorhersage für die nächsten 48h
st.subheader("Detaillierter Wetterverlauf (nächste 48h)")

# 1. TEMPERATUR & FEUCHTIGKEIT
fig1 = make_subplots(specs=[[{"secondary_y": True}]])

fig1.add_trace(go.Scatter(x=df_zukunft['date'], y=df_zukunft['Temperatur (°C)'], name="Temperatur (°C)", line=dict(color="red")), secondary_y=False)
fig1.add_trace(go.Scatter(x=df_zukunft['date'], y=df_zukunft['Bodentemperatur (°C)'], name="Bodentemperatur (0cm)", line=dict(color="orange", dash='dash')), secondary_y=False)
fig1.add_trace(go.Scatter(x=df_zukunft['date'], y=df_zukunft['Feuchtigkeit (%)'], name="rel. Feuchte (%)", line=dict(color="blue", width=1)), secondary_y=True)

fig1.update_layout(title_text="Temperatur vs. Luftfeuchtigkeit")
fig1.update_yaxes(title_text="Temperatur (°C)", secondary_y=False)
fig1.update_yaxes(title_text="Feuchtigkeit (%)", secondary_y=True)
st.plotly_chart(fig1, use_container_width=True)

# 2. WIND (Linie, Böen & Richtung)
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=df_zukunft['date'], y=df_zukunft['Windgeschwindigkeit (km/h)'], name="Windgeschwindigkeit", line=dict(color="green")))
fig2.add_trace(go.Scatter(x=df_zukunft['date'], y=df_zukunft['Windböen (km/h)'], name="Windböen", line=dict(color="lightgreen", width=1)))
# windrichtung als punkte auf der windgeschwindigkeit
fig2.add_trace(go.Scatter(x=df_zukunft['date'], y=df_zukunft['Windgeschwindigkeit (km/h)'], name="Windrichtung (°)", mode='markers', marker=dict(symbol='arrow', angle=df_zukunft['Windrichtung (°)'], size=10)))

fig2.update_layout(title="Wind (Geschwindigkeit & Böen in km/h)")
st.plotly_chart(fig2, use_container_width=True)

# 3. NIEDERSCHLAG & SCHNEEHÖHE
fig3 = make_subplots(specs=[[{"secondary_y": True}]])
fig3.add_trace(go.Bar(x=df_zukunft['date'], y=df_zukunft['Regen (mm)'], name="Regen (mm)", marker_color='green'), secondary_y=False)
fig3.add_trace(go.Bar(x=df_zukunft['date'], y=df_zukunft['Schneefall (mm)'], name="Schnee (mm)", marker_color='royalblue'), secondary_y=False)
fig3.add_trace(go.Scatter(x=df_zukunft['date'], y=df_zukunft['Schneehöhe (cm)'], name="Schneehöhe (cm)", line=dict(color="lightblue")), secondary_y=True)

fig3.update_layout(title="Niederschlag & Schneehöhe")
st.plotly_chart(fig3, use_container_width=True)

# 4. SOLARSTRAHLUNG & UV
fig4 = make_subplots(specs=[[{"secondary_y": True}]])
fig4.add_trace(go.Bar(x=df_zukunft['date'], y=df_zukunft['Solarstrahlung (W/m2)'], name="Solarstrahlung (W/m2)", marker_color='yellow'), secondary_y=False)
fig4.add_trace(go.Bar(x=df_zukunft['date'], y=df_zukunft['UV-Index'], name="UV-Index", marker_color='red'), secondary_y=True)
fig4.update_layout(title="Solarstrahlung & UV")
st.plotly_chart(fig4, use_container_width=True)

# 5. LUFTDRUCK
fig5 = px.line(df_zukunft, x="date", y="Luftdruck (hPa)", title="Luftdruck (hPa)", labels={"Luftdruck (hPa)": "hPa"})
fig5.update_traces(line_color='purple')
st.plotly_chart(fig5, use_container_width=True)