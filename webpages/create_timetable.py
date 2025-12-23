import pandas as pd
from utils import *

st.set_page_config(page_title="Exam Timetable Generator",
                   page_icon="\U0001F4D8",
                   layout="wide")

st.markdown(f"""
<img src="data:image/jpeg;base64,{open_picture('noun (2).png')}" width="10%"><br>
""", unsafe_allow_html=True)

st.title("\U0001F4D8 Exam Timetable Generator")

st.sidebar.header("Upload Department CSVs")
cs_file = st.sidebar.file_uploader("Upload Computer Science CSV", type="csv")
ist_file = st.sidebar.file_uploader("Upload Information and System Technology CSV", type="csv")
cyb_file = st.sidebar.file_uploader("Upload Cyber Security CSV", type="csv")
co_file = st.sidebar.file_uploader("Upload Carryover Courses CSV", type="csv")

# Upload venue csv data
venue_file = st.sidebar.file_uploader("Upload Venue Lists CSV", type="csv")

weeks = st.sidebar.number_input("Number of exam weeks (Mon–Fri)", min_value=1, max_value=5, step=1, value=1)

# Selects number of venues
venues = st.sidebar.number_input("How many venues for the exam", min_value=1, max_value=6, step=1, value=2)

generate_btn = st.sidebar.button("Generate Timetable")

exam_days = weeks * 5


# Helper to check if all files are uploaded
def all_files_uploaded():
    return all([cs_file, ist_file, cyb_file, co_file, venue_file])


# Regenerate timetable if button is pressed
if generate_btn and all_files_uploaded():
    cs_df = pd.read_csv(cs_file)
    ist_df = pd.read_csv(ist_file)
    cyb_df = pd.read_csv(cyb_file)
    co_df = pd.read_csv(co_file)
    venues_df = pd.read_csv(venue_file)

    all_courses_df = pd.concat([cs_df, ist_df, cyb_df], ignore_index=True)
    all_courses_df["units"] = all_courses_df["units"].astype(int)
    all_courses_df["course"] = all_courses_df["course"].str.strip().str.lower()
    all_courses_df = all_courses_df.reset_index(drop=True)
    all_courses = all_courses_df.to_dict(orient="records")
    course_list = list(range(len(all_courses)))

    # venue mapping
    venues_list = venues_df.to_dict(orient='records')
    # Use only the number of venues the user selected
    venues_list = venues_list[:venues]  # venues variable from sidebar selectbox
    # quick maps
    venue_capacity = {v['venue_id']: int(v['capacity']) for v in venues_list}
    venue_name = {v['venue_id']: v.get('venue_name', v['venue_id']) for v in venues_list}

    # show chosen venues
    st.sidebar.markdown("**Using venues:**")
    for v in venues_list:
        st.sidebar.markdown(f"- {v.get('venue_name', v['venue_id'])} (ID: {v['venue_id']}, cap: {v['capacity']})")


    unique_units = sorted(set(row["units"] for row in all_courses))
    slot_cache = {u: get_time_slots(u) for u in unique_units}

    slots = []
    slot_time_cache = {}
    for day in range(1, exam_days + 1):
        for units in unique_units:
            for start, end in slot_cache[units]:
                if start >= "09:00" and end <= "17:45":
                    for venue in venues_list:
                        venue_id = venue["venue_id"]
                        slot = (f"Day {day}", start, end, units, venue_id)
                        slots.append(slot)
                        slot_time_cache[slot] = (time_to_minutes(start), time_to_minutes(end))

    LEVELS = [100, 200, 300, 400]
    co_courses = set(co_df[co_df["is_carryover"] == True]["course"].str.strip().str.lower())
    course_levels = {}
    for idx, row in enumerate(all_courses):
        course = row["course"]
        level = int(row["level"])
        levels = [level]
        if course in co_courses:
            levels += [i for i in LEVELS if i > level]
        course_levels[course] = levels

    conflict_map = {i: set() for i in course_list}
    for i in course_list:
        ci = all_courses[i]
        for j in course_list:
            if i == j:
                continue
            cj = all_courses[j]
            if ci["department"] == cj["department"]:
                if not set(course_levels[ci["course"]]).isdisjoint(course_levels[cj["course"]]):
                    conflict_map[i].add(j)

    best = genetic_algorithm(
        generations=200,
        pop_size=30,
        all_courses=all_courses,
        slots=slots,
        slot_time_cache=slot_time_cache,
        course_levels=course_levels,
        conflict_map=conflict_map,
        course_list=course_list,
        venue_capacity=venue_capacity
    )

    timetable = []
    for idx, slot in best.assignments.items():
        row = all_courses[idx]
        venue_id = slot[4]
        timetable.append({
            "Day": slot[0],
            "Start Time": slot[1],
            "End Time": slot[2],
            "Course": row["course"].upper(),
            "Level": row["level"],
            "Department": row["department"],
            "Units": row["units"],
            "Venue ID": venue_id,
            "Venue": venue_name.get(venue_id, venue_id),
            "Venue Capacity": venue_capacity.get(venue_id, None),
            "Enrolled": row.get("enrolled", 0)

        })
    timetable_df = pd.DataFrame(timetable)

    pivot_table = timetable_df.copy()
    pivot_table["Slot"] = pivot_table["Start Time"] + "-" + pivot_table["End Time"]
    # pivot_table["Info"] = pivot_table["Course"] + " (" + pivot_table["Department"] + ", Lvl " + pivot_table["Level"].astype(str) + ")"
    pivot_table["Info"] = pivot_table["Course"] + " (" + pivot_table["Department"] + ", Lvl " + pivot_table["Level"].astype(str) + ", " + pivot_table["Venue"] + ")"

    pivoted = pivot_table.pivot_table(index="Slot", columns="Day", values="Info", aggfunc=lambda x: '\n'.join(x))

    # Store in session state
    st.session_state["timetable_df"] = timetable_df
    st.session_state["pivoted"] = pivoted
    st.session_state["departments"] = timetable_df["Department"].unique()
    st.session_state["dept_pivoted"] = {
        dept: timetable_df[timetable_df["Department"] == dept]
        .assign(Slot=lambda df: df["Start Time"] + "-" + df["End Time"])
        # .assign(Info=lambda df: df["Course"] + " (Lvl " + df["Level"].astype(str) + ")")
        .assign(Info=lambda df: df["Course"] + " (Lvl " + df["Level"].astype(str) + ", " + df["Venue"] + ")")
        .pivot_table(index="Slot", columns="Day", values="Info", aggfunc=lambda x: "\n".join(x))
        for dept in timetable_df["Department"].unique()
    }
    st.session_state["summary"] = {
        "total_courses": len(all_courses),
        "total_days": exam_days,
        "unique_slots": len(slots),
        "fitness": best.fitness,
        "hard_conflicts": best.hard_conflicts,
        "soft_conflicts": best.soft_conflicts
    }
    st.session_state["generated"] = True

# Display timetable if generated
if st.session_state.get("generated", False):
    timetable_df = st.session_state["timetable_df"]
    pivoted = st.session_state["pivoted"]
    departments = st.session_state["departments"]
    dept_pivoted = st.session_state["dept_pivoted"]
    summary = st.session_state["summary"]

    # Sort days in columns
    pivoted_sort = sort_days(pivoted.columns)
    pivoted = pivoted[pivoted_sort]

    st.subheader("\U0001F4C4 General Timetable for all departments.")
    st.dataframe(pivoted.fillna(""))
    csv = pivoted.to_csv(index=True).encode("utf-8")
    st.download_button("Download General Timetable for all departments", csv, file_name="exam_timetable.csv", mime="text/csv")

    st.subheader("\U0001F4CA Summary Stats")
    st.markdown(f"- Total Courses: **{summary['total_courses']}**")
    st.markdown(f"- Total Days: **{summary['total_days']}**")
    st.markdown(f"- Unique Time Slots: **{summary['unique_slots']}**")
    st.markdown(f"- Final Fitness Score: **{summary['fitness']}**")

    st.markdown("### 🧠 Interpretation")
    if summary["hard_conflicts"] == 0 and summary["soft_conflicts"] == 0:
        st.success("✅ No hard or soft conflicts. Timetable is fully optimized!")
    else:
        st.info(f"""
    - **Hard Conflicts**: {summary['hard_conflicts']} (overlapping exams)
    - **Soft Conflicts**: {summary['soft_conflicts']} (e.g., exams scheduled with <30 mins gap)
    - Timetable is **feasible** and can be improved if needed.
    """)

    st.subheader("📚 Department-Specific Timetables")
    for dept in sorted(departments):
        st.markdown(f"### 🏛️ {dept} Department")
        pivoted_dept = dept_pivoted[dept]
        sorted_cols = sort_days(pivoted_dept.columns)
        pivoted_dept = pivoted_dept[sorted_cols]
        st.dataframe(pivoted_dept.fillna(""))
        csv_dept = pivoted_dept.to_csv(index=True).encode("utf-8")
        st.download_button(
            f"⬇️ Download {dept} Timetable",
            csv_dept,
            file_name=f"{dept.lower().replace(' ', '_')}_timetable.csv",
            mime="text/csv",
        )
else:
    st.info("Upload all required CSVs and click **Generate Timetable** to begin.")