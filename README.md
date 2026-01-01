# Genetic Algorithm Exam Timetable

---

This application helps you generate an optimized exam timetable for multiple departments using a genetic algorithm
with well defined constraint categories.

---

### 🧬 How It Works

1. **Upload Data**  
   Upload CSV files for each department, carryover courses and venue using the sidebar.

2. **Configure Exam Weeks**  
   Select the number of exam weeks (each week is Monday–Friday).

3. **Configure Venue**   
   Select the number of venues available.

4. **Generate Timetable**  
   Click **Generate Timetable** to start the optimization. The algorithm will:
   - Assign all exams to available time slots (09:00–17:45)
   - Avoid hard conflicts (no overlapping exams for the same department and level, including carryovers)
   - Minimize soft conflicts (exams scheduled with less than 30 minutes gap)
   - Handle different exam durations based on course units
   - Handle venue overcapacity

5. **Review & Download**  
   - View the generated timetable in a pivoted table format
   - Download the full timetable or department-specific timetables as CSV
   - See summary statistics and conflict interpretation

---

# Clone the project and Deployment


## Part 1: Forking a Repository
### Step 1: Fork on GitHub Website

1. Navigate to the original repository on GitHub that you want to fork 
2. Click the "Fork" button in the top-right corner of the repository page 
3. Select your personal GitHub account as the destination 
4. Wait for GitHub to create your copy of the repository

### Step 2: Clone Your Fork Locally
```git
# Clone your forked repository to local machine
git clone https://github.com/<replace with YOUR-USERNAME>/<replace with REPOSITORY-NAME>.git

# Navigate into the project directory
cd REPOSITORY-NAME
```

### Step 3: Test Locally Before Deployment
```shell
# Install dependencies
pip install -r requirements.txt

# Run the app locally
streamlit run pagination.py

# Or run on a specific port
streamlit run pagination.py --server.port 8502
```