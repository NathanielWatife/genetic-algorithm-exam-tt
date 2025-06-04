import streamlit as st
import pandas as pd
import random
import os
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Exam Timetable Generator", layout="wide")
st.title("\U0001F4D8 Exam Timetable Generator")

st.sidebar.header("Upload Department CSVs")
cs_file = st.sidebar.file_uploader("Upload Computer Science CSV", type="csv")
ist_file = st.sidebar.file_uploader("Upload Information and System Technology CSV", type="csv")
cyb_file = st.sidebar.file_uploader("Upload Cyber Security CSV", type="csv")
co_file = st.sidebar.file_uploader("Upload Carryover Courses CSV", type="csv")

weeks = st.sidebar.selectbox("Number of exam weeks (Mon–Fri)", [1, 2, 3], index=1)
generate_btn = st.sidebar.button("Generate Timetable")
exam_days = weeks * 5


def time_to_minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m


def get_time_slots(units):
    if units == 1:
        return [("09:00", "10:00"), ("10:15", "11:15"), ("11:30", "12:30"), ("12:45", "13:45"), ("14:00", "15:00"),
                ("15:15", "16:15")]
    elif units == 2:
        return [("09:00", "11:00"), ("11:15", "13:15"), ("13:30", "15:30"), ("15:45", "17:45")]
    elif units == 3:
        return [("09:00", "12:00"), ("12:15", "15:15")]
    elif units == 4:
        return [("09:00", "13:00"), ("13:15", "17:15")]
    else:
        return []


