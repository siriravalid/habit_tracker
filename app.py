import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import requests
from openpyxl import Workbook, load_workbook

# Load environment variables
load_dotenv()
GROK_API_KEY = os.getenv("GROK_API_KEY")

# Constants
FILE_NAME = "habit_tracker.xlsx"

# --- Helper Functions ---

def load_data():
    if not os.path.exists(FILE_NAME):
        # Create empty DataFrame with Date column and core habits
        core_habits = ["exercise", "study", "work", "cooking", "reading", "sleep", "maintenance"]
        columns = ["Date"] + core_habits
        df = pd.DataFrame(columns=columns)
        df.to_excel(FILE_NAME, index=False)
        return df
    
    # Load existing data
    df = pd.read_excel(FILE_NAME)
    # Ensure Date column exists
    if "Date" not in df.columns:
        df["Date"] = pd.NA
    
    # Ensure only core habits exist
    core_habits = ["exercise", "study", "work", "cooking", "reading", "sleep", "maintenance"]
    columns_to_keep = ["Date"] + core_habits
    current_columns = df.columns.tolist()
    
    # Add missing core habits
    for habit in core_habits:
        if habit not in current_columns:
            df[habit] = "No"
    
    # Remove any non-core habits
    for col in current_columns:
        if col not in columns_to_keep:
            df = df.drop(columns=[col])
    
    return df

def save_data(df):
    # Ensure Date column exists and is first
    if "Date" not in df.columns:
        df.insert(0, "Date", pd.NA)
    else:
        # Move Date column to first position if not already there
        date_col = df.pop("Date")
        df.insert(0, "Date", date_col)
    
    # Save the DataFrame to Excel
    df.to_excel(FILE_NAME, index=False)

def extract_habits(text):
    # Core habits with simple variations
    habit_patterns = {
        "exercise": ["exercise", "workout", "walked", "ran", "jogged", "gym"],
        "study": ["study", "studied", "learning", "read", "reading", "papers"],
        "work": ["work", "coding", "emails", "meeting", "presentation"],
        "cooking": ["cook", "cooked", "food", "lunch", "grocery", "shopping"],
        "reading": ["read", "reading", "novel", "studied", "papers"],
        "sleep": ["sleep", "slept", "woke", "hours"],
        "maintenance": ["clean", "laundry", "cleaned", "apartment"]
    }
    
    detected = set()
    text_lower = text.lower()
    
    # Check for exact matches
    for habit, patterns in habit_patterns.items():
        if any(pattern in text_lower for pattern in patterns):
            detected.add(habit)
    
    return list(detected)

def update_sheet(df, habits_today, today):
    # Convert today to string format
    if isinstance(today, str):
        today_str = today
    else:
        today_str = today.strftime("%Y-%m-%d")
    
    # Ensure we only use core habits
    core_habits = ["exercise", "study", "work", "cooking", "reading", "sleep", "maintenance"]
    
    # Check if today's entry exists
    if today_str in df["Date"].astype(str).values:
        # Get the existing row
        existing_row = df[df["Date"].astype(str) == today_str].iloc[0]
        
        # Create new row with existing values
        row = existing_row.to_dict()
        
        # Update habits to Yes if they were detected
        for habit in habits_today:
            if habit in core_habits:
                row[habit] = "Yes"
    else:
        # Create new row for today
        row = {"Date": today_str}
        # Set detected habits to Yes
        for habit in habits_today:
            if habit in core_habits:
                row[habit] = "Yes"
        # Set remaining core habits to No
        for habit in core_habits:
            if habit not in row:
                row[habit] = "No"
    
    # Remove any existing entry for today
    df = df[df["Date"].astype(str) != today_str]
    
    # Add the updated/created row
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df

def analyze_period(df, period="week"):
    if period == "week":
        # Get the start date of the current week (Monday)
        today = datetime.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    else:  # month
        # Get the start and end dates of the current month
        today = datetime.today()
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year+1, month=1, day=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month+1, day=1) - timedelta(days=1)
    
    # Convert Date column to datetime
    df["Date"] = pd.to_datetime(df["Date"])
    
    # Filter data for the selected period
    mask = (df["Date"] >= start) & (df["Date"] <= end)
    df_period = df[mask]
    
    # Core habits we want to track
    core_habits = ["exercise", "study", "work", "cooking", "reading", "sleep", "maintenance"]
    
    # Initialize counts for core habits
    habit_counts = {habit: 0 for habit in core_habits}
    
    # Count only core habits
    for _, row in df_period.iterrows():
        for habit in core_habits:
            if habit in row and row[habit].lower() == "yes":
                habit_counts[habit] += 1
    
    # Create a Series with counts and add total days for context
    result = pd.Series(habit_counts)
    result["Total Days in Period"] = len(df_period)
    
    return result

def grok_feedback(user_text):
    # Return a basic feedback since Grok API is not accessible
    feedback = "Here are some observations and suggestions based on your daily log:\n"
    
    # Positive activities
    if "exercise" in user_text.lower() or "workout" in user_text.lower():
        feedback += "- Great job staying active! Exercise is fantastic for both physical and mental health.\n"
    if "reading" in user_text.lower() or "studied" in user_text.lower():
        feedback += "- Good job on the learning! Keep nurturing your mind with new knowledge.\n"
    if "cleaning" in user_text.lower() or "organized" in user_text.lower():
        feedback += "- Great work on keeping your space tidy! A clean environment promotes better focus and well-being.\n"
    if "podcast" in user_text.lower() or "learned" in user_text.lower():
        feedback += "- Good job on continuous learning! Mental health education is especially valuable.\n"
    
    # Areas for improvement
    if "overslept" in user_text.lower() or "missed" in user_text.lower() and "morning" in user_text.lower():
        feedback += "- Consider setting a consistent wake-up time to improve your morning routine.\n"
    if "fast food" in user_text.lower() or "junk" in user_text.lower():
        feedback += "- Try to include more nutritious meals in your diet. Your body will thank you!\n"
    if "didn't feel great" in user_text.lower() or "bad" in user_text.lower():
        feedback += "- Pay attention to how food affects your mood and energy levels.\n"
    if "emails" in user_text.lower() or "organizing" in user_text.lower():
        feedback += "- Good job on staying organized! Maintaining a clear workspace helps reduce stress.\n"
    
    # General health tips
    if "mental health" in user_text.lower():
        feedback += "- Taking care of your mental health is essential. Keep it up!\n"
    if "cleaning" in user_text.lower() or "organized" in user_text.lower():
        feedback += "- Maintaining a clean environment can boost your mood and productivity.\n"
    
    # If no specific activities were found
    if feedback == "Here are some observations and suggestions based on your daily log:\n":
        feedback += "- Keep up the good work! Every day is a chance to make positive choices.\n"
    
    return feedback.strip()

def show_chart(counts, title):
    st.subheader(title)
    fig, ax = plt.subplots()
    counts.plot(kind="bar", ax=ax)
    ax.set_ylabel("Times Done")
    ax.set_title(title)
    st.pyplot(fig)

# --- Streamlit UI ---

st.title("Smart Habit Tracker with NLP + Visualization")

# Date selection
selected_date = st.date_input("Select a date", datetime.today())
selected_date_str = selected_date.strftime("%Y-%m-%d")

st.markdown("Enter a short note about your day (e.g. *I exercised, read, and spent time on social media*)")

user_text = st.text_area("Your Daily Log", height=150)

if st.button("Log Habits"):
    if user_text.strip() == "":
        st.warning("Please enter some text first.")
    else:
        data = load_data()
        habits = extract_habits(user_text)
        new_data = update_sheet(data, habits, selected_date_str)
        save_data(new_data)
        st.success(f"Logged for {selected_date_str}")
        st.write("✅ Habits Detected:", habits)
        st.markdown("### 🤖 Grok's Smart Suggestion")
        st.info(grok_feedback(user_text))

# --- Analysis Section ---

st.markdown("---")
st.subheader("📊 Analyze Your Progress")

if st.button("Analyze My Week"):
    data = load_data()
    weekly = analyze_period(data, "week")
    st.write("✅ Weekly Habit Counts")
    st.write(weekly)
    show_chart(weekly, "This Week's Habits")

if st.button("Analyze My Month"):
    data = load_data()
    monthly = analyze_period(data, "month")
    st.write("✅ Monthly Habit Counts")
    st.write(monthly)
    show_chart(monthly, "This Month's Habits")

# --- Download Section ---

st.markdown("---")
st.subheader("📥 Download Your Tracker")

if not os.path.exists(FILE_NAME):
    # Create empty workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Date"])  # Add header
    wb.save(FILE_NAME)
    st.success("Created new habit tracker file!")

with open(FILE_NAME, "rb") as file:
    st.download_button(label="Download Excel File", data=file, file_name="habit_tracker.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
