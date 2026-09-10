import streamlit as st
import pandas as pd
import qrcode
import hashlib
import time
import os
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Attendance Portal", page_icon="🎓", layout="wide")

STUDENTS_FILE = "students.csv"
ATTENDANCE_FILE = "attendance.csv"
SECRET_KEY = "my_college_secure_salt"

# ⏱️ UPDATED: Token valid for 5 Minutes (300 Seconds)
TOKEN_EXPIRY_SECONDS = 300  
TEACHER_PASSWORD = "admin123"

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

# --- FILE INITIALIZATION ---
if not os.path.exists(STUDENTS_FILE):
    df_init = pd.DataFrame([
        {"RollNo": "101", "Name": "Aarav Sharma"},
        {"RollNo": "102", "Name": "Ananya Verma"},
        {"RollNo": "103", "Name": "Rohan Mehta"}
    ])
    df_init.to_csv(STUDENTS_FILE, index=False)

if not os.path.exists(ATTENDANCE_FILE):
    df_att = pd.DataFrame(columns=["Date", "Time", "Subject", "RollNo", "Name", "Status"])
    df_att.to_csv(ATTENDANCE_FILE, index=False)

df_students = pd.read_csv(STUDENTS_FILE)
df_students['RollNo'] = df_students['RollNo'].astype(str)

