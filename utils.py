import random
import os
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import base64


def open_picture(image_name):
    cwd = os.path.dirname(__file__)
    image_path = os.path.join(cwd, "image", image_name)
    image_path = os.path.abspath(image_path)
    file = open(image_path, "rb")
    images = base64.b64encode(file.read()).decode()
    return images


def time_to_minutes(t):
    """
        Converts a time string in 'HH:MM' format to the total number of minutes.

        Args:
            t (str): Time string in 'HH:MM' format.

        Returns:
            int: Total minutes.
        """
    h, m = map(int, t.split(":"))
    return h * 60 + m


def get_time_slots(units):
    """
    Returns a list of available time slots based on the number of units.

    Args:
        units (int): The number of units for the course.

    Returns:
        list: A list of tuples, each representing a start and end time in 'HH:MM' format.
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
    Represents a candidate solution (chromosome) for the timetable scheduling problem.

    Attributes:
        assignments (dict): Mapping of course indices to assigned time slots.
        fitness (float or None): Fitness score of the chromosome.
        hard_conflicts (int): Number of hard conflicts in the timetable.
        soft_conflicts (int): Number of soft conflicts in the timetable.
    """
    def __init__(self, assignments):
        """
        Initializes a Chromosome instance with course assignments.

        Args:
            assignments (dict): Mapping of course indices to assigned time slots.
        """
        self.assignments = assignments
        self.fitness = None
        self.hard_conflicts = 0
        self.soft_conflicts = 0

    def calculate_fitness(self, all_courses, slot_time_cache, course_levels):
        """
        Calculates the fitness score for the chromosome based on scheduling constraints.

        Args:
            all_courses (pd.DataFrame): DataFrame containing all course information.
            slot_time_cache (dict): Mapping of time slots to their start and end times in minutes.
            course_levels (dict): Mapping of course names to their levels.

        Returns:
            float: The calculated fitness score (negative penalty).
        """
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


def is_slot_conflict(idx, slot, assignments, slot_time_cache, conflict_map):
    """
    Checks if assigning a given slot to a course index causes a conflict with already assigned courses.

    Args:
        idx (int): Index of the course to check.
        slot (tuple): The time slot to assign.
        assignments (dict): Current assignments of courses to slots.
        slot_time_cache (dict): Mapping of slots to their start and end times in minutes.
        conflict_map (dict): Mapping of course indices to conflicting course indices.

    Returns:
        bool: True if there is a conflict, False otherwise.
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


def generate_initial_population(pop_size, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list):
    """
    Generates the initial population of chromosomes for the genetic algorithm.

    Args:
        pop_size (int): Number of chromosomes to generate.
        all_courses (pd.DataFrame): DataFrame containing all course information.
        slots (list): List of available time slots.
        slot_time_cache (dict): Mapping of slots to their start and end times in minutes.
        course_levels (dict): Mapping of course names to their levels.
        conflict_map (dict): Mapping of course indices to conflicting course indices.
        course_list (list): List of course indices to schedule.

    Returns:
        list: List of Chromosome instances representing the initial population.
    """
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
                    if not is_slot_conflict(idx, slot, assignments, slot_time_cache, conflict_map):
                        assignments[idx] = slot
                        break
                else:
                    assignments[idx] = random.choice(possible_slots)
        chromo = Chromosome(assignments)
        population.append(chromo)
    calculate_population_fitness(population, all_courses, slot_time_cache, course_levels)
    return population


def calculate_population_fitness(population, all_courses, slot_time_cache, course_levels):
    """
    Calculates the fitness for each chromosome in the population in parallel.

    Args:
        population (list): List of Chromosome instances.
        all_courses (pd.DataFrame): DataFrame containing all course information.
        slot_time_cache (dict): Mapping of slots to their start and end times in minutes.
        course_levels (dict): Mapping of course names to their levels.

    Returns:
        None
    """
    with ThreadPoolExecutor(max_workers=max(2, os.cpu_count() // 2)) as executor:
        list(executor.map(lambda c: c.calculate_fitness(all_courses, slot_time_cache, course_levels), population))


def crossover(parent1, parent2, course_list):
    """
    Performs crossover between two parent chromosomes to produce a child chromosome.

    Args:
        parent1 (Chromosome): The first parent chromosome.
        parent2 (Chromosome): The second parent chromosome.
        course_list (list): List of course indices to schedule.

    Returns:
        Chromosome: A new child chromosome with mixed assignments from both parents.
    """
    assignments = {}
    for idx in course_list:
        assignments[idx] = parent1.assignments[idx] if random.random() < 0.5 else parent2.assignments[idx]
    return Chromosome(assignments)


def mutate(chromo, mutation_rate, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list):
    """
    Mutates a chromosome by randomly reassigning time slots to courses based on the mutation rate.

    Args:
        chromo (Chromosome): The chromosome to mutate.
        mutation_rate (float): Probability of mutating each course assignment.
        all_courses (pd.DataFrame): DataFrame containing all course information.
        slots (list): List of available time slots.
        slot_time_cache (dict): Mapping of slots to their start and end times in minutes.
        course_levels (dict): Mapping of course names to their levels.
        conflict_map (dict): Mapping of course indices to conflicting course indices.
        course_list (list): List of course indices to schedule.

    Returns:
        None
    """
    for idx in course_list:
        if random.random() < mutation_rate:
            row = all_courses.loc[idx]
            units = row["units"]
            possible_slots = [s for s in slots if s[3] == units]
            random.shuffle(possible_slots)
            for slot in possible_slots:
                if not is_slot_conflict(idx, slot, chromo.assignments, slot_time_cache, conflict_map):
                    chromo.assignments[idx] = slot
                    break


def repair(chromo, all_courses, slots, slot_time_cache, course_levels, conflict_map):
    """
    Repairs a chromosome by resolving hard conflicts in course assignments.

    Args:
        chromo (Chromosome): The chromosome to repair.
        all_courses (pd.DataFrame): DataFrame containing all course information.
        slots (list): List of available time slots.
        slot_time_cache (dict): Mapping of slots to their start and end times in minutes.
        course_levels (dict): Mapping of course names to their levels.
        conflict_map (dict): Mapping of course indices to conflicting course indices.

    Returns:
        None
    """
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
                    if not is_slot_conflict(idx, new_slot, chromo.assignments, slot_time_cache, conflict_map):
                        chromo.assignments[idx] = new_slot
                        break
    # Recalculate fitness after repair
    chromo.calculate_fitness(all_courses, slot_time_cache, course_levels)


def genetic_algorithm(
        generations, pop_size, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list, ):
    """
    Runs a genetic algorithm to generate an optimized timetable.

    Args:
        generations (int): Number of generations to run the algorithm.
        pop_size (int): Size of the population in each generation.
        all_courses (pd.DataFrame): DataFrame containing course information.
        slots (list): List of available time slots.
        slot_time_cache (dict): Mapping of slots to their start and end times in minutes.
        course_levels (dict): Mapping of course names to their levels.
        conflict_map (dict): Mapping of course indices to conflicting course indices.
        course_list (list): List of course indices to schedule.

    Returns:
        Chromosome: The best chromosome (timetable) found.
    """
    population = generate_initial_population(
        pop_size, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list
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
            mutate(child, mutation_rate, all_courses, slots, slot_time_cache, course_levels, conflict_map, course_list)
            repair(child, all_courses, slots, slot_time_cache, course_levels, conflict_map)
            next_gen.append(child)
        calculate_population_fitness(next_gen, all_courses, slot_time_cache, course_levels)
        population = next_gen
        progress_bar.progress((gen + 1) / generations)
        status_text.text(f"Generation {gen + 1}/{generations} | Best fitness: {population[0].fitness}")
    progress_bar.progress(1.0)
    st.success("✅ Timetable generation complete!")
    return population[0]
