import streamlit as st
from google import genai
import folium
from streamlit_folium import st_folium
import json
from datetime import datetime, timedelta

# 1. 시스템 핵심 인프라 설정
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="AI 개인 맞춤형 여행 최적화 에이전트", layout="wide")
st.title("✈️ AI 개인 맞춤형 여행·맛집 최적화 시스템")

# 세션 상태 캐시 초기화
if "timeline_data" not in st.session_state:
    st.session_state.timeline_data = None
if "tips_data" not in st.session_state:
    st.session_state.tips_data = []
if "map_center" not in st.session_state:
    st.session_state.map_center = [20.0, 0.0]
if "map_zoom" not in st.session_state:
    st.session_state.map_zoom = 2
if "selected_loc" not in st.session_state:
    st.session_state.selected_loc = None
if "duration" not in st.session_state:
    st.session_state.duration = 1
if "current_destination" not in st.session_state:
    st.session_state.current_destination = ""
if "extend_destination" not in st.session_state:
    st.session_state.extend_destination = None

# 인터페이스 UI/UX 디자인 엔지니어링
st.markdown("""
    <style>
    .timeline-container {
        position: relative;
        padding-left: 30px;
        border-left: 3px solid #06b6d4;
        margin-left: 15px;
        margin-bottom: 15px;
    }
    .timeline-dot {
        position: absolute;
        left: -11px;
        top: 5px;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background-color: #06b6d4;
        border: 3px solid white;
    }
    .timeline-dot-active {
        background-color: #f59e0b !important;
        transform: scale(1.2);
        box-shadow: 0 0 8px #f59e0b;
    }
    </style>
""", unsafe_allow_html=True)

# 연계 확장 요청 처리 로직
if st.session_state.extend_destination:
    target_dest = st.session_state.extend_destination
    st.session_state.extend_destination = None
    
    with st.spinner(f"빅데이터 기반 {target_dest} 연계 광역 동선 최적화 시뮬레이션을 실행 중입니다..."):
        try:
            extend_prompt = f"""
            당신은 광역 국가 연계 동선을 설계하는 전문 여행 컨설팅 엔진입니다.
            기존 목적지 주변의 추천 연계 도시인 '{target_dest}'를 중심으로 3~4일간의 핵심 인텐시브 스케줄을 추가로 연산하십시오.

            [지침 사양]:
            1. '{target_dest}' 지역의 아침, 점심, 저녁 실제 식당 상호명과 핵심 랜드마크를 Day 1부터 Day 3까지 조밀하게 구성하십시오. 모호한 표현은 절대 배제합니다.
            2. 'detail' 필드에 핵심 시그니처 메뉴명과 단가, 'spot_story' 필드에 1~2문장의 압축 비하인드를 반드시 매핑하십시오.

            아래 프로토콜 규격에 부합하는 정제된 JSON 블록만 반환하십시오. 외부 서술은 생략합니다.
            {{
              "tips": [{{"title": "광역 이동 팁", "content": "연계 이동 시 필수 유의사항 고도화 기술"}}],
              "itinerary": [
                {{
                  "day": 1, "time": "12:00", "name": "실존 장소명", "lat": 위도숫자, "lng": 경도숫자,
                  "summary": "일정 구분", "spot_story": "1~2문장 압축 스토리.", "detail": "추천 메뉴 및 안내 상세"
                }}
              ]
            }}
            """
            response = client.models.generate_content(model='gemini-2.5-flash', contents=extend_prompt)
            json_part = response.text.split("```json")[1].split("```")[0].strip()
            parsed_data = json.loads(json_part)
            
            st.session_state.timeline_data = parsed_data.get("itinerary", [])
            st.session_state.tips_data = parsed_data.get("tips", [])
            st.session_state.duration = 3
            
            if st.session_state.timeline_data:
                first_item = st.session_state.timeline_data[0]
                st.session_state.map_center = [first_item.get('lat', 20.0), first_item.get('lng', 0.0)]
                st.session_state.map_zoom = 12
            st.session_state.selected_loc = None
            st.rerun()
        except Exception as e:
            st.error("연계 노드 연산 중 에러가 발생했습니다.")

# 2. 실시간 사용자 컨텍스트 수집 (사이드바 제어판)
with st.sidebar:
    st.header("📋 여행 매개변수 설정")
    destination = st.text_input("📍 목적지 명시", placeholder="예: 프랑스 파리 (필수)")
    
    today = datetime.now().date()
    date_range = st.date_input("📅 여정 일정 선택", value=(today, today + timedelta(days=2)), min_value=today)
    travelers = st.number_input("👥 총 인원 (명)", min_value=1, value=1, step=1)
    
    travel_custom = st.text_area(
        "✨ 고유 여행 스타일 / 제약 사항",
        placeholder="예: 박물관 중심 투어, 걷는 동선 최소화, 여유로운 휴식형 여행 선호"
    )
    
    col_flight1, col_flight2 = st.columns(2)
    with col_flight1:
        arr_time = st.text_input("🛫 현지 도착 예정 시각", placeholder="예: 11:30")
    with col_flight2:
        dep_time = st.text_input("🛬 현지 출발 예정 시각", placeholder="예: 18:00")
        
    accommodation = st.text_input("🏠 예약 숙소 기준점", placeholder="예: 에펠탑 근처 호텔")
    places = st.text_area("📍 선호 경유지 (미입력 시 인공지능이 랜드마크 자동 설계)", placeholder="예: 루브르 박물관, 오르세")
    food_pref = st.text_input("🍜 선호 음식 유형", placeholder="예: 정통 프렌치 코스 요리, 로컬 베이커리 맛집")
    
    submit_button = st.button("🚀 맞춤형 지능 동선 연산")

# 3. 분산 데이터 큐레이션 및 인공지능 매핑 연산
if submit_button:
    if len(date_range) != 2:
        st.warning("여정의 시작일과 종료일을 모두 지정해 주십시오.")
    elif not destination.strip():
        st.error("목적지 필드는 누락될 수 없습니다. 정확한 지역명을 입력해 주십시오.")
    else:
        start_date, end_date = date_range
        st.session_state.duration = (end_date - start_date).days + 1
        
        if st.session_state.current_destination != destination.strip():
            st.session_state.timeline_data = None
            st.session_state.tips_data = []
            st.session_state.current_destination = destination.strip()
        
        user_custom = travel_custom.strip() if travel_custom.strip() else "가장 대중적이고 여유로운 힐링 여행 스타일"
        user_arr = arr_time.strip() if arr_time.strip() else "오전 중 도착"
        user_dep = dep_time.strip() if dep_time.strip() else "오후 늦게 출발"
        user_hotel = accommodation.strip() if accommodation.strip() else "해당 도시 중심가 역 근처 숙소"
        user_places = places.strip() if places.strip() else "없음 (AI가 주요 명소를 직접 선정할 것)"
        user_food = food_pref.strip() if food_pref.strip() else "현지 로컬 대중 음식 및 최고 평점 맛집 전체 추천"
        
        with st.spinner("빅데이터 기반 글로벌 이동 경로 최적화 시뮬레이션을 실행 중입니다..."):
            try:
                prompt = f"""
                당신은 글로벌 여행 컨설팅 플랫폼의 맞춤형 엔진입니다.
                사용자가 전달한 파라미터를 기반으로 {destination} 지역의 {st.session_state.duration}일 여정을 정밀 연산하십시오.

                [분석 데이터 컨텍스트]:
                - 목적지: {destination}
                - 스타일 패러다임: {user_custom}
                - 항공 스케줄: 인바운드 {user_arr} / 아웃바운드 {user_dep}
                - 숙소 베이스캠프: {user_hotel}
                - 지정 희망지: {user_places}
                - 선호 카테고리: {user_food}

                [스케줄 분배 지침]:
                - 만약 여행 기간({st.session_state.duration}일)이 일주일 이상으로 길어질 경우, {destination}의 가장 유명한 핵심 랜드마크와 세끼 맛집 일정은 초반 5일차 분량까지만 완성도 높게 집중 설계하십시오.
                - 그 이후의 일정은 데이터 블록을 전면 비워두십시오.

                [개별 노드 생성 절대 수칙 - 데이터가 존재하는 날짜만 적용]:
                1. 일정이 존재하는 날에는 매일 아침, 점심, 저녁 스케줄에 실제 상호명이 명시된 식당을 강제 배정하십시오. 추상적인 표현은 금지합니다.
                2. 식당 배정 시 'detail' 필드에 핵심 시그니처 메뉴명과 단가를 명시하십시오.
                3. 일자별 스케줄의 최종 노드는 반드시 지정된 숙소 위치인 '{user_hotel}' 또는 해당 숙소 인근 지역으로 회귀하도록 종결 동선을 설계하고, 숙소 복귀 직전 노드에는 야경 스팟 또는 현지 인기 노포 야식 매장을 연계 배치하십시오.
                4. 'spot_story' 필드에는 해당 장소나 메뉴에 숨겨진 배경이나 특징적 비하인드를 정확히 1~2문장으로 함축 기술하십시오.

                아래 프로토콜 규격에 부합하는 정제된 JSON 블록만 반환하십시오. 외부 안내 서술은 전면 생략합니다.

                {{
                  "tips": [
                    {{"title": "가이드 에센셜 제목", "content": "실전 현지 가이드 구조화 텍스트"}}
                  ],
                  "itinerary": [
                    {{
                      "day": 1,
                      "time": "HH:MM",
                      "name": "실존 장소 또는 식당명",
                      "lat": 위도좌표숫자,
                      "lng": 경도좌표숫자,
                      "summary": "일정 구분 표기",
                      "spot_story": "장소 고유의 1~2문장 압축 스토리 텍스트.",
                      "detail": "상세 가이드 정보와 메뉴 추천 텍스트."
                    }}
                  ]
                }}
                """
                response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                json_part = response.text.split("```json")[1].split("```")[0].strip()
                parsed_data = json.loads(json_part)
                
                st.session_state.timeline_data = parsed_data.get("itinerary", [])
                st.session_state.tips_data = parsed_data.get("tips", [])
                
                if st.session_state.timeline_data:
                    first_item = st.session_state.timeline_data[0]
                    st.session_state.map_center = [first_item.get('lat', 20.0), first_item.get('lng', 0.0)]
                    st.session_state.map_zoom = 12
                st.session_state.selected_loc = None

            except Exception as e:
                st.error("실시간 서버 노드 연결 실패. 잠시 후 다시 시도해 주십시오.")

