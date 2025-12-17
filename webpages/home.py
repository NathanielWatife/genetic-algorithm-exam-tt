import streamlit as st
from utils import open_picture

st.set_page_config(page_title="Exam Timetable Generator - Home",
                   page_icon="🗣",
                   layout="wide")

st.markdown(f"""
<img src="data:image/jpeg;base64,{open_picture('Yabatech.jpg')}" width="20%"><br>
""", unsafe_allow_html=True)

st.header("Welcome to the Exam Timetable Generator")

st.markdown("""
This application helps you generate an optimized exam timetable for multiple departments using a genetic algorithm.

---

### 🧬 How It Works

1. **Upload Data**  
   Upload CSV files for each department and for carryover courses using the sidebar.

2. **Configure Exam Weeks**  
   Select the number of exam weeks (each week is Monday–Friday).

3. **Generate Timetable**  
   Click **Generate Timetable** to start the optimization. The algorithm will:
   - Assign all exams to available time slots (09:00–17:45)
   - Avoid hard conflicts (no overlapping exams for the same department and level, including carryovers)
   - Minimize soft conflicts (exams scheduled with less than 30 minutes gap)
   - Handle different exam durations based on course units

4. **Review & Download**  
   - View the generated timetable in a pivoted table format
   - Download the full timetable or department-specific timetables as CSV
   - See summary statistics and conflict interpretation

---

### 🚀 Getting Started

- Use the sidebar to upload all required CSV files (Computer Science, Information and System Technology, Cyber Security,
Carryover Courses)
- Select the number of exam weeks
- Click **Generate Timetable**
- Download and review your optimized schedule

---

### ⚡ Features

- **Genetic Algorithm Optimization**: Fast, parallelized search for feasible timetables
- **Conflict Handling**: No overlapping exams for the same department/level, including carryovers
- **Flexible Durations**: Supports 1–4 unit courses with appropriate time slots
- **Department Views**: Download department-specific timetables
- **Summary & Interpretation**: See hard/soft conflict counts and overall fitness

""")
