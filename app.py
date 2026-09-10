import streamlit as st
import pandas as pd
import qrcode
import hashlib
import time
import os
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="Anti-Proxy QR Attendance Portal", page_icon="🔒", layout="wide")

STUDENTS_FILE = "students.csv"
ATTENDANCE_FILE = "attendance.csv"
SECRET_KEY = "my_college_secure_salt"
TOKEN_EXPIRY_SECONDS = 15

SUBJECTS = [
    "Database Management System",
    "Indian Knowledge System",
    "Communication and Business Skills",
    "Environmental Studies",
    "AI Tools and Prompt Engineering",
    "Introduction to Python",
    "Introduction to AI",
    "Practical - Data Handling with SQL",
    "Practical - Introduction to Python Programming"
]

# --- 1. FILE INITIALIZATION ---
if not os.path.exists(STUDENTS_FILE):
    df_init = pd.DataFrame([
        {"RollNo": "101", "Name": "Aarav Sharma"},
        {"RollNo": "102", "Name": "Ananya Verma"},
        {"RollNo": "103", "Name": "Rohan Mehta"},
        {"RollNo": "104", "Name": "Sanya Kapoor"}
    ])
    df_init.to_csv(STUDENTS_FILE, index=False)

if not os.path.exists(ATTENDANCE_FILE):
    df_att = pd.DataFrame(columns=["Date", "Time", "Subject", "RollNo", "Name", "Status"])
    df_att.to_csv(ATTENDANCE_FILE, index=False)

# --- 2. SECURITY TOKEN FUNCTIONS ---
def get_current_token(time_step=TOKEN_EXPIRY_SECONDS):
    current_slot = int(time.time() // time_step)
    raw_string = f"{SECRET_KEY}_{current_slot}"
    return hashlib.md5(raw_string.encode()).hexdigest()[:8]

def verify_token(scanned_token, time_step=TOKEN_EXPIRY_SECONDS):
    current_slot = int(time.time() // time_step)
    valid_tokens = [
        hashlib.md5(f"{SECRET_KEY}_{current_slot}".encode()).hexdigest()[:8],
        hashlib.md5(f"{SECRET_KEY}_{current_slot - 1}".encode()).hexdigest()[:8]
    ]
    return scanned_token in valid_tokens

# --- 3. NAVIGATION MENU ---
st.title("🔒 Anti-Proxy QR Attendance Portal")
menu = st.sidebar.radio("Navigation", ["📱 Student Check-In", "📺 Live Dynamic QR (Classroom)", "👨‍🏫 Teacher Dashboard"])

# --- TAB 1: STUDENT CHECK-IN ---
if menu == "📱 Student Check-In":
    st.subheader("Mark Daily Attendance")
    
    # Read token parameter from URL
    scanned_token = st.query_params.get("token", None)

    if not scanned_token or not verify_token(scanned_token):
        st.error("🚨 INVALID OR EXPIRED QR CODE!")
        st.warning("Anti-Proxy Lock: Screenshots expire after 15 seconds. Please scan the live QR code projected on the classroom screen.")
    else:
        st.success("✅ Live Classroom Session Verified!")
        
        df_students = pd.read_csv(STUDENTS_FILE)
        df_attendance = pd.read_csv(ATTENDANCE_FILE)

        with st.form("attendance_form"):
            selected_subject = st.selectbox("1. Select Subject:", SUBJECTS)
            selected_roll = st.selectbox("2. Select Your Roll Number:", df_students['RollNo'].unique())
            
            student_name = df_students[df_students['RollNo'] == selected_roll]['Name'].values[0]
            st.write(f"**Student Name:** {student_name}")

            submit = st.form_submit_button("✅ Mark Present")

        if submit:
            today = datetime.now().strftime("%Y-%m-%d")
            current_time = datetime.now().strftime("%H:%M:%S")

            # Check if already marked present
            already_marked = False
            if not df_attendance.empty:
                existing = df_attendance[
                    (df_attendance['Date'] == today) & 
                    (df_attendance['Subject'] == selected_subject) & 
                    (df_attendance['RollNo'] == str(selected_roll))
                ]
                if not existing.empty:
                    already_marked = True

            if already_marked:
                st.warning(f"⚠️ {student_name}, you have already marked attendance for '{selected_subject}' today!")
            else:
                new_entry = pd.DataFrame([{
                    "Date": today,
                    "Time": current_time,
                    "Subject": selected_subject,
                    "RollNo": str(selected_roll),
                    "Name": student_name,
                    "Status": "Present"
                }])
                new_entry.to_csv(ATTENDANCE_FILE, mode='a', header=False, index=False)
                st.success(f"🎉 Marked Present for '{selected_subject}' at {current_time}.")
                st.balloons()

# --- TAB 2: LIVE DYNAMIC QR DISPLAY ---
elif menu == "📺 Live Dynamic QR (Classroom)":
    st.subheader("📺 Classroom Projector Screen")
    st.caption("Project this screen in class. The QR code automatically updates with a new security token.")

    # Local IP or Host address
    base_url = "http://localhost:8501" 
    
    current_token = get_current_token()
    dynamic_url = f"{base_url}/?token={current_token}"

    # Generate QR Code Image directly
    qr = qrcode.QRCode(box_size=10, border=3)
    qr.add_data(dynamic_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    col1, col2 = st.columns([1, 2])
    with col1:
        # Display image directly
        st.image(qr_img, caption=f"Active Token: {current_token}", width=280)
    
    with col2:
        st.markdown(f"""
        ### 🛡️ Anti-Proxy System Active
        * **Token Refresh Window:** 15 seconds
        * **Security Link:** `{dynamic_url}`
        * **Proxy Defense:** Screenshots sent over WhatsApp or social media will expire before an absent student can scan them.
        """)
        
        if st.button("🔄 Refresh QR Token"):
            st.rerun()

# --- TAB 3: TEACHER DASHBOARD ---
elif menu == "👨‍🏫 Teacher Dashboard":
    st.subheader("Attendance Reports & Defaulter List (<75%)")
    df_attendance = pd.read_csv(ATTENDANCE_FILE)
    df_students = pd.read_csv(STUDENTS_FILE)

    if not df_attendance.empty:
        selected_subject = st.selectbox("Select Subject:", SUBJECTS)
        total_conducted = st.number_input(f"Total Lectures Conducted for '{selected_subject}':", min_value=1, value=10)

        subj_attendance = df_attendance[df_attendance['Subject'] == selected_subject]
        counts = subj_attendance.groupby('RollNo')['Date'].nunique().reset_index()
        counts.columns = ['RollNo', 'Attended']
        counts['RollNo'] = counts['RollNo'].astype(str)

        df_students['RollNo'] = df_students['RollNo'].astype(str)
        report = pd.merge(df_students, counts, on='RollNo', how='left').fillna(0)
        report['Attendance %'] = (report['Attended'] / total_conducted) * 100
        report['Status'] = report['Attendance %'].apply(lambda x: "🚨 DEFAULTER" if x < 75 else "✅ Regular")

        st.dataframe(report, use_container_width=True)

        defaulters = report[report['Attendance %'] < 75]
        st.write("---")
        st.subheader("🚨 Defaulter Summary (<75%)")
        if not defaulters.empty:
            st.error(f"Found {len(defaulters)} defaulter student(s) for '{selected_subject}':")
            st.table(defaulters[['RollNo', 'Name', 'Attended', 'Attendance %']])
        else:
            st.success("🎉 No defaulters! All students are at or above 75%.")
    else:
        st.info("No attendance entries recorded yet.")