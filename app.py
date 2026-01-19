import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from shapely.geometry import shape
from folium.features import DivIcon

# --- 1. 页面配置 ---
st.set_page_config(layout="wide", page_title="Site Data Extractor")
st.title("🏙️ Site Data Extractor")

# --- 2. 初始化 Session State ---
if 'map_markers' not in st.session_state:
    st.session_state.map_markers = []
if 'extracted_df' not in st.session_state:
    st.session_state.extracted_df = None
if 'map_center' not in st.session_state:
    st.session_state.map_center = [42.349, -71.066]
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 18


# --- 3. 创建基础地图函数 ---
def create_base_map():
    # 使用固定或上一次提取时锁定的坐标
    m = folium.Map(
        location=st.session_state.map_center,
        zoom_start=st.session_state.map_zoom
    )
    from folium.plugins import Draw
    Draw(
        export=False,
        draw_options={'polyline': False, 'circle': False, 'marker': False, 'circlemarker': False},
        edit_options={'remove': True}
    ).add_to(m)

    for marker in st.session_state.map_markers:
        folium.Marker(
            location=[marker['lat'], marker['lon']],
            icon=DivIcon(
                icon_size=(30, 30),
                icon_anchor=(15, 15),
                html=f"""
                    <div style="
                        font-size: 11pt; color: white; background-color: #0047AB; 
                        border-radius: 50%; width: 24px; height: 24px; 
                        display: flex; justify-content: center; align-items: center;
                        border: 2px solid white; font-weight: bold;
                    "> {marker['id']} </div>
                """
            ),
            popup=marker['popup']
        ).add_to(m)
    return m


# --- 4. 重置功能 ---
if st.sidebar.button("🗑️ Clear All & Reset"):
    st.session_state.map_markers = []
    st.session_state.extracted_df = None
    st.session_state.map_center = [42.349, -71.066]
    st.session_state.map_zoom = 18
    st.rerun()

# --- 5. 渲染地图 ---
# 关键改动：不再实时把 output 的 center 传回 session_state
curr_map = create_base_map()
output = st_folium(
    curr_map,
    width=1200,
    height=500,
    key="stable_map"  # 固定 key 减少不必要的重绘
)

# --- 6. 提取逻辑 ---
st.markdown("---")
if st.button("🔍 Extract & Mark Buildings", type="primary"):
    raw_geom = None
    # 只有在点击按钮时，才去捕捉地图的当前视口状态
    if output:
        if output.get("center"):
            st.session_state.map_center = [output["center"]["lat"], output["center"]["lng"]]
            st.session_state.map_zoom = output["zoom"]

        if output.get("all_draw_features"):
            raw_geom = output["all_draw_features"][0]["geometry"]
        elif output.get("last_active_drawing"):
            raw_geom = output["last_active_drawing"]["geometry"]

    if raw_geom:
        try:
            with st.spinner("🚀 Mapping data..."):
                overpass_url = "https://overpass.kumi.systems/api/interpreter"
                coords = raw_geom['coordinates'][0]
                osm_coords = " ".join([f"{c[1]} {c[0]}" for c in coords])

                query = f"""
                [out:json][timeout:30];
                (way["building"](poly:"{osm_coords}"); relation["building"](poly:"{osm_coords}"););
                out center;
                """

                response = requests.post(overpass_url, data=query)
                data = response.json()

                new_markers = []
                results = []

                for element in data.get('elements', []):
                    tags = element.get('tags', {})
                    lat, lon = element.get('center', {}).get('lat'), element.get('center', {}).get('lon')

                    b_type = tags.get('building', 'yes').capitalize()
                    if b_type not in ['Fence', 'Wall', 'Roof']:
                        idx = len(results) + 1
                        name = tags.get('name', 'Unnamed')
                        addr = f"{tags.get('addr:housenumber', '')} {tags.get('addr:street', '')}".strip(", ")

                        new_markers.append(
                            {'id': idx, 'lat': lat, 'lon': lon, 'popup': f"<b>#{idx}: {name}</b><br>{addr}"})
                        results.append({"#": idx, "Building Name": name, "Full Address": addr,
                                        "Floors": tags.get('building:levels', 'N/A')})

                if results:
                    st.session_state.map_markers = new_markers
                    st.session_state.extracted_df = pd.DataFrame(results)
                    st.rerun()  # 只有这里触发重跑，地图会加载最新的 session_state 坐标
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.warning("Please draw a polygon first.")

# --- 7. 显示表格 ---
if st.session_state.extracted_df is not None:
    st.dataframe(st.session_state.extracted_df, use_container_width=True, hide_index=True)
