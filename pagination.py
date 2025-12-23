import streamlit as st

# Page Navigation
about_project = st.Page("webpages/home.py", title="About Project", icon=":material/home:")
timetable = st.Page("webpages/create_timetable.py", title="Generate Timetable", icon=":material/calendar_view_week:")
insights = st.Page("webpages/insight.py", title="Project Insights", icon=":material/view_kanban:")
pg = st.navigation([about_project, timetable, insights])

pg.run()
