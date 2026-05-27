import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timezone
import pytz

st.set_page_config(page_title="Live Earthquake Monitor Pro", page_icon="🌍", layout="wide")

# CSS
st.markdown("""
<style>
   .main {background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);}
    h1,h2,h3 {color:#fff;}
   .stMetric {background: rgba(255,255,255,0.05); padding:15px; border-radius:12px; border:1px solid rgba(255,255,255,0.1);}
</style>
""", unsafe_allow_html=True)

st.title("🌍 Live Earthquake Monitor Pro")
st.caption("Real-time USGS data • Global seismic activity • Auto refresh")

# Sidebar
st.sidebar.header("🔍 Filters")
time_range = st.sidebar.selectbox("Time Range", ["Past Hour", "Past Day", "Past 7 Days", "Past 30 Days"], index=1)
min_magnitude = st.sidebar.slider("Min Magnitude", 0.0, 8.0, 2.5, 0.1)
max_depth = st.sidebar.slider("Max Depth km", 0, 700, 700, 10)
show_india = st.sidebar.checkbox("Highlight India Region", True)
auto_refresh = st.sidebar.checkbox("Auto Refresh 60s", False)

if auto_refresh:
    st.sidebar.info("Auto refresh ON")
    st.rerun = st.experimental_rerun if hasattr(st, 'experimental_rerun') else lambda: None

# USGS feed mapping
feed_map = {
    "Past Hour": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson",
    "Past Day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
    "Past 7 Days": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson",
    "Past 30 Days": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson"
}

@st.cache_data(ttl=60)
def fetch_earthquakes(url):
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        features = data['features']
        rows = []
        for f in features:
            props = f['properties']
            coords = f['geometry']['coordinates']
            rows.append({
                'id': f['id'],
                'place': props.get('place', ''),
                'mag': props.get('mag', 0),
                'time': pd.to_datetime(props.get('time'), unit='ms', utc=True),
                'updated': pd.to_datetime(props.get('updated'), unit='ms', utc=True),
                'depth_km': coords[2],
                'lon': coords[0],
                'lat': coords[1],
                'type': props.get('type', ''),
                'status': props.get('status', ''),
                'tsunami': props.get('tsunami', 0)
            })
        df = pd.DataFrame(rows)
        return df
    except Exception as e:
        st.error(f"Data fetch error: {e}")
        return pd.DataFrame()

df_raw = fetch_earthquakes(feed_map[time_range])

if df_raw.empty:
    st.warning("No data available")
    st.stop()

# Filter
df = df_raw[(df_raw['mag'] >= min_magnitude) & (df_raw['depth_km'] <= max_depth)].copy()
df['time_ist'] = df['time'].dt.tz_convert('Asia/Kolkata')

# India region filter
def is_india_region(lat, lon):
    return 6 <= lat <= 38 and 68 <= lon <= 97

df['is_india'] = df.apply(lambda x: is_india_region(x['lat'], x['lon']), axis=1)

# KPIs
c1,c2,c3,c4 = st.columns(4)
c1.metric("Total Quakes", f"{len(df):,}")
c2.metric("Max Magnitude", f"{df['mag'].max():.1f}" if not df.empty else "0")
c3.metric("Avg Depth", f"{df['depth_km'].mean():.0f} km" if not df.empty else "0")
c4.metric("India Region", f"{df['is_india'].sum()}")

st.divider()

# Map
st.subheader("🗺️ Global Earthquake Map")

# Size and color
df['size'] = df['mag'].clip(lower=0).apply(lambda x: max(5, x**2.5))
df['color'] = df['mag']

fig_map = px.scatter_mapbox(
    df,
    lat='lat',
    lon='lon',
    size='size',
    color='mag',
    color_continuous_scale='Reds',
    hover_name='place',
    hover_data={'mag':True,'depth_km':True,'time_ist':True,'lat':False,'lon':False,'size':False},
    zoom=1,
    height=650,
    mapbox_style='open-street-map'
)

fig_map.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0,r=0,t=0,b=0),
    coloraxis_colorbar=dict(title="Mag")
)

# Highlight India
if show_india:
    fig_map.add_trace(go.Scattermapbox(
        lat=[20.5937], lon=[78.9629],
        mode='markers',
        marker=dict(size=0),
        showlegend=False
    ))

st.plotly_chart(fig_map, use_container_width=True)

col1, col2 = st.columns([1.2,1])

with col1:
    st.subheader("📊 Top 10 Strongest")
    top10 = df.nlargest(10, 'mag')[['time_ist','place','mag','depth_km']]
    top10['time_ist'] = top10['time_ist'].dt.strftime('%d %b %H:%M')
    st.dataframe(top10, use_container_width=True, hide_index=True)

    st.subheader("⏱️ Hourly Activity")
df['hour'] = df['time_ist'].dt.floor('h')
hourly = df.groupby('hour').size().reset_index(name='count')
fig_line = px.line(hourly, x='hour', y='count', markers=True)
fig_line.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(15,23,42,0.5)',
                       font=dict(color='white'), height=300)
st.plotly_chart(fig_line, use_container_width=True)

with col2:
    st.subheader("📈 Magnitude Distribution")
    fig_hist = px.histogram(df, x='mag', nbins=20, color_discrete_sequence=['#ef4444'])
    fig_hist.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(15,23,42,0.5)',
                           font=dict(color='white'), height=300, margin=dict(l=0,r=0,t=30,b=0))
    st.plotly_chart(fig_hist, use_container_width=True)

    st.subheader("🌊 Depth vs Magnitude")
    fig_scatter = px.scatter(df, x='depth_km', y='mag', color='mag',
                             color_continuous_scale='Turbo', size='mag',
                             hover_data=['place'])
    fig_scatter.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(15,23,42,0.5)',
                              font=dict(color='white'), height=300, margin=dict(l=0,r=0,t=30,b=0))
    st.plotly_chart(fig_scatter, use_container_width=True)

# India alerts
if show_india and df['is_india'].any():
    st.subheader("🇮🇳 India Region Alerts")
    india_df = df[df['is_india']].sort_values('mag', ascending=False).head(10)
    india_df_display = india_df[['time_ist','place','mag','depth_km']].copy()
    india_df_display['time_ist'] = india_df_display['time_ist'].dt.strftime('%d %b %H:%M IST')
    st.dataframe(india_df_display, use_container_width=True, hide_index=True)

# Tsunami warning
tsunami_df = df[df['tsunami']==1]
if not tsunami_df.empty:
    st.error(f"🌊 Tsunami Warning: {len(tsunami_df)} event(s) flagged")

# Export
st.divider()
st.subheader("💾 Export Live Data")
csv = df[['time_ist','place','mag','depth_km','lat','lon']].to_csv(index=False).encode('utf-8')
st.download_button("Download CSV", csv, f"earthquakes_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")

st.caption(f"Last updated: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d %b %Y %H:%M:%S IST')} • Source: USGS Earthquake Hazards Program")