import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from shapely.geometry import shape

# --- 页面配置 ---
st.set_page_config(layout="wide", page_title="Professional Site Data Extractor")
st.title("🏙️ Site Data Extractor: Address & GPS Edition")

# --- 地图初始化 ---
if 'm' not in st.session_state:
    # 默认定位波士顿 Tufts/Chinatown 区域
    m = folium.Map(location=[42.349, -71.066], zoom_start=18)
    from folium.plugins import Draw

    Draw(export=False).add_to(m)
    st.session_state.m = m

st.info("💡 Pro Tip: Each record now includes GPS Coordinates for precise mapping.")
output = st_folium(st.session_state.m, width=1200, height=450, key="main_map")

# --- 核心提取逻辑 ---
if st.button("🔍 Extract Full Architectural Data", type="primary"):
    raw_geom = None
    if output and output.get("all_draw_features"):
        raw_geom = output["all_draw_features"][0]["geometry"]
    elif output and output.get("last_active_drawing"):
        raw_geom = output["last_active_drawing"]["geometry"]

    if raw_geom:
        try:
            with st.spinner("🚀 Gathering GPS and Address data..."):
                overpass_url = "https://overpass.kumi.systems/api/interpreter"
                coords = raw_geom['coordinates'][0]
                osm_coords = " ".join([f"{c[1]} {c[0]}" for c in coords])

                # 请求语句：out center 会返回建筑的中心点坐标
                query = f"""
                [out:json][timeout:30];
                (
                  way["building"](poly:"{osm_coords}");
                  relation["building"](poly:"{osm_coords}");
                );
                out center;
                """

                response = requests.post(overpass_url, data=query)
                data = response.json()

                results = []
                for element in data.get('elements', []):
                    tags = element.get('tags', {})

                    # 1. 提取 GPS 坐标 (从 center 属性中获取)
                    lat = element.get('center', {}).get('lat')
                    lon = element.get('center', {}).get('lon')

                    # 2. 深度地址构建 (加入邮编强制搜索)
                    h_num = tags.get('addr:housenumber', '')
                    street = tags.get('addr:street', '')
                    city = tags.get('addr:city', 'Boston')
                    postcode = tags.get('addr:postcode', '')

                    full_address = f"{h_num} {street}, {city} {postcode}".strip(", ")

                    # 3. 建筑基础信息
                    name = tags.get('name', 'Unnamed Structure')
                    b_type = tags.get('building', 'yes').capitalize()
                    levels = tags.get('building:levels', 'N/A')

                    # 只要是有效的建筑面就记录
                    if b_type not in ['Fence', 'Wall', 'Roof']:
                        results.append({
                            "Building Name": name,
                            "Full Mailing Address": full_address,
                            "Floors": levels,
                            "Latitude": lat,
                            "Longitude": lon,
                            "Usage": b_type,
                            "Postcode": postcode if postcode else "N/A"
                        })

                if results:
                    df = pd.DataFrame(results)
                    st.success(f"✅ Extracted {len(df)} records with GPS data.")

                    # 显示表格：调整了列顺序，让坐标和地址并列
                    display_cols = ["Building Name", "Full Mailing Address", "Floors", "Latitude", "Longitude", "Usage"]
                    st.dataframe(df[display_cols], use_container_width=True)

                    # 导出 CSV
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 Download Geo-Report", csv, "site_gps_report.csv")
                else:
                    st.warning("No valid buildings found in this selection.")
        except Exception as e:
            st.error(f"Extraction error: {e}")
    else:
        st.warning("Please draw a polygon on the map first.")