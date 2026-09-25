import streamlit as st
import pandas as pd
import qrcode
import hashlib
import time
import os
from datetime import datetime
import zoneinfo
from streamlit_gsheets import GSheetsConnection

# --- TIMEZONE CONFIGURATION (IST) ---
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Attendance Portal", page_icon="🎓", layout="wide")

SECRET_KEY = "my_college_secure_salt"
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

# --- SHARED SERVER QR CONFIGURATION (Cross-Session Sync) ---
@st.cache_resource
def get_shared_qr_config():
    """Stores shared QR session parameters across all student and teacher logins."""
    return {
        "salt": 1000,
        "validity_mins": 10,
        "is_locked": False,
        "active_subject": SUBJECTS[0]  # Default subject
    }

# --- GOOGLE SHEETS & DATA HANDLING ---
@st.cache_resource
def get_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception:
        return None

conn = get_connection()

def sanitize_filename(name):
    """Sanitizes subject names for local fallback CSV saving"""
    return "".join([c if c.isalnum() else "_" for c in name])

def load_students():
    """Loads student list from Google Sheets or local fallback"""
    if conn:
        try:
            df = conn.read(worksheet="Students", ttl=0)
            if not df.empty and 'RollNo' in df.columns:
                df['RollNo'] = df['RollNo'].astype(str)
                return df
        except Exception:
            pass
    
    if os.path.exists("students.csv"):
        df = pd.read_csv("students.csv")
        df['RollNo'] = df['RollNo'].astype(str)
        return df
    return pd.DataFrame([{"RollNo": "101", "Name": "Aarav Sharma"}])

def save_students(df_new):
    """Saves student list permanently to Google Sheets and local backup"""
    df_new['RollNo'] = df_new['RollNo'].astype(str)
    df_new.to_csv("students.csv", index=False)
    if conn:
        try:
            conn.update(worksheet="Students", data=df_new)
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Error syncing with Google Sheets: {e}")

def load_subject_attendance(subject_name):
    """Loads attendance for a specific subject tab with strict deduplication"""
    df = pd.DataFrame(columns=["Date", "Time", "RollNo", "Name", "Status"])
    
    if conn:
        try:
            df_sheet = conn.read(worksheet=subject_name, ttl=0)
            if not df_sheet.empty and 'RollNo' in df_sheet.columns:
                df = df_sheet
        except Exception:
            pass
    
    if df.empty:
        local_file = f"attendance_{sanitize_filename(subject_name)}.csv"
        if os.path.exists(local_file):
            df = pd.read_csv(local_file)

    if not df.empty and 'RollNo' in df.columns:
        df['RollNo'] = df['RollNo'].astype(str)
        df = df.drop_duplicates(subset=['Date', 'RollNo'], keep='first')
        
    return df

def append_subject_attendance(subject_name, new_row_df):
    """Appends attendance cleanly with zero duplicates"""
    new_row_df['RollNo'] = new_row_df['RollNo'].astype(str)
    
    existing_df = load_subject_attendance(subject_name)
    combined_df = pd.concat([existing_df, new_row_df], ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset=['Date', 'RollNo'], keep='first')
    
    local_file = f"attendance_{sanitize_filename(subject_name)}.csv"
    combined_df.to_csv(local_file, index=False)
        
    if conn:
        try:
            conn.update(worksheet=subject_name, data=combined_df)
            st.cache_data.clear()
        except Exception as e:
            st.warning(f"Saved locally, but Google Sheets sync pending for {subject_name}: {e}")

def reset_subject_attendance(subject_name):
    """Erases all attendance records for a specific subject tab"""
    empty_df = pd.DataFrame(columns=["Date", "Time", "RollNo", "Name", "Status"])
    
    local_file = f"attendance_{sanitize_filename(subject_name)}.csv"
    empty_df.to_csv(local_file, index=False)
    
    if conn:
        try:
            conn.update(worksheet=subject_name, data=empty_df)
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Error resetting Google Sheets tab '{subject_name}': {e}")