# --- HELPER FUNCTIONS ---
def get_current_token(time_step=TOKEN_EXPIRY_SECONDS):
    current_slot = int(time.time() // time_step)
    raw_string = f"{SECRET_KEY}_{current_slot}"
    return hashlib.md5(raw_string.encode()).hexdigest()[:8]

def verify_token(scanned_token, time_step=TOKEN_EXPIRY_SECONDS):
    current_slot = int(time.time() // time_step)
    # Allows current 5-min window and previous 5-min window for slight clock differences
    valid_tokens = [
        hashlib.md5(f"{SECRET_KEY}_{current_slot}".encode()).hexdigest()[:8],
        hashlib.md5(f"{SECRET_KEY}_{current_slot - 1}".encode()).hexdigest()[:8]
    ]
    return scanned_token in valid_tokens

def get_public_url():
    try:
        headers = st.context.headers
        host = headers.get("Host", "")
        if host:
            protocol = "https" if "streamlit.app" in host else "http"
            return f"{protocol}://{host}"
    except Exception:
        pass
    return "http://localhost:8501"

# --- SESSION STATE FOR LOGIN ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["role"] = None
    st.session_state["student_roll"] = None
    st.session_state["student_name"] = None

st.title("🎓 Smart Attendance Portal")
url_token = st.query_params.get("token", None)

# --- 1. LOGIN SCREEN ---
if not st.session_state["logged_in"]:
    st.subheader("🔑 Please Log In")
    role = st.radio("Select Login Type:", ["Student", "Teacher"], horizontal=True)

    if role == "Student":
        roll_list = df_students["RollNo"].unique().tolist()
        selected_roll = st.selectbox("Select Your Roll Number:", roll_list)
        student_info = df_students[df_students["RollNo"] == selected_roll]
        
        if not student_info.empty:
            st.info(f"Welcome, **{student_info.iloc[0]['Name']}**")

        if st.button("Log In as Student"):
            st.session_state["logged_in"] = True
            st.session_state["role"] = "Student"
            st.session_state["student_roll"] = str(selected_roll)
            st.session_state["student_name"] = student_info.iloc[0]['Name']
            st.rerun()

    elif role == "Teacher":
        password = st.text_input("Enter Teacher Password:", type="password")
        if st.button("Log In as Teacher"):
            if password == TEACHER_PASSWORD:
                st.session_state["logged_in"] = True
                st.session_state["role"] = "Teacher"
                st.success("Authenticated!")
                st.rerun()
            else:
                st.error("Incorrect Password!")

# --- 2. LOGGED IN PORTAL ---
else:
    st.sidebar.markdown(f"**Logged in as:** {st.session_state['role']}")
    if st.session_state["role"] == "Student":
        st.sidebar.markdown(f"**Name:** {st.session_state['student_name']}")
        st.sidebar.markdown(f"**Roll No:** {st.session_state['student_roll']}")

    if st.sidebar.button("🚪 Log Out"):
        st.session_state["logged_in"] = False
        st.session_state["role"] = None
        st.session_state["student_roll"] = None
        st.session_state["student_name"] = None
        st.rerun()

    # --- STUDENT DASHBOARD ---
    if st.session_state["role"] == "Student":
        menu = st.sidebar.radio("Student Menu", ["📱 Mark Attendance (QR)", "📊 My Monthly Attendance %"])

        if menu == "📱 Mark Attendance (QR)":
            st.subheader("Mark Daily Class Attendance")

            if not url_token or not verify_token(url_token):
                st.error("🚨 INVALID OR EXPIRED QR CODE!")
                st.warning("This QR code has expired (valid for 5 minutes). Scan the active code on the classroom projector.")
            else:
                st.success("✅ QR Session Verified (5-Min Window Active)!")
                
                with st.form("student_mark_form"):
                    selected_subject = st.selectbox("Select Subject:", SUBJECTS)
                    submit = st.form_submit_button("✅ Submit Attendance")

                if submit:
                    today = datetime.now().strftime("%Y-%m-%d")
                    current_time = datetime.now().strftime("%H:%M:%S")

                    df_att = pd.read_csv(ATTENDANCE_FILE)
                    df_att['RollNo'] = df_att['RollNo'].astype(str)

                    existing = df_att[
                        (df_att['Date'] == today) & 
                        (df_att['Subject'] == selected_subject) & 
                        (df_att['RollNo'] == st.session_state['student_roll'])
                    ]

                    if not existing.empty:
                        st.warning(f"⚠️ You have already marked attendance for '{selected_subject}' today!")
                    else:
                        new_entry = pd.DataFrame([{
                            "Date": today,
                            "Time": current_time,
                            "Subject": selected_subject,
                            "RollNo": st.session_state['student_roll'],
                            "Name": st.session_state['student_name'],
                            "Status": "Present"
                        }])
                        new_entry.to_csv(ATTENDANCE_FILE, mode='a', header=False, index=False)
                        st.success(f"🎉 Marked Present for {selected_subject} at {current_time}!")
                        st.balloons()

        elif menu == "📊 My Monthly Attendance %":
            st.subheader(f"Attendance Report: {st.session_state['student_name']} (Roll: {st.session_state['student_roll']})")
            
            df_att = pd.read_csv(ATTENDANCE_FILE)
            if not df_att.empty:
                df_att['RollNo'] = df_att['RollNo'].astype(str)
                df_att['Date'] = pd.to_datetime(df_att['Date'])
                
                my_records = df_att[df_att['RollNo'] == st.session_state['student_roll']].copy()
                
                if my_records.empty:
                    st.info("No attendance records found for your roll number yet.")
                else:
                    my_records['Month'] = my_records['Date'].dt.strftime('%B %Y')
                    available_months = my_records['Month'].unique().tolist()
                    
                    selected_month = st.selectbox("Select Month:", available_months)
                    monthly_data = my_records[my_records['Month'] == selected_month]

                    st.markdown(f"### Monthly Summary - {selected_month}")
                    
                    report_data = []
                    for subject in SUBJECTS:
                        subject_records = monthly_data[monthly_data['Subject'] == subject]
                        attended_count = len(subject_records)
                        conducted_count = 8 
                        perc = round((attended_count / conducted_count) * 100, 1) if conducted_count > 0 else 0
                        
                        report_data.append({
                            "Subject": subject,
                            "Lectures Attended": attended_count,
                            "Estimated Conducted": conducted_count,
                            "Attendance %": f"{perc}%",
                            "Status": "✅ Regular" if perc >= 75 else "🚨 Below Target (<75%)"
                        })
                    
                    st.table(pd.DataFrame(report_data))
            else:
                st.info("No attendance records exist in the system yet.")

    # --- TEACHER DASHBOARD ---
    elif st.session_state["role"] == "Teacher":
        t_menu = st.sidebar.radio("Teacher Menu", ["📺 Classroom Projector (Live QR)", "📊 Full Class Reports & Defaulters"])

        if t_menu == "📺 Classroom Projector (Live QR)":
            st.subheader("📺 Classroom Projector Display")
            st.caption("Project this screen on the board. The QR code automatically expires every 5 minutes.")

            base_url = get_public_url()
            current_token = get_current_token()
            dynamic_url = f"{base_url}/?token={current_token}"

            # Calculate remaining time in current 5-minute window
            seconds_remaining = TOKEN_EXPIRY_SECONDS - (int(time.time()) % TOKEN_EXPIRY_SECONDS)
            mins_left = seconds_remaining // 60
            secs_left = seconds_remaining % 60

            # Generate QR image
            qr = qrcode.QRCode(box_size=10, border=3)
            qr.add_data(dynamic_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(qr_img, caption=f"Active Token: {current_token}", width=280)
            
            with col2:
                st.markdown(f"""
                ### ⏱️ 5-Minute Timed Session
                * **Time Remaining for Current QR:** `{mins_left}m {secs_left}s`
                * **Active Link:** `{dynamic_url}`
                * **Anti-Proxy Rule:** Screenshots shared after 5 minutes will be rejected automatically.
                """)
                
                if st.button("🔄 Force Refresh / Generate New QR"):
                    st.rerun()

        elif t_menu == "📊 Full Class Reports & Defaulters":
            st.subheader("👨‍🏫 Teacher Analytics & Defaulters (<75%)")
            
            df_att = pd.read_csv(ATTENDANCE_FILE)
            if not df_att.empty:
                df_att['RollNo'] = df_att['RollNo'].astype(str)
                selected_subject = st.selectbox("Select Subject:", SUBJECTS)
                total_conducted = st.number_input(f"Total Conducted Lectures for '{selected_subject}':", min_value=1, value=10)

                subj_att = df_att[df_att['Subject'] == selected_subject]
                counts = subj_att.groupby('RollNo')['Date'].nunique().reset_index()
                counts.columns = ['RollNo', 'Attended']
                counts['RollNo'] = counts['RollNo'].astype(str)

                report = pd.merge(df_students, counts, on='RollNo', how='left').fillna(0)
                report['Attendance %'] = round((report['Attended'] / total_conducted) * 100, 1)
                report['Status'] = report['Attendance %'].apply(lambda x: "🚨 DEFAULTER" if x < 75 else "✅ Regular")

                st.dataframe(report[['RollNo', 'Name', 'Attended', 'Attendance %', 'Status']], use_container_width=True)

                defaulters = report[report['Attendance %'] < 75]
                st.write("---")
                st.subheader("🚨 Defaulter List (<75%)")
                if not defaulters.empty:
                    st.error(f"Found {len(defaulters)} defaulter student(s):")
                    st.table(defaulters[['RollNo', 'Name', 'Attended', 'Attendance %']])
                else:
                    st.success("🎉 All students meet or exceed the 75% attendance criteria!")
            else:
                st.info("No attendance records logged yet.")