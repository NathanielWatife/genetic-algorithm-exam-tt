import os
import re
import base64
import random
from typing import Any

import streamlit as st
from concurrent.futures import ThreadPoolExecutor


def sort_days(cols: Any) -> list:
    """
    Sort column labels that follow the format 'Day N' numerically.

    This helper function ensures that timetable columns such as
    'Day 1', 'Day 2', ..., 'Day 10' are ordered by their numeric
    day value rather than lexicographically.

    Args:
        cols (Iterable): Iterable of column labels.

    Returns:
        list: Sorted list of column labels based on day number.
    """
    def day_key(day: Any) -> int | float:
        """
        Extract numeric day index from a column label.

        Args:
            day (Any): Column label, expected to contain 'Day N'.

        Returns:
            int or float: Numeric day value if matched, otherwise infinity.
        """
        m = re.match(r"Day (\d+)", str(day))
        return int(m.group(1)) if m else float('inf')
    return sorted(cols, key=day_key)


def open_picture(image_name: str) -> str:
    """
    Load an image file from the local 'image' directory and encode it in Base64.

    This is typically used for embedding images (logos, diagrams) directly
    into Streamlit or HTML templates.

    Args:
        image_name (str): Name of the image file.

    Returns:
        str: Base64-encoded string representation of the image.
    """
    cwd = os.path.dirname(__file__)
    image_path = os.path.join(cwd, "image", image_name)
    image_path = os.path.abspath(image_path)

    with open(image_path, "rb") as file:
    # file = open(image_path, "rb")
        images = base64.b64encode(file.read()).decode()
    return images


def time_to_minutes(t: str) -> int:
    """
    Convert a time string (HH:MM) into total minutes since midnight.

    Args:
        t (str): Time string in 'HH:MM' format.

    Returns:
        int: Total minutes since midnight.
    """
    h, m = map(int, t.split(":"))
    return h * 60 + m


def get_time_slots(units: int) -> list[tuple[str, str]]:
    """
    Return valid exam time slots based on course credit units.

    The function defines allowed exam durations and corresponding
    time slots for different course unit loads.

    Args:
        units (int): Number of credit units for the course.

    Returns:
        list[tuple[str, str]]: List of (start_time, end_time) tuples.
    """
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


class Chromosome:
    """
    Represents a single timetable solution in the genetic algorithm.

    A chromosome maps course indices to assigned exam slots and
    tracks both hard and soft constraint violations.
    """
    def __init__(self, assignments: Any) -> None:
        """
        Initialize a chromosome.

        Args:
            assignments (dict): Mapping of course index -> slot tuple.
        """
        self.assignments = assignments
        self.fitness = None
        self.hard_conflicts = 0
        self.soft_conflicts = 0

    def calculate_fitness(
            self, all_courses: list[dict],
            slot_time_cache: dict, course_levels: dict,
            venue_capacity: dict) -> int:
        """
        Compute the fitness score of the chromosome.

        Fitness is calculated as the negative total penalty incurred
        from violating scheduling constraints.

        Hard constraints (severe penalties):
        - Overlapping exams for the same department and level

        Soft constraints (lighter penalties):
        - Consecutive exams with short gaps
        - Venue over-capacity (penalized proportionally)

        Args:
            all_courses (list[dict]): All course records.
            slot_time_cache (dict): Slot -> (start_min, end_min) mapping.
            course_levels (dict): Course -> list of affected levels.
            venue_capacity (dict): Venue ID -> seating capacity.

        Returns:
            int: Fitness score (higher is better).
        """
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


def is_slot_conflict(idx: int, slot: tuple, assignments: dict, slot_time_cache: dict, conflict_map: dict) -> bool:
    """
    Check whether assigning a course to a slot causes a time conflict.

    Args:
        idx (int): Course index being evaluated.
        slot (tuple): Proposed exam slot.
        assignments (dict): Current course-slot assignments.
        slot_time_cache (dict): Slot -> (start_min, end_min).
        conflict_map (dict): Course index -> conflicting course indices.

    Returns:
        bool: True if a conflict exists, otherwise False.
    """
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


def generate_initial_population(
        pop_size: int, all_courses: list[dict], slots: list[tuple],
        slot_time_cache: dict, course_levels: dict, conflict_map: dict,
        course_list: list[int], venue_capacity: dict) -> list[Chromosome]:
    """
    Generate the initial population of chromosomes.

    Each chromosome represents a feasible (or near-feasible) exam timetable.
    The generation process attempts to:
    - Avoid time conflicts
    - Respect venue capacity constraints
    - Proportionally allocate students to venues where possible

    Args:
        pop_size (int): Number of chromosomes to generate.
        all_courses (list[dict]): List of all course records.
        slots (list[tuple]): All available exam slots.
        slot_time_cache (dict): Slot -> (start_min, end_min).
        course_levels (dict): Course -> affected academic levels.
        conflict_map (dict): Course index -> conflicting course indices.
        course_list (list[int]): Ordered list of course indices to schedule.
        venue_capacity (dict): Venue ID -> seating capacity.

    Returns:
        list[Chromosome]: Initial population of chromosomes.
    """
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


def calculate_population_fitness(
        population: list[Chromosome], all_courses: list[dict],
        slot_time_cache: dict, course_levels: dict, venue_capacity: dict) -> None:
    """
    Calculate fitness values for all chromosomes in the population.

    Fitness evaluation is parallelized using a thread pool to
    speed up computation for large populations.

    Args:
        population (list[Chromosome]): Population of chromosomes.
        all_courses (list[dict]): Course dataset.
        slot_time_cache (dict): Slot -> (start_min, end_min).
        course_levels (dict): Course -> affected academic levels.
        venue_capacity (dict): Venue ID -> seating capacity.
    """
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(
            executor.map(
                lambda c: c.calculate_fitness(
                    all_courses, slot_time_cache, course_levels, venue_capacity
                ), population
            )
        )


def crossover(parent1: Chromosome, parent2: Chromosome, course_list: list[int]) -> Chromosome:
    """
    Perform uniform crossover between two parent chromosomes.

    For each course, the child's slot assignment is randomly
    selected from one of the two parents with equal probability.

    Args:
        parent1 (Chromosome): First parent chromosome.
        parent2 (Chromosome): Second parent chromosome.
        course_list (list[int]): List of course indices.

    Returns:
        Chromosome: Newly created offspring chromosome.
    """
    assignments = {}
    for idx in course_list:
        assignments[idx] = parent1.assignments[idx] if random.random() < 0.5 else parent2.assignments[idx]
    return Chromosome(assignments)


def mutate(
        chromo: Chromosome, mutation_rate: float, all_courses: list[dict],
        slots: list[tuple], slot_time_cache: dict, course_levels: dict,
        conflict_map: dict, course_list: list[int], venue_capacity: dict) -> None:
    """
    Mutate a chromosome by randomly reassigning exam slots.

    Mutation introduces diversity and helps escape local optima.
    The process attempts to:
    - Respect time conflicts
    - Avoid venue over-capacity where possible

    Args:
        chromo (Chromosome): Chromosome to mutate.
        mutation_rate (float): Probability of mutating each gene.
        all_courses (list[dict]): Course dataset.
        slots (list[tuple]): All available exam slots.
        slot_time_cache (dict): Slot -> (start_min, end_min).
        course_levels (dict): Course -> affected academic levels.
        conflict_map (dict): Course index -> conflicting course indices.
        course_list (list[int]): Ordered list of course indices.
        venue_capacity (dict): Venue ID -> seating capacity.
    """
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


def repair(
        chromo: Chromosome, all_courses: list[dict], slots: list[tuple],
        slot_time_cache: dict, course_levels: dict, conflict_map: dict, venue_capacity: dict) -> None:
    """
    Repair an infeasible chromosome by resolving conflicts.

    This function attempts to:
    - Fix overlapping exam slots
    - Reduce venue over-capacity issues

    Repairs are performed greedily and only applied when
    a conflict is detected.

    Args:
        chromo (Chromosome): Chromosome to repair.
        all_courses (list[dict]): Course dataset.
        slots (list[tuple]): All available exam slots.
        slot_time_cache (dict): Slot -> (start_min, end_min).
        course_levels (dict): Course -> affected academic levels.
        conflict_map (dict): Course index -> conflicting course indices.
        venue_capacity (dict): Venue ID -> seating capacity.
    """
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


def genetic_algorithm(
        generations: int, pop_size: int, all_courses: list[dict],
        slots: list[tuple], slot_time_cache: dict, course_levels: dict,
        conflict_map: dict, course_list: list[int], venue_capacity: dict) -> Chromosome:
    """
    Run the genetic algorithm to generate an optimized exam timetable.

    The algorithm evolves a population of candidate solutions over
    multiple generations using:
    - Selection
    - Crossover
    - Mutation
    - Repair
    - Fitness-based survival

    Progress is reported interactively using Streamlit widgets.

    Args:
        generations (int): Number of evolutionary iterations.
        pop_size (int): Population size per generation.
        all_courses (list[dict]): Course dataset.
        slots (list[tuple]): All possible exam slots.
        slot_time_cache (dict): Slot -> (start_min, end_min).
        course_levels (dict): Course -> affected academic levels.
        conflict_map (dict): Course index -> conflicting course indices.
        course_list (list[int]): Ordered list of course indices.
        venue_capacity (dict): Venue ID -> seating capacity.

    Returns:
        Chromosome: Best chromosome (highest fitness) found.
    """
    population = generate_initial_population(
        pop_size, all_courses, slots,
        slot_time_cache, course_levels, conflict_map,
        course_list, venue_capacity
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