# --- DYNAMIC TOKEN & SECURITY FUNCTIONS ---
def get_current_token():
    cfg = get_shared_qr_config()
    validity_seconds = cfg["validity_mins"] * 60
    salt = cfg["salt"]
    subj = cfg.get("active_subject", "")
    current_slot = int(time.time() // validity_seconds)
    raw_string = f"{SECRET_KEY}_{current_slot}_{salt}_{subj}"
    return hashlib.md5(raw_string.encode()).hexdigest()[:8]

def verify_token(scanned_token):
    cfg = get_shared_qr_config()
    
    if cfg["is_locked"]:
        return False, "🔒 Attendance session has been locked by the teacher.", None
        
    if not scanned_token:
        return False, "🚨 No attendance token provided.", None

    validity_seconds = cfg["validity_mins"] * 60
    salt = cfg["salt"]
    subj = cfg.get("active_subject", "")
    current_slot = int(time.time() // validity_seconds)
    
    valid_tokens = [
        hashlib.md5(f"{SECRET_KEY}_{current_slot}_{salt}_{subj}".encode()).hexdigest()[:8],
        hashlib.md5(f"{SECRET_KEY}_{current_slot - 1}_{salt}_{subj}".encode()).hexdigest()[:8]
    ]
    
    if scanned_token in valid_tokens:
        return True, f"✅ QR Session Verified for {subj}!", subj
    return False, "🚨 EXPIRED OR INVALID QR CODE! Scan the active code on the classroom board.", None

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

# --- SESSION STATE ---
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
        df_students = load_students()
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

            is_valid, msg, active_subject = verify_token(url_token)

            if not is_valid:
                st.error(msg)
            else:
                st.success(f"✅ Verified Active Session for: **{active_subject}**")
                
                with st.form("student_mark_form"):
                    # Locked Subject Field (Cannot be modified by student)
                    st.text_input("Active Lecture Subject:", value=active_subject, disabled=True)
                    submit = st.form_submit_button("✅ Submit Attendance")

                if submit:
                    now_ist = datetime.now(IST)
                    today = now_ist.strftime("%Y-%m-%d")
                    current_time = now_ist.strftime("%H:%M:%S")

                    df_att = load_subject_attendance(active_subject)

                    existing = df_att[
                        (df_att['Date'] == today) & 
                        (df_att['RollNo'] == st.session_state['student_roll'])
                    ]

                    if not existing.empty:
                        st.warning(f"⚠️ You have already marked attendance for '{active_subject}' today!")
                    else:
                        new_entry = pd.DataFrame([{
                            "Date": today,
                            "Time": current_time,
                            "RollNo": st.session_state['student_roll'],
                            "Name": st.session_state['student_name'],
                            "Status": "Present"
                        }])
                        append_subject_attendance(active_subject, new_entry)
                        st.success(f"🎉 Marked Present for {active_subject} at {current_time} (IST)!")
                        st.balloons()

        elif menu == "📊 My Monthly Attendance %":
            st.subheader(f"Attendance Report: {st.session_state['student_name']} (Roll: {st.session_state['student_roll']})")
            
            selected_subject = st.selectbox("Select Subject to View Report:", SUBJECTS)
            df_att = load_subject_attendance(selected_subject)
            
            if not df_att.empty:
                df_att['Date'] = pd.to_datetime(df_att['Date'])
                my_records = df_att[df_att['RollNo'] == st.session_state['student_roll']].copy()
                
                if my_records.empty:
                    st.info(f"No attendance records found for '{selected_subject}'.")
                else:
                    my_records['Month'] = my_records['Date'].dt.strftime('%B %Y')
                    available_months = my_records['Month'].unique().tolist()
                    
                    selected_month = st.selectbox("Select Month:", available_months)
                    monthly_data = my_records[my_records['Month'] == selected_month]

                    attended_count = len(monthly_data)
                    conducted_count = 8 
                    perc = round((attended_count / conducted_count) * 100, 1) if conducted_count > 0 else 0
                    
                    report_df = pd.DataFrame([{
                        "Subject": selected_subject,
                        "Lectures Attended": attended_count,
                        "Estimated Conducted": conducted_count,
                        "Attendance %": f"{perc}%",
                        "Status": "✅ Regular" if perc >= 75 else "🚨 Below Target (<75%)"
                    }])
                    
                    st.table(report_df)
            else:
                st.info(f"No attendance records exist for '{selected_subject}' yet.")

    # --- TEACHER DASHBOARD ---
    elif st.session_state["role"] == "Teacher":
        try:
            sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        except Exception:
            sheet_url = "https://sheets.google.com"

        st.sidebar.markdown("---")
        st.sidebar.link_button("🟢 Open Live Google Sheet", sheet_url)

        t_menu = st.sidebar.radio("Teacher Menu", [
            "📺 Classroom Projector (Live QR)", 
            "📊 Subject Reports & Defaulters",
            "📁 Upload Student Roster"
        ])

        if t_menu == "📺 Classroom Projector (Live QR)":
            st.subheader("📺 Classroom Projector Display")
            
            cfg = get_shared_qr_config()

            # --- TEACHER SUBJECT & SESSION CONTROLS ---
            current_subj = cfg.get("active_subject", SUBJECTS[0])
            selected_subject = st.selectbox(
                "📚 Select Current Subject for this Lecture:", 
                SUBJECTS, 
                index=SUBJECTS.index(current_subj) if current_subj in SUBJECTS else 0
            )
            
            if selected_subject != current_subj:
                cfg["active_subject"] = selected_subject
                cfg["salt"] += 1  # Generate a new token when subject changes
                st.rerun()

            st.write("---")

            ctrl_col1, ctrl_col2, ctrl_col3 = st.columns(3)
            with ctrl_col1:
                selected_validity = st.selectbox(
                    "⏱️ QR Validity Duration:", 
                    [3, 5, 10, 15], 
                    index=[3, 5, 10, 15].index(cfg["validity_mins"])
                )
                if selected_validity != cfg["validity_mins"]:
                    cfg["validity_mins"] = selected_validity
                    st.rerun()

            with ctrl_col2:
                st.write("")
                st.write("")
                if st.button("🔄 Force Refresh / Generate New QR"):
                    cfg["salt"] += 1
                    cfg["is_locked"] = False
                    st.success("New QR Generated!")
                    st.rerun()

            with ctrl_col3:
                st.write("")
                st.write("")
                if cfg["is_locked"]:
                    if st.button("🔓 Unlock Attendance Session"):
                        cfg["is_locked"] = False
                        st.rerun()
                else:
                    if st.button("🔒 Lock / End Attendance Session"):
                        cfg["is_locked"] = True
                        st.rerun()

            st.write("---")

            if cfg["is_locked"]:
                st.error("🔒 ATTENDANCE SESSION IS LOCKED. Students cannot mark attendance currently.")
            else:
                base_url = get_public_url()
                current_token = get_current_token()
                dynamic_url = f"{base_url}/?token={current_token}"

                validity_seconds = cfg["validity_mins"] * 60
                seconds_remaining = validity_seconds - (int(time.time()) % validity_seconds)
                mins_left = seconds_remaining // 60
                secs_left = seconds_remaining % 60

                qr = qrcode.QRCode(box_size=10, border=3)
                qr.add_data(dynamic_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(qr_img, caption=f"Active Token: {current_token}", width=280)
                
                with col2:
                    st.markdown(f"""
                    ### ⏱️ Active Timed Session
                    * **Active Subject:** `{cfg['active_subject']}`
                    * **QR Expiry Window:** `{cfg['validity_mins']} Minutes`
                    * **Time Remaining for Current QR:** `{mins_left}m {secs_left}s`
                    * **Active Link:** `{dynamic_url}`
                    * **Anti-Proxy Rule:** The QR token is cryptographically bound to **{cfg['active_subject']}**. Students cannot choose a different subject.
                    """)

        elif t_menu == "📊 Subject Reports & Defaulters":
            st.subheader("👨‍🏫 Subject Analytics & Defaulters (<75%)")
            
            selected_subject = st.selectbox("Select Subject:", SUBJECTS)
            df_att = load_subject_attendance(selected_subject)
            df_curr_students = load_students()

            if not df_att.empty:
                total_conducted = st.number_input(f"Total Conducted Lectures for '{selected_subject}':", min_value=1, value=10)

                counts = df_att.groupby('RollNo')['Date'].nunique().reset_index()
                counts.columns = ['RollNo', 'Attended']
                counts['RollNo'] = counts['RollNo'].astype(str)

                report = pd.merge(df_curr_students, counts, on='RollNo', how='left').fillna(0)
                report['Attended'] = report['Attended'].astype(int)
                report['Absent'] = (total_conducted - report['Attended']).clip(lower=0).astype(int)
                report['Attendance %'] = round((report['Attended'] / total_conducted) * 100, 1)
                report['Status'] = report['Attendance %'].apply(lambda x: "🚨 DEFAULTER" if x < 75 else "✅ Regular")

                st.markdown("### 📈 Overall Subject Summary Table")
                st.dataframe(
                    report[['RollNo', 'Name', 'Attended', 'Absent', 'Attendance %', 'Status']], 
                    use_container_width=True
                )

                st.write("---")
                st.subheader(f"📅 Daily Attendance & Absentee List ({selected_subject})")
                unique_dates = sorted(df_att['Date'].unique().tolist(), reverse=True)

                if unique_dates:
                    selected_date = st.selectbox("Select Lecture Date:", unique_dates)
                    daily_att = df_att[df_att['Date'] == selected_date]
                    present_rolls = daily_att['RollNo'].astype(str).tolist()

                    df_curr_students['RollNo'] = df_curr_students['RollNo'].astype(str)
                    
                    present_df = daily_att[['RollNo', 'Name', 'Time']].copy()
                    present_df['Status'] = "🟢 Present"

                    absent_df = df_curr_students[~df_curr_students['RollNo'].isin(present_rolls)].copy()
                    absent_df['Status'] = "🔴 Absent"

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Class Strength", len(df_curr_students))
                    m2.metric("Present Today", len(present_df))
                    m3.metric("Absent Today", len(absent_df))

                    col_p, col_a = st.columns(2)
                    with col_p:
                        st.markdown(f"#### 🟢 Present ({len(present_df)})")
                        st.dataframe(present_df[['RollNo', 'Name', 'Time', 'Status']], use_container_width=True)
                    
                    with col_a:
                        st.markdown(f"#### 🔴 Absent ({len(absent_df)})")
                        st.dataframe(absent_df[['RollNo', 'Name', 'Status']], use_container_width=True)

                st.write("---")
                defaulters = report[report['Attendance %'] < 75]
                st.subheader(f"🚨 Defaulter List for {selected_subject} (<75%)")
                if not defaulters.empty:
                    st.error(f"Found {len(defaulters)} defaulter student(s):")
                    st.table(defaulters[['RollNo', 'Name', 'Attended', 'Absent', 'Attendance %']])
                else:
                    st.success("🎉 All students meet or exceed the 75% attendance criteria!")

                st.write("---")
                csv_data = df_att.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"📥 Download {selected_subject} Backup CSV",
                    data=csv_data,
                    file_name=f"{sanitize_filename(selected_subject)}_backup_{datetime.now(IST).strftime('%Y-%m-%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info(f"No attendance records logged for '{selected_subject}' yet.")

            st.write("---")
            with st.expander(f"🗑️ Reset / Erase Attendance Data for {selected_subject}"):
                st.warning(f"⚠️ **Warning:** This action will permanently delete all logged attendance records for **'{selected_subject}'** from both Google Sheets and local backups.")
                confirm_reset = st.checkbox(f"I understand that this will erase all attendance data for '{selected_subject}'")
                
                if st.button(f"🔥 Reset Attendance Data for {selected_subject}", disabled=not confirm_reset):
                    reset_subject_attendance(selected_subject)
                    st.success(f"🎉 Attendance data for '{selected_subject}' has been successfully reset!")
                    time.sleep(1.5)
                    st.rerun()

        elif t_menu == "📁 Upload Student Roster":
            st.subheader("📁 Upload Student List (CSV or Excel)")
            st.caption("Upload an `.xlsx` or `.csv` file containing student roll numbers and names.")

            uploaded_file = st.file_uploader("Choose an Excel/CSV file", type=["csv", "xlsx"])

            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        new_df = pd.read_csv(uploaded_file)
                    else:
                        new_df = pd.read_excel(uploaded_file)

                    new_df.columns = new_df.columns.astype(str).str.strip()

                    col_mapping = {}
                    for col in new_df.columns:
                        cleaned_col = col.lower().replace(" ", "").replace("_", "").replace("-", "")
                        if cleaned_col in ["rollno", "roll", "rollnumber", "srno", "sno"]:
                            col_mapping[col] = "RollNo"
                        elif cleaned_col in ["name", "studentname", "student"]:
                            col_mapping[col] = "Name"

                    new_df.rename(columns=col_mapping, inplace=True)

                    if 'RollNo' not in new_df.columns or 'Name' not in new_df.columns:
                        st.error("🚨 Could not detect Roll Number and Name columns automatically!")
                        st.warning(f"Detected columns in your file: `{list(new_df.columns)}`")
                        st.info("Please ensure your file has columns named 'RollNo' and 'Name'.")
                    else:
                        new_df['RollNo'] = new_df['RollNo'].astype(str)
                        new_df = new_df[['RollNo', 'Name']].dropna()
                        
                        st.write("### Preview of Uploaded Roster:")
                        st.dataframe(new_df, use_container_width=True)

                        if st.button("💾 Permanently Save Student List"):
                            save_students(new_df)
                            st.success(f"🎉 Successfully saved {len(new_df)} students permanently to Google Sheets!")
                            time.sleep(1)
                            st.rerun()

                except Exception as e:
                    st.error(f"Error reading file: {e}")

            st.write("---")
            st.subheader("📋 Currently Active Student Roster")
            df_curr = load_students()
            st.dataframe(df_curr, use_container_width=True)