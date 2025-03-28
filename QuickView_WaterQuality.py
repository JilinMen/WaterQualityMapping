import ee
import geemap
from IPython.display import display
from ipyleaflet import WidgetControl, DrawControl, TileLayer
from geemap.foliumap import Map

import streamlit as st
import warnings
import sys, os
sys.path.append(os.path.dirname(__file__))
import waterquality_functions as wqf
from typing import Any, Optional, Dict
import fiona
import geopandas as gpd
import numpy as np
import datetime

st.set_page_config(layout="wide")
warnings.filterwarnings("ignore")

# @st.cache_data
# def ee_authenticate(token_name="EARTHENGINE_TOKEN"):
#     geemap.ee_initialize(token_name=token_name)
def uploaded_file_to_gdf(data):
    import tempfile
    import os
    import uuid

    _, file_extension = os.path.splitext(data.name)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(tempfile.gettempdir(), f"{file_id}{file_extension}")

    with open(file_path, "wb") as file:
        file.write(data.getbuffer())

    if file_path.lower().endswith(".kml"):
        fiona.drvsupport.supported_drivers["KML"] = "rw"
        gdf = gpd.read_file(file_path, driver="KML")
    else:
        gdf = gpd.read_file(file_path)

    return gdf


st.sidebar.title("More information:")

st.sidebar.info(
    """
    - email: jmen@ua.edu
    - GitHub repository: <https://github.com/JilinMen/WaterQualityMapping>
    - THE UNIVERSITY OF ALABAMA
    """
)

st.title('Quick View of Water Quality')
st.markdown(
"""
Quickly mapping chlorophyll-a, CDOM, turbidity for inland waters
"""
)

# ee_authenticate(token_name="EARTHENGINE_TOKEN")
# 读取 GEE 账号和密钥
service_account = st.secrets["GEE_SERVICE_ACCOUNT"]
private_key = st.secrets["GEE_PRIVATE_KEY"]

# 解析密钥
credentials = ee.ServiceAccountCredentials(service_account, key_data=private_key)
ee.Initialize(credentials)

col1, col2 = st.columns([3,1])

# 初始化 session_state 变量
default_values = {
    "min_lon": 0,
    "max_lon": 0,
    "min_lat": 0,
    "max_lat": 0,
    "sensor": ["L8_OLI"],
    "atmospheric_correction": "SR",
    "bios": ["Chl-a"]
}

# 可视化参数
st.session_state['vis_chl'] = {
                                "width": 2.5,
                                "height": 0.3,
                                "vmin": 0,  # 颜色条的最小值
                                "vmax": 50,  # 颜色条的最大值
                                "orientation": "horizontal",
                                "label": "Chl-a (mg/L)",
                                # "cmap": "winter",
                                "palette": ["#ccff33", "#9ef01a", "#70e000", "#38b000","#008000"],  # 颜色渐变
                                }
st.session_state['vis_tss'] =  {       # 可视化参数
                                "width": 2.5,
                                "height": 0.3,
                                "vmin": 0,  # 颜色条的最小值
                                "vmax": 50,  # 颜色条的最大值
                                "orientation": "horizontal",
                                "label": "TSS (mg/L)",
                                # "cmap": "winter",
                                "palette": ["#ffe169", "#edc531", "#c9a227", "#a47e1b", "#805b10"],  # 颜色渐变
                                }
st.session_state['vis_cdom'] =  {
                                "width": 2.5,
                                "height": 0.3,
                                "vmin": 0,  # 颜色条的最小值
                                "vmax": 10,  # 颜色条的最大值
                                "orientation": "horizontal",
                                "label": "CDOM (m-1)",
                                # "cmap": "rainbow",
                                "palette": ["#007f5f", "#55a630", "#aacc00", "#d4d700", "#ffff3f"],  # 颜色渐变
                                }

# 检查并设置缺失的 session_state 变量
for key, default_value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

with col1:
    data = st.file_uploader(
        "Upload a GeoJSON file to use as an ROI. Customize timelapse parameters and then click the Submit button 😇👇",
        type=["geojson", "kml", "zip"],
        )
if data:
    gdf = uploaded_file_to_gdf(data)
    st.session_state["roi"] = geemap.gdf_to_ee(gdf, geodesic=False)
    st.session_state['m'].add_gdf(gdf, "ROI")
    bounds = np.array(gdf.bounds)

    # 更新 session_state 中的值（这里要用 `st.session_state.update` 避免冲突）
    st.session_state.update({
        "min_lon": bounds[0][0],
        "min_lat": bounds[0][1],
        "max_lon": bounds[0][2],
        "max_lat": bounds[0][3]
    })

with col2:
    st.write('Date range:')
    start_date = st.date_input("start_date",value=datetime.date.today() - datetime.timedelta(days=30))
    end_date = st.date_input("end_date", value=datetime.date.today())
    st.write('Coordinates:')

    # 创建输入框，并绑定到 session_state，同时使用 on_change 回调
    st.number_input("min lon", value=st.session_state["min_lon"], key="min_lon")
    st.number_input("max lon", value=st.session_state["max_lon"], key="max_lon")
    st.number_input("min lat", value=st.session_state["min_lat"], key="min_lat")
    st.number_input("max lat", value=st.session_state["max_lat"], key="max_lat")

    st.multiselect('Sensor:',["L8_OLI","L9_OLI",'S2A_MSI','S2B_MSI'],default=st.session_state['sensor'],key="sensor")
    st.selectbox("Atmospheric correction:",["SR","ACOLITE"],index=0,key="atmospheric_correction")
    st.multiselect("Bio-optical:",["Chl-a","TSS","CDOM"],default=st.session_state['bios'],key='bios')

    button_run = st.button("Run")
    button_clear = st.button("Clear")

