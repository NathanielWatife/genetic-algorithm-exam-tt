import streamlit as st

# Page Navigation
About_Project = st.Page("webpages/home.py", title="About Project", icon=":material/home:")
timetable = st.Page("webpages/create_timetable.py", title="Generate Timetable", icon=":material/calendar_view_week:")

pg = st.navigation([About_Project, timetable])

pg.run()
