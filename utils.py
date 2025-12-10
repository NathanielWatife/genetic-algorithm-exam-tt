import os
import re
import base64
import random
from tkinter.ttk import Treeview

import streamlit as st
from concurrent.futures import ThreadPoolExecutor


def sort_days(cols):
    def day_key(day):
        m = re.match(r"Day (\d+)", str(day))
        return int(m.group(1)) if m else float('inf')
    return sorted(cols, key=day_key)


def open_picture(image_name):
    cwd = os.path.dirname(__file__)
    image_path = os.path.join(cwd, "image", image_name)
    image_path = os.path.abspath(image_path)
    file = open(image_path, "rb")
    images = base64.b64encode(file.read()).decode()
    return images


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


# class Chromosome:
#     def __init__(self, assignments):
#         self.assignments = assignments
#         self.fitness = None
#         self.hard_conflicts = 0
#         self.soft_conflicts = 0
#
#     def calculate_fitness(self, all_courses, slot_time_cache, course_levels, venue_capacity):
#         penalty = 0
#         hard_conflicts = 0
#         soft_conflicts = 0
#         slot_usage = {}
#         venue_usage = {}
#
#         for idx, slot in self.assignments.items():
#             row = all_courses[idx]
#             course = row["course"]
#             department = row["department"]
#             start_min, end_min = slot_time_cache[slot]
#             venue_id = slot[4]
#
#             for level in course_levels[course]:
#                 key = (slot[0], level, department)
#                 slot_usage.setdefault(key, []).append((start_min, end_min, course))
#
#             # venue booking keys
#             venue_key = (slot[0], venue_id)
#             venue_usage.setdefault(venue_key, []).append((start_min, end_min, course, idx))
#
#             # capacity check
#             enrolled = int(row.get("enrolled", 0) or 0)
#             cap = venue_capacity.get(venue_id, 999999)
#             if enrolled > 0 and 0 < cap < enrolled:
#                 # modest penalty for over-capacity (soft conflict)
#                 penalty += 1000
#                 soft_conflicts += 1
#
#
#         for exams in slot_usage.values():
#             exams.sort()
#             for i in range(len(exams)):
#                 for j in range(i + 1, len(exams)):
#                     s1, e1, _ = exams[i]
#                     s2, e2, _ = exams[j]
#                     if s1 < e2 and s2 < e1:
#                         penalty += 100000
#                         hard_conflicts += 1
#                     elif 0 <= s2 - e1 < 30:
#                         penalty += 500
#                         soft_conflicts += 1
#
#         # venue double-bookings (hard)
#         for bookings in venue_usage.values():
#             bookings.sort()
#             for i in range(len(bookings)):
#                 for j in range(i + 1, len(bookings)):
#                     s1, e1, _, _ = bookings[i]
#                     s2, e2, _, _ = bookings[j]
#                     if s1 < e2 and s2 < e1:
#                         penalty += 80000
#                         hard_conflicts += 1
#
#
#
#         self.fitness = -penalty
#         self.hard_conflicts = hard_conflicts
#         self.soft_conflicts = soft_conflicts
#         return self.fitness


class Chromosome:
    def __init__(self, assignments):
        self.assignments = assignments
        self.fitness = None
        self.hard_conflicts = 0
        self.soft_conflicts = 0

    def calculate_fitness(self, all_courses, slot_time_cache, course_levels, venue_capacity):
        penalty = 0
        hard_conflicts = 0
        soft_conflicts = 0

        slot_usage = {}  # (day, level, dept) -> list of (start, end, course)
        venue_usage = {}  # (day, venue_id) -> total enrolled

        for idx, slot in self.assignments.items():
            row = all_courses[idx]
            course = row["course"]
            dept = row["department"]
            level = row["level"]
            start_min, end_min = slot_time_cache[slot]
            venue_id = slot[4]
            enrolled = int(row.get("enrolled", 0) or 0)

            # Track slot usage for conflicts
            for lvl in course_levels[course]:
                key = (slot[0], lvl, dept)
                slot_usage.setdefault(key, []).append((start_min, end_min, course))

            # Track venue usage for proportional allocation
            venue_key = (slot[0], venue_id)
            venue_usage.setdefault(venue_key, 0)
            venue_usage[venue_key] += enrolled

        # Penalize over-capacity per venue
        for (day, venue_id), total in venue_usage.items():
            cap = venue_capacity.get(venue_id, 999999)
            if total > cap:
                overflow = total - cap
                penalty += overflow * 100  # proportional penalty
                soft_conflicts += 1

        # Check slot conflicts (hard & soft)
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


def is_slot_conflict(idx, slot, assignments, slot_time_cache, conflict_map):
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


# def generate_initial_population(pop_size, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity):
#     population = []
#     for _ in range(pop_size):
#         assignments = {}
#         used_slots = {}
#         for idx in course_list:
#             row = all_courses[idx]
#             course = row["course"]
#             dept = row["department"]
#             possible_slots = [s for s in slots if s[3] == row["units"]]
#             random.shuffle(possible_slots)
#             assigned = False
#             for slot in possible_slots:
#                 start, end = slot_time_cache[slot]
#                 valid = True
#                 for level in course_levels[course]:
#                     key = (slot[0], level, dept)
#                     existing = used_slots.get(key, [])
#                     for s2, e2 in existing:
#                         if not (end <= s2 or start >= e2):
#                             valid = False
#                             break
#                     if not valid:
#                         break
#
#                 # quick capacity heuristic: skip obviously too-small venues
#                 if valid:
#                     venue_id = slot[4]
#                     cap = venue_capacity.get(venue_id, 999999)
#                     enrolled = int(row.get('enrolled', 0) or 0)
#                     if enrolled and cap and enrolled > cap:
#                         valid = False
#                 if valid:
#                     assignments[idx] = slot
#                     for level in course_levels[course]:
#                         key = (slot[0], level, dept)
#                         used_slots.setdefault(key, []).append((start, end))
#                     assigned = True
#                     break
#             if not assigned:
#                 for slot in possible_slots:
#                     if not is_slot_conflict(idx, slot, assignments, slot_time_cache, conflict_map):
#                         assignments[idx] = slot
#                         assigned = True
#                         break
#                 # last resort to pick random slots
#                 if not assigned and possible_slots:
#                 # else:
#                     assignments[idx] = random.choice(possible_slots)
#         chromo = Chromosome(assignments)
#         population.append(chromo)
#     calculate_population_fitness(population, all_courses, slot_time_cache, course_levels, venue_capacity)
#     return population


def generate_initial_population(pop_size, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity):
    population = []

    for _ in range(pop_size):
        assignments = {}
        used_venue_students = {}  # (day, venue_id) -> enrolled

        for idx in course_list:
            row = all_courses[idx]
            course = row["course"]
            dept = row["department"]
            units = row["units"]
            enrolled = int(row.get("enrolled", 0) or 0)

            possible_slots = [s for s in slots if s[3] == units]
            random.shuffle(possible_slots)
            assigned = False

            for slot in possible_slots:
                if is_slot_conflict(idx, slot, assignments, slot_time_cache, conflict_map):
                    continue

                venue_id = slot[4]
                cap = venue_capacity.get(venue_id, 999999)
                current_usage = used_venue_students.get((slot[0], venue_id), 0)
                available = cap - current_usage

                if available <= 0:
                    continue  # try next venue

                # Assign as many as possible to this venue
                assigned_students = min(enrolled, available)
                assignments[idx] = slot
                used_venue_students[(slot[0], venue_id)] = current_usage + assigned_students
                assigned = True
                break

            # Last resort: pick any slot ignoring conflicts
            if not assigned and possible_slots:
                slot = random.choice(possible_slots)
                assignments[idx] = slot

        chromo = Chromosome(assignments)
        chromo.calculate_fitness(all_courses, slot_time_cache, course_levels, venue_capacity)
        population.append(chromo)

    return population