if button_clear:

    print("Clear successfully!")

st.session_state['m'] = Map(center=(35, -95), zoom=4, Draw_export=True)

if button_run:
    st.write('Retrieving images!')
    images, imColl = wqf.match_scenes(
        start_date.isoformat(), end_date.isoformat(), day_range=1,
        surface_reflectance=True,
        limit=[st.session_state["min_lat"], st.session_state["min_lon"], st.session_state["max_lat"], st.session_state["max_lon"]],
        st_lat=None, st_lon=None, filter_tiles=None,
        sensors=", ".join(st.session_state['sensor'])
    )

    st.write("Total images:", len(images))
    st.write("Image list: ",imColl.aggregate_array('system:index').getInfo())
    st.write("Cloud cover: ",imColl.aggregate_array('CLOUD_COVER').getInfo())

    if len(images)==0:
    
        st.write('No image founded!')

    elif st.session_state['atmospheric_correction'] == 'SR':
        collection = imColl

        # transfer to surface reflectance
        if st.session_state['sensor'][0] in ['S2A_MSI', 'S2B_MSI']:
            print('Input S2')
            collection_scaled = collection.map(wqf.scale_reflectance_sentinel)
        elif st.session_state['sensor'][0] in ['L4_TM', 'L5_TM', 'L7_ETM', 'L8_OLI', 'L9_OLI']:
            print('Input Landsat')
            collection_scaled = collection.map(wqf.scale_reflectance_landsat)
        else:
            print("Unsupported sensor for reflectance conversion.",st.session_state['sensor'])
            collection_scaled = collection

        # mosaic images on the same day
        # print("Band names before mosaic: ",collection_scaled.first().bandNames().getInfo())
        collection_day = wqf.merge_by_day(collection_scaled)
        # print("Band names after mosaic: ",collection_day.first().bandNames().getInfo())
        print("Total images after mosaic:", collection_day.size().getInfo())
        # print(collection_day.first().bandNames().getInfo())
        # mask clouds and land
        water_extracted_collection = collection_day.map(wqf.mask_water)
        print("Property names: ",water_extracted_collection.first().propertyNames().getInfo())
        print("Mosaic image list: ",water_extracted_collection.aggregate_array('custom_id').getInfo())
        # print("water_extracted_collection size: ",water_extracted_collection.size().getInfo())

        print("Band names after masking: ",water_extracted_collection.first().bandNames().getInfo())
        # RGB preview
        print('start to map RGB image!')
        wqf.preview_rgb_image(collection_day)
        print('start to map water quality parameters!')
        bios_results = wqf.show_wq(water_extracted_collection)

        print("Processing complete!")
    elif st.session_state['atmospheric_correction'] == 'ACOLITE':
        # with status_output:
        st.write("Applying ACOLITE Atmospheric Correction...")
        collection = wqf.ACOLITE_run(
                    [st.session_state["min_lat"], st.session_state["min_lon"], st.session_state["max_lat"], st.session_state["max_lon"]],
                    start_date.isoformat(), end_date.isoformat(),
                    ", ".join(st.session_state['sensor'])
                    )
        # Ensure collection and imColl have the same start_time by merging metadata
        def merge_scl_or_qa_pixel(image, reference_image):
            if st.session_state['sensor'] == 'S2A_MSI' or st.session_state['sensor'] == 'S2B_MSI':
                flag_band = 'SCL'
            else:
                flag_band = 'QA_PIXEL'
            # Merge the SCL or QA_PIXEL from imColl to ACOLITE collection
            scl_or_qa_pixel = reference_image.select(flag_band).rename(flag_band)  # Or use QA_PIXEL if needed
            return image.addBands(scl_or_qa_pixel)
        
        # Apply the merging function to ensure that both collections have the same SCL/QA_PIXEL
        collection = collection.map(lambda image: merge_scl_or_qa_pixel(image,imColl.filterDate(image.get('time_start')).first()))
        
        print("Atmospheric correction complete!")
        
        collection_day = wqf.merge_by_day(collection)
        
        # mask clouds and land
        water_extracted_collection = collection_day.map(wqf.mask_water)
        print("Band names after masking: ",water_extracted_collection.first().bandNames().getInfo())
        
        # RGB preview
        print('start to map RGB image!')
        wqf.preview_rgb_image(collection_day)
        print('start to map water quality parameters!')
        wqf.show_wq(water_extracted_collection)
        print("Processing complete!")
    else:
        print("Unsupported atmospheric correction method.")

    if "Chl-a" in st.session_state['bios']:
        st.session_state['m'].add_colormap(position=(80, 4), **st.session_state['vis_chl'])
        # st.session_state['m'].add_colorbar(label='Chl-a (mg/m3)',
        #                                    vis_params=st.session_state['vis_chl'],
        #                                    position="bottomright")
    if "TSS" in st.session_state['bios']:
        st.session_state['m'].add_colormap(position=(80, 15), **st.session_state['vis_tss'])
        # st.session_state['m'].add_colorbar(label='TSS (mg/m3)',
        #                                    vis_params=st.session_state['vis_tss'],
        #                                    position="bottomright")
    if "CDOM" in st.session_state['bios']:
        st.session_state['m'].add_colormap(position=(80, 26), **st.session_state['vis_cdom'])
        # st.session_state['m'].add_colorbar(label='CDOM (m-1)',
        #                                    vis_params=st.session_state['vis_cdom'],
        #                                    loc="bottom")

with col1:
    st.session_state['m'].to_streamlit(height=800)