# 4. 종합 대시보드 렌더링 파트
if st.session_state.timeline_data:
    
    if st.session_state.tips_data:
        st.subheader("💡 실시간 여정 인텔리전스 가이드 북")
        with st.container(border=True):
            st.write("해당 인덱스를 확장하여 현지 최적화 팁을 확인하십시오.")
            for tip in st.session_state.tips_data:
                with st.expander(tip.get("title", "💡 종합 안내")):
                    st.info(tip.get("content", "데이터 로드 실패"))
        st.markdown("---")

    col_timeline, col_map = st.columns([1.2, 1.8])

    with col_timeline:
        st.subheader("📋 타임라인 시퀀스 및 핵심 정보")
        
        day_list = [f"{d}일차" for d in range(1, st.session_state.duration + 1)]
        selected_day_str = st.radio("일차별 상세 여정 필터링:", day_list, horizontal=True)
        current_day = int(selected_day_str.replace("일차", ""))
        
        day_items = [item for item in st.session_state.timeline_data if item.get('day') == current_day]
        
        # 📌 실질적인 일정이 존재하는지 검사 (껍데기 유령 데이터 필터링)
        has_valid_schedule = False
        if day_items:
            if any(item.get('name') for item in day_items):
                has_valid_schedule = True

        if not has_valid_schedule:
            st.info(f"✨ {current_day}일차에는 고정된 세부 스케줄이 없습니다.")
            
            suggested_country = "영국 런던 (유로스타 연계)" if "프랑스" in st.session_state.current_destination or "파리" in st.session_state.current_destination else "근교 소도시 및 주변 국가"
            if "일본" in st.session_state.current_destination or "오사카" in st.session_state.current_destination:
                suggested_country = "교토·고베 광역 루트"
                
            st.success(f"""
            **🗺️ 상용 엔진 추천 연계 루트 가이드**
            
            현재 목적지의 핵심 거점 투어가 전반부에 성공적으로 배치되었습니다. {current_day}일차부터는 **{suggested_country}** 여정으로 확장하여 여행을 더 풍성하게 즐겨보시는 것을 추천합니다!
            """)
            
            # 🎯 오타 수정한 구역 (버튼 핸들러)
            if st.button(f"🚀 {suggested_country} 연계 여정 즉시 짜기", use_container_width=True):
                st.session_state.extend_destination = suggested_country
                st.session_state.map_center = [20.0, 0.0]
                st.session_state.map_zoom = 2
                st.rerun()
        else:
            if st.session_state.selected_loc is None and day_items:
                target_lat = day_items[0].get('lat')
                target_lng = day_items[0].get('lng')
                if target_lat is not None and target_lng is not None:
                    st.session_state.map_center = [target_lat, target_lng]
                    st.session_state.map_zoom = 13

            for idx, item in enumerate(day_items):
                item_name = item.get('name')
                if not item_name:
                    continue
                    
                is_active = (item_name == st.session_state.selected_loc)
                dot_class = "timeline-dot timeline-dot-active" if is_active else "timeline-dot"
                
                st.markdown(f"""
                    <div class="timeline-container">
                        <div class="{dot_class}"></div>
                        <span style='color: #06b6d4; font-weight: bold;'>[{item.get('time', '스케줄')}]</span>
                    </div>
                """, unsafe_allow_html=True)
                
                col_btn, col_exp = st.columns([0.4, 0.6])
                with col_btn:
                    if st.button(f"🎯 {item_name}", key=f"focus_{current_day}_{idx}", use_container_width=True):
                        t_lat = item.get('lat')
                        t_lng = item.get('lng')
                        if t_lat is not None and t_lng is not None:
                            st.session_state.map_center = [t_lat, t_lng]
                            st.session_state.map_zoom = 16
                        st.session_state.selected_loc = item_name
                        st.rerun()
                        
                with col_exp:
                    with st.expander("📄 추천 구성 가이드", expanded=is_active):
                        st.write(f"**📌 주요 개요:** {item.get('summary', '')}")
                        
                        if item.get('spot_story'):
                            st.write(f"*🎬 **스토리 큐레이션:** {item.get('spot_story')}*")
                            
                        st.write(item.get('detail', '가이드라인 분석 중'))

    with col_map:
        st.subheader(f"🗺️ 실시간 이동 경로 매핑 지오데이터 ({current_day}일차)")
        
        active_day_locs = [l for l in st.session_state.timeline_data if l.get('day') == current_day]

        current_center = st.session_state.get("map_center", [20.0, 0.0])
        current_zoom = st.session_state.get("map_zoom", 2)

        if (current_center is None or 
            not isinstance(current_center, list) or 
            len(current_center) < 2 or 
            current_center[0] is None or 
            current_center[1] is None):
            
            if active_day_locs and active_day_locs[0].get('lat') is not None:
                current_center = [active_day_locs[0]['lat'], active_day_locs[0]['lng']]
                current_zoom = 13
            else:
                current_center = [46.2276, 2.2137] if "프랑스" in st.session_state.current_destination else [20.0, 0.0]
                current_zoom = 5 if "프랑스" in st.session_state.current_destination else 2

        m = folium.Map(location=current_center, zoom_start=current_zoom)
        
        day_coords = []
        for order, loc in enumerate(active_day_locs):
            loc_lat = loc.get('lat')
            loc_lng = loc.get('lng')
            loc_name = loc.get('name', '지정 장소')
            if loc_lat is not None and loc_lng is not None:
                pos = [loc_lat, loc_lng]
                day_coords.append(pos)
                
                is_selected = (loc_name == st.session_state.selected_loc)
                marker_color = 'orange' if is_selected else 'blue'
                
                summary_text = loc.get('summary', '')
                popup_html = f"""
                <div style='width:220px'>
                    <b>{order+1}. {loc_name}</b> ({loc.get('time', '')})<br>
                    <small style='color:teal; font-weight:bold;'>{summary_text}</small>
                </div>
                """
                
                folium.Marker(
                    location=pos,
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"[{loc.get('time', '')}] {loc_name}",
                    icon=folium.Icon(color=marker_color, icon="cutlery" if "식사" in summary_text or "맛집" in summary_text or "야식" in summary_text else "info-sign")
                ).add_to(m)
        
        if len(day_coords) > 1:
            folium.PolyLine(
                locations=day_coords, 
                color="#06b6d4", 
                weight=5, 
                opacity=0.8,
                tooltip="이동 최적화 경로"
            ).add_to(m)
        
        st_folium(
            m, 
            width=750, 
            height=580, 
            key=f"fly_map_day_{current_day}",
            center=current_center,
            zoom=current_zoom
        )
