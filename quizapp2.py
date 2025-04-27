import streamlit as st
import pandas as pd
import random
import datetime
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

# --- CONFIG ---
GRADE_START_RIT = {
    "Grade 6": 200,
    "Grade 7": 200,
    "Grade 8": 200,
    "Grade 9": 200,
    "Grade 10": 200
}

# --- DATABASE ---
engine = create_engine('sqlite:///quiz_results.db')

# --- LOAD CSVs ---
questions_df = pd.read_csv("questions.csv", skipinitialspace=True)
questions_df.columns = questions_df.columns.str.strip()

answers_df = pd.read_csv("anskey.csv", skipinitialspace=True)
answers_df.columns = answers_df.columns.str.strip()

correct_df = pd.read_csv("keys.csv", skipinitialspace=True)
correct_df.columns = correct_df.columns.str.strip()

# --- SESSION STATE ---
if "started" not in st.session_state:
    st.session_state.started = False
    st.session_state.username = ""
    st.session_state.grade = None
    st.session_state.starting_rit = None
    st.session_state.current_rit = None
    st.session_state.strands = []
    st.session_state.q_number = 0
    st.session_state.max_questions = 15
    st.session_state.finished = False
    st.session_state.rit_history = []
    st.session_state.questions_answered = []
    st.session_state.score_correct = 0
    st.session_state.current_question = None
    st.session_state.correct_answer = None
    st.session_state.submitted = False
    st.session_state.result_saved = False

# --- FUNCTIONS ---
def parse_rit_band(band):
    low, high = band.split("-")
    return int(low), int(high)

def select_question(current_rit, strands_selected):
    candidate_questions = []
    for index, row in questions_df.iterrows():
        low, high = parse_rit_band(row["RIT Band"])
        if row["Strand"] in strands_selected and low <= current_rit < high:
            candidate_questions.append(row)
    if candidate_questions:
        return random.choice(candidate_questions)
    else:
        return questions_df[questions_df["Strand"].isin(strands_selected)].sample().iloc[0]

def save_result():
    df = pd.DataFrame({
        "username": [st.session_state.username],
        "grade_level": [st.session_state.grade],
        "strands_selected": [",".join(st.session_state.strands)],
        "starting_rit": [st.session_state.starting_rit],
        "final_rit": [st.session_state.current_rit],
        "rit_history": [",".join(map(str, st.session_state.rit_history))],
        "questions_answered": [",".join(map(str, st.session_state.questions_answered))],
        "score_correct": [st.session_state.score_correct],
        "score_total": [st.session_state.max_questions],
        "timestamp": [datetime.datetime.now()]
    })
    df.to_sql('adaptive_results', con=engine, if_exists='append', index=False)

def reset_quiz():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.started = False

# --- STREAMLIT APP ---
st.title("🧠 Adaptive Math Growth Quiz")

if not st.session_state.started:
    st.header("Start New Test")

    st.session_state.username = st.text_input("Enter your name:")
    grade_selected = st.selectbox("Select your Grade Level:", list(GRADE_START_RIT.keys()))
    strands_selected = st.multiselect(
        "Select Math Strand(s) to focus on:",
        options=["Algebra", "Measurement", "Statistics", "Numbers"]
    )

    if st.button("Start Quiz"):
        if st.session_state.username and grade_selected and strands_selected:
            st.session_state.started = True
            st.session_state.grade = grade_selected
            st.session_state.starting_rit = GRADE_START_RIT[grade_selected]
            st.session_state.current_rit = GRADE_START_RIT[grade_selected]
            st.session_state.strands = strands_selected
        else:
            st.warning("⚠️ Please fill all selections before starting.")
else:
    if not st.session_state.finished:

        # --- Progress bar ---
        st.progress((st.session_state.q_number) / st.session_state.max_questions)

        # --- Load a question if none is loaded ---
        if st.session_state.current_question is None:
            question_row = select_question(st.session_state.current_rit, st.session_state.strands)
            st.session_state.current_question = question_row
            st.session_state.correct_answer = correct_df[correct_df['ID'] == question_row["ID"]]['CorrectAnswer'].values[0]
            st.session_state.submitted = False

        question_row = st.session_state.current_question
        qid = question_row["ID"]
        question_text = question_row["Question"]
        options_row = answers_df[answers_df['ID'] == qid].iloc[0]

        st.subheader(f"Question {st.session_state.q_number + 1} of {st.session_state.max_questions}")
        st.write(question_text)

        choices = options_row[1:].dropna().tolist()
        selected_text = st.radio("Choose your answer:", choices, key=f"q{st.session_state.q_number}")

        if not st.session_state.submitted:
            if st.button("Submit Answer"):
                st.session_state.questions_answered.append(qid)

                # --- Adaptive difficulty adjustment ---
                low, high = parse_rit_band(st.session_state.current_question["RIT Band"])
                current_rit = st.session_state.current_rit

                if high <= current_rit - 10:
                    difficulty = "easy"
                elif low <= current_rit <= high:
                    difficulty = "at_level"
                else:
                    difficulty = "hard"

                # Adjust RIT based on difficulty and answer correctness
                if selected_text == st.session_state.correct_answer:
                    if difficulty == "easy":
                        st.success("✅ Correct (Easy)!")
                        st.session_state.current_rit += 5
                    elif difficulty == "at_level":
                        st.success("✅ Correct (At-level)!")
                        st.session_state.current_rit += 10
                    else:
                        st.success("✅ Correct (Hard)!")
                        st.session_state.current_rit += 15
                    st.session_state.score_correct += 1
                else:
                    if difficulty == "easy":
                        st.error("❌ Incorrect (Easy)!")
                        st.session_state.current_rit -= 15
                    elif difficulty == "at_level":
                        st.error("❌ Incorrect (At-level)!")
                        st.session_state.current_rit -= 10
                    else:
                        st.error("❌ Incorrect (Hard)!")
                        st.session_state.current_rit -= 5

                st.session_state.rit_history.append(st.session_state.current_rit)
                st.session_state.submitted = True

        else:
            if st.button("Next Question ➡️"):
                st.session_state.q_number += 1
                st.session_state.current_question = None
                st.session_state.submitted = False

                if st.session_state.q_number >= st.session_state.max_questions:
                    st.session_state.finished = True

    else:
        st.success(f"🎉 Test completed! Final Estimated RIT Score: {st.session_state.current_rit}")

        # --- AUTOMATICALLY SAVE THE RESULT ---
        if not st.session_state.result_saved:
            save_result()
            st.session_state.result_saved = True
            st.success("✅ Result has been automatically saved!")

        # --- SHOW RIT Progress Chart ---
        st.subheader("📈 Your RIT Progress During the Test")
        fig, ax = plt.subplots()
        ax.plot(range(1, len(st.session_state.rit_history)+1), st.session_state.rit_history, marker='o', linestyle='-')
        ax.set_xlabel("Question Number")
        ax.set_ylabel("Estimated RIT Score")
        ax.set_title("RIT Growth Throughout the Quiz")
        ax.grid(True)
        st.pyplot(fig)

        if st.button("Restart Quiz"):
            reset_quiz()
            st.rerun()
