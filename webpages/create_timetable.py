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

weeks = st.sidebar.selectbox("Number of exam weeks (Mon–Fri)", [1, 2, 3], index=1)
generate_btn = st.sidebar.button("Generate Timetable")
exam_days = weeks * 5

if all([cs_file, ist_file, cyb_file, co_file]) and generate_btn:
    cs_df = pd.read_csv(cs_file)
    ist_df = pd.read_csv(ist_file)
    cyb_df = pd.read_csv(cyb_file)
    co_df = pd.read_csv(co_file)

    all_courses_df = pd.concat([cs_df, ist_df, cyb_df], ignore_index=True)
    all_courses_df["units"] = all_courses_df["units"].astype(int)
    all_courses_df["course"] = all_courses_df["course"].str.strip().str.lower()
    all_courses_df = all_courses_df.reset_index(drop=True)
    all_courses = all_courses_df.to_dict(orient="records")  # List of dicts
    course_list = list(range(len(all_courses)))

    unique_units = sorted(set(row["units"] for row in all_courses))
    slot_cache = {u: get_time_slots(u) for u in unique_units}
    slots = []
    slot_time_cache = {}
    for day in range(1, exam_days + 1):
        for units in unique_units:
            for start, end in slot_cache[units]:
                if start >= "09:00" and end <= "17:45":
                    slot = (f"Day {day}", start, end, units)
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

    # === Conflict Map ===
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
        course_list=course_list
    )

    timetable = []
    for idx, slot in best.assignments.items():
        row = all_courses[idx]
        timetable.append({
            "Day": slot[0],
            "Start Time": slot[1],
            "End Time": slot[2],
            "Course": row["course"].upper(),
            "Level": row["level"],
            "Department": row["department"],
            "Units": row["units"]
        })
    timetable_df = pd.DataFrame(timetable)

    pivot_table = timetable_df.copy()
    pivot_table["Slot"] = pivot_table["Start Time"] + "-" + pivot_table["End Time"]
    pivot_table["Info"] = pivot_table["Course"] + " (" + pivot_table["Department"] + ", Lvl " + pivot_table[
        "Level"].astype(str) + ")"
    pivoted = pivot_table.pivot_table(index="Slot", columns="Day", values="Info", aggfunc=lambda x: '\n'.join(x))

    st.subheader("\U0001F4C4 Download Timetable")
    st.dataframe(pivoted.fillna(""))
    csv = pivoted.to_csv(index=True).encode("utf-8")
    st.download_button("Download CSV Timetable", csv, file_name="exam_timetable.csv", mime="text/csv")

    st.subheader("\U0001F4CA Summary Stats")
    st.markdown(f"- Total Courses: **{len(all_courses)}**")
    st.markdown(f"- Total Days: **{exam_days}**")
    st.markdown(f"- Unique Time Slots: **{len(slots)}**")
    st.markdown(f"- Final Fitness Score: **{best.fitness}**")

    st.markdown("### 🧠 Interpretation")
    if best.hard_conflicts == 0 and best.soft_conflicts == 0:
        st.success("✅ No hard or soft conflicts. Timetable is fully optimized!")
    else:
        st.info(f"""
    - **Hard Conflicts**: {best.hard_conflicts} (overlapping exams)
    - **Soft Conflicts**: {best.soft_conflicts} (e.g., exams scheduled with <30 mins gap)
    - Timetable is **feasible** and can be improved if needed.
    """)

    st.subheader("📚 Department-Specific Timetables")
    departments = timetable_df["Department"].unique()
    for dept in sorted(departments):
        st.markdown(f"### 🏛️ {dept} Department")
        dept_df = timetable_df[timetable_df["Department"] == dept].copy()
        dept_df["Slot"] = dept_df["Start Time"] + "-" + dept_df["End Time"]
        dept_df["Info"] = (
                dept_df["Course"]
                + " (Lvl "
                + dept_df["Level"].astype(str)
                + ")"
        )
        pivoted_dept = dept_df.pivot_table(
            index="Slot", columns="Day", values="Info", aggfunc=lambda x: "\n".join(x)
        )
        st.dataframe(pivoted_dept.fillna(""))
        csv_dept = pivoted_dept.to_csv(index=True).encode("utf-8")
        st.download_button(
            f"⬇️ Download {dept} Timetable",
            csv_dept,
            file_name=f"{dept.lower().replace(' ', '_')}_timetable.csv",
            mime="text/csv",
        )
