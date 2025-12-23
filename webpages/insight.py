import streamlit as st

st.set_page_config(page_title="Exam Timetable Generator - Project Insight",
                   page_icon="🗣",
                   layout="wide")

st.header("Architecture of the project")

st.markdown("""
In this application, it is a constraint-aware, repair-based, real-world exam timetabling Genetic Algorithm (GA), 
The categories used align with standard academic timetabling models and they are:

"Hard constraints define feasibility and must be strictly satisfied, while soft constraints define quality and are minimized through penalty-based fitness evaluation."

---

A. **🔴 HARD CONSTRAINTS (Must never be violated)**

   Violating these makes a timetable invalid.    
   a) Exam time overlap (same dept + level)    
       - Two exams for same department & level cannot overlap    
       - Carryover courses extend this across multiple levels

   b) Unit-based duration constraint    
      - 1-unit ≠ 4-unit duration    
      - Prevents invalid exam lengths


B. **🟠 SOFT CONSTRAINTS (Should be minimized)**    
   
   These don’t invalidate the timetable, but reduce quality.    
   a) Short gap between exams    
       - Students shouldn’t write back-to-back exams    
       - Penalized but allowed

   b) Venue overcapacity    
        - Allows proportional overflow    
        - Penalized based on severity (This is realistic, not binary.)


C. **🔵 RESOURCE CONSTRAINTS (Physical limits)**

   Handled via "Venue Capacity" and "Venue Usage"    
   It ensures:    
        - Venues aren’t overloaded    
        - Capacity matters during mutation & repair


D. **🟢 SEARCH STABILITY & CONVERGENCE CONTROLS**

   These ensure the GA actually converges:

   a) Elitism: keeps best solutions intact.    
   b) Adaptive mutation: High exploration early and Fine-tuning later    
   c) Repair operator: Fixes broken chromosomes and prevents population collapse


""")