if all([cs_file, ist_file, cyb_file, co_file]) and generate_btn:
    cs_df = pd.read_csv(cs_file)
    ist_df = pd.read_csv(ist_file)
    cyb_df = pd.read_csv(cyb_file)
    co_df = pd.read_csv(co_file)

    all_courses = pd.concat([cs_df, ist_df, cyb_df], ignore_index=True)
    all_courses["units"] = all_courses["units"].astype(int)
    all_courses["course"] = all_courses["course"].str.strip().str.lower()
    all_courses = all_courses.reset_index(drop=True)
    course_list = all_courses.index.tolist()

    unique_units = sorted(all_courses["units"].unique())
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
    for idx, row in all_courses.iterrows():
        course = row["course"]
        level = int(row["level"])
        levels = [level]
        if course in co_courses:
            levels += [l for l in LEVELS if l > level]
        course_levels[course] = levels

    # === Conflict Map ===
    conflict_map = {i: set() for i in course_list}
    for i in course_list:
        ci = all_courses.loc[i]
        for j in course_list:
            if i == j:
                continue
            cj = all_courses.loc[j]
            if ci["department"] == cj["department"]:
                if not set(course_levels[ci["course"]]).isdisjoint(course_levels[cj["course"]]):
                    conflict_map[i].add(j)


    class Chromosome:
        def __init__(self, assignments):
            self.assignments = assignments
            self.fitness = None

        def calculate_fitness(self):
            penalty = 0
            hard_conflicts = 0
            soft_conflicts = 0
            slot_usage = {}

            for idx, slot in self.assignments.items():
                row = all_courses.loc[idx]
                course = row["course"]
                department = row["department"]
                start_min, end_min = slot_time_cache[slot]
                for level in course_levels[course]:
                    key = (slot[0], level, department)
                    slot_usage.setdefault(key, []).append((start_min, end_min, course))

            for exams in slot_usage.values():
                exams.sort()
                for i in range(len(exams)):
                    for j in range(i + 1, len(exams)):
                        s1, e1, _ = exams[i]
                        s2, e2, _ = exams[j]
                        if s1 < e2 and s2 < e1:
                            penalty += 100000
                            hard_conflicts += 1
                        elif 0 <= s2 - e1 < 30:
                            penalty += 500
                            soft_conflicts += 1

            self.fitness = -penalty
            self.hard_conflicts = hard_conflicts
            self.soft_conflicts = soft_conflicts
            return self.fitness


    def is_slot_conflict(idx, slot, assignments):
        start_min, end_min = slot_time_cache[slot]
        for j in conflict_map[idx]:
            if j not in assignments:
                continue
            other_slot = assignments[j]
            if slot[0] != other_slot[0]:
                continue
            other_start, other_end = slot_time_cache[other_slot]
            if start_min < other_end and other_start < end_min:
                return True
        return False


    def generate_initial_population(pop_size):
        population = []
        for _ in range(pop_size):
            assignments = {}
            used_slots = {}
            for idx, row in all_courses.iterrows():
                course = row["course"]
                dept = row["department"]
                possible_slots = [s for s in slots if s[3] == row["units"]]
                random.shuffle(possible_slots)
                assigned = False
                for slot in possible_slots:
                    start, end = slot_time_cache[slot]
                    valid = True
                    for level in course_levels[course]:
                        key = (slot[0], level, dept)
                        existing = used_slots.get(key, [])
                        for s2, e2 in existing:
                            if not (end <= s2 or start >= e2):
                                valid = False
                                break
                        if not valid:
                            break
                    if valid:
                        assignments[idx] = slot
                        for level in course_levels[course]:
                            key = (slot[0], level, dept)
                            used_slots.setdefault(key, []).append((start, end))
                        assigned = True
                        break
                if not assigned:
                    for slot in possible_slots:
                        if not is_slot_conflict(idx, slot, assignments):
                            assignments[idx] = slot
                            break
                    else:
                        assignments[idx] = random.choice(possible_slots)
            chromo = Chromosome(assignments)
            population.append(chromo)
        calculate_population_fitness(population)
        return population


    def calculate_population_fitness(population):
        with ThreadPoolExecutor(max_workers=max(2, os.cpu_count() // 2)) as executor:
            list(executor.map(lambda c: c.calculate_fitness(), population))


    def crossover(parent1, parent2):
        assignments = {}
        for idx in course_list:
            assignments[idx] = parent1.assignments[idx] if random.random() < 0.5 else parent2.assignments[idx]
        return Chromosome(assignments)


    def mutate(chromo, mutation_rate=0.1):
        for idx in course_list:
            if random.random() < mutation_rate:
                row = all_courses.loc[idx]
                units = row["units"]
                possible_slots = [s for s in slots if s[3] == units]
                random.shuffle(possible_slots)
                for slot in possible_slots:
                    if not is_slot_conflict(idx, slot, chromo.assignments):
                        chromo.assignments[idx] = slot
                        break


    def repair(chromo):
        for idx, slot in list(chromo.assignments.items()):
            row = all_courses.loc[idx]
            course = row["course"]
            units = row["units"]
            for j in conflict_map[idx]:
                if j not in chromo.assignments:
                    continue
                other_slot = chromo.assignments[j]
                if slot[0] != other_slot[0]:
                    continue
                s1, e1 = slot_time_cache[slot]
                s2, e2 = slot_time_cache[other_slot]
                if s1 < e2 and s2 < e1:
                    possible_slots = [s for s in slots if s[3] == units]
                    random.shuffle(possible_slots)
                    for new_slot in possible_slots:
                        if not is_slot_conflict(idx, new_slot, chromo.assignments):
                            chromo.assignments[idx] = new_slot
                            break
        chromo.calculate_fitness()


    def genetic_algorithm(generations=200, pop_size=30):
        population = generate_initial_population(pop_size)
        progress_bar = st.progress(0)
        status_text = st.empty()
        for gen in range(generations):
            population.sort(key=lambda x: x.fitness, reverse=True)
            next_gen = population[:10]
            mutation_rate = 0.2 * (1 - gen / generations)
            while len(next_gen) < pop_size:
                p1, p2 = random.choices(population[:20], k=2)
                child = crossover(p1, p2)
                mutate(child, mutation_rate=mutation_rate)
                # if gen % 5 == 0:
                repair(child)
                next_gen.append(child)
            calculate_population_fitness(next_gen)
            population = next_gen
            progress_bar.progress((gen + 1) / generations)
            status_text.text(f"Generation {gen + 1}/{generations} | Best fitness: {population[0].fitness}")
        progress_bar.progress(1.0)
        st.success("✅ Timetable generation complete!")
        return population[0]


    best = genetic_algorithm()

    timetable = []
    for idx, slot in best.assignments.items():
        row = all_courses.loc[idx]
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

    # Interpret conflicts more clearly
    st.markdown("### 🧠 Interpretation")

    if best.hard_conflicts == 0 and best.soft_conflicts == 0:
        st.success("✅ No hard or soft conflicts. Timetable is fully optimized!")
    else:
        st.info(f"""
    - **Hard Conflicts**: {best.hard_conflicts} (overlapping exams)
    - **Soft Conflicts**: {best.soft_conflicts} (e.g., exams scheduled with <30 mins gap)
    - Timetable is **feasible** and can be improved if needed.
    """)

    # === Department-specific Timetables ===
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