def calculate_population_fitness(population, all_courses, slot_time_cache, course_levels, venue_capacity):
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda c: c.calculate_fitness(all_courses, slot_time_cache, course_levels, venue_capacity), population))


def crossover(parent1, parent2, course_list):
    assignments = {}
    for idx in course_list:
        assignments[idx] = parent1.assignments[idx] if random.random() < 0.5 else parent2.assignments[idx]
    return Chromosome(assignments)


# def mutate(chromo, mutation_rate, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity):
#     mutated = False
#     for idx in course_list:
#         if random.random() < mutation_rate:
#             row = all_courses[idx]
#             units = row["units"]
#             possible_slots = [s for s in slots if s[3] == units]
#             random.shuffle(possible_slots)
#             for slot in possible_slots:
#                 if not is_slot_conflict(idx, slot, chromo.assignments, slot_time_cache, conflict_map):
#                     venue_id = slot[4]
#                     cap = venue_capacity.get(venue_id, 999999)
#                     enrolled = int(row.get('enrolled', 0) or 0)
#                     if enrolled and cap and enrolled > cap:
#                         continue
#                     chromo.assignments[idx] = slot
#                     mutated = True
#                     break
#     if mutated:
#         chromo.calculate_fitness(all_courses, slot_time_cache, course_levels, venue_capacity)


def mutate(chromo, mutation_rate, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity):
    mutated = False
    used_venue_students = {}

    # Build current venue usage
    for idx, slot in chromo.assignments.items():
        row = all_courses[idx]
        venue_id = slot[4]
        enrolled = int(row.get("enrolled", 0) or 0)
        key = (slot[0], venue_id)
        used_venue_students.setdefault(key, 0)
        used_venue_students[key] += enrolled

    for idx in course_list:
        if random.random() < mutation_rate:
            row = all_courses[idx]
            units = row["units"]
            enrolled = int(row.get("enrolled", 0) or 0)
            possible_slots = [s for s in slots if s[3] == units]
            random.shuffle(possible_slots)

            for slot in possible_slots:
                if is_slot_conflict(idx, slot, chromo.assignments, slot_time_cache, conflict_map):
                    continue
                venue_id = slot[4]
                cap = venue_capacity.get(venue_id, 999999)
                current_usage = used_venue_students.get((slot[0], venue_id), 0)
                available = cap - current_usage
                if available <= 0:
                    continue

                chromo.assignments[idx] = slot
                used_venue_students[(slot[0], venue_id)] = current_usage + enrolled
                mutated = True
                break

    if mutated:
        chromo.calculate_fitness(all_courses, slot_time_cache, course_levels, venue_capacity)


# def repair(chromo, all_courses, slots, slot_time_cache, course_levels, conflict_map, venue_capacity):
#     repaired = False
#     for idx, slot in list(chromo.assignments.items()):
#         row = all_courses[idx]
#         course = row["course"]
#         units = row["units"]
#         for j in conflict_map[idx]:
#             if j not in chromo.assignments:
#                 continue
#             other_slot = chromo.assignments[j]
#             if slot[0] != other_slot[0]:
#                 continue
#             s1, e1 = slot_time_cache[slot]
#             s2, e2 = slot_time_cache[other_slot]
#             if s1 < e2 and s2 < e1:
#                 possible_slots = [s for s in slots if s[3] == units]
#                 random.shuffle(possible_slots)
#                 for new_slot in possible_slots:
#                     if not is_slot_conflict(idx, new_slot, chromo.assignments, slot_time_cache, conflict_map):
#                         # capacity check for candidate
#                         venue_id = new_slot[4]
#                         cap = venue_capacity.get(venue_id, 999999)
#                         enrolled = int(row.get('enrolled', 0) or 0)
#                         if enrolled and cap and enrolled > cap:
#                             continue
#                         chromo.assignments[idx] = new_slot
#                         repaired = True
#                         break
#     if repaired:
#         chromo.calculate_fitness(all_courses, slot_time_cache, course_levels, venue_capacity)


def repair(chromo, all_courses, slots, slot_time_cache, course_levels, conflict_map, venue_capacity):
    repaired = False
    used_venue_students = {}

    for idx, slot in chromo.assignments.items():
        row = all_courses[idx]
        venue_id = slot[4]
        enrolled = int(row.get("enrolled", 0) or 0)
        key = (slot[0], venue_id)
        used_venue_students.setdefault(key, 0)
        used_venue_students[key] += enrolled

    for idx, slot in list(chromo.assignments.items()):
        row = all_courses[idx]
        units = row["units"]
        enrolled = int(row.get("enrolled", 0) or 0)

        if is_slot_conflict(idx, slot, chromo.assignments, slot_time_cache, conflict_map):
            possible_slots = [s for s in slots if s[3] == units]
            random.shuffle(possible_slots)
            for new_slot in possible_slots:
                venue_id = new_slot[4]
                cap = venue_capacity.get(venue_id, 999999)
                current_usage = used_venue_students.get((new_slot[0], venue_id), 0)
                available = cap - current_usage
                if available <= 0:
                    continue
                chromo.assignments[idx] = new_slot
                used_venue_students[(new_slot[0], venue_id)] = current_usage + enrolled
                repaired = True
                break

    if repaired:
        chromo.calculate_fitness(all_courses, slot_time_cache, course_levels, venue_capacity)


# def genetic_algorithm(
#         generations, pop_size, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity):
#     population = generate_initial_population(
#         pop_size, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity
#     )
#     progress_bar = st.progress(0)
#     status_text = st.empty()
#     for gen in range(generations):
#         population.sort(key=lambda x: x.fitness, reverse=True)
#         next_gen = population[:10]
#         mutation_rate = 0.2 * (1 - gen / generations)
#         while len(next_gen) < pop_size:
#             p1, p2 = random.choices(population[:20], k=2)
#             child = crossover(p1, p2, course_list)
#             mutate(child, mutation_rate, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity)
#             repair(child, all_courses, slots, slot_time_cache, course_levels, conflict_map, venue_capacity)
#             if child.fitness is None:
#                 child.calculate_fitness(all_courses, slot_time_cache, course_levels, venue_capacity)
#             next_gen.append(child)
#         population = next_gen
#         progress_bar.progress((gen + 1) / generations)
#         status_text.text(f"Generation {gen + 1}/{generations} | Best fitness: {population[0].fitness}")
#     progress_bar.progress(1.0)
#     st.success("✅ Timetable generation complete!")
#     return population[0]


def genetic_algorithm(
        generations, pop_size, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity):
    population = generate_initial_population(
        pop_size, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity
    )
    progress_bar = st.progress(0)
    status_text = st.empty()

    for gen in range(generations):
        population.sort(key=lambda x: x.fitness, reverse=True)
        next_gen = population[:10]
        mutation_rate = 0.2 * (1 - gen / generations)

        while len(next_gen) < pop_size:
            p1, p2 = random.choices(population[:20], k=2)
            child = crossover(p1, p2, course_list)
            mutate(child, mutation_rate, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, venue_capacity)
            repair(child, all_courses, slots, slot_time_cache, course_levels, conflict_map, venue_capacity)
            if child.fitness is None:
                child.calculate_fitness(all_courses, slot_time_cache, course_levels, venue_capacity)
            next_gen.append(child)

        population = next_gen
        progress_bar.progress((gen + 1) / generations)
        status_text.text(f"Generation {gen + 1}/{generations} | Best fitness: {population[0].fitness}")

    progress_bar.progress(1.0)
    st.success("✅ Timetable generation complete!")
    return population[0]
