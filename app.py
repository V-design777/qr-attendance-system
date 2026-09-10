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
st.set_page_config(
    page_title="FYBSc AI & ML | V.G. Vaze (Kelkar) College", 
    page_icon="🤖", 
    layout="wide"
)

SECRET_KEY = "vaze_kelkar_aiml_secure_key"
TOKEN_EXPIRY_SECONDS = 300  # 5 Minutes QR validity
TEACHER_PASSWORD = "admin123"

# --- FYBSc AI & ML SUBJECT ROSTER ---
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

# --- GOOGLE SHEETS & LOCAL DATA HANDLING ---
@st.cache_resource
def get_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception:
        return None

conn = get_connection()

def load_students():
    """Loads students permanently from Google Sheets or local file"""
    if conn:
        try:
            df = conn.read(worksheet="Students", ttl=0)
            if not df.empty and 'RollNo' in df.columns:
                df['RollNo'] = df['RollNo'].astype(str)
                return df
        except Exception:
            pass
    
    # Fallback to local CSV
    if os.path.exists("students.csv"):
        df = pd.read_csv("students.csv")
        df['RollNo'] = df['RollNo'].astype(str)
        return df
    return pd.DataFrame([{"RollNo": "101", "Name": "Sample Student"}])

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

def load_attendance():
    """Loads attendance entries permanently"""
    if conn:
        try:
            df = conn.read(worksheet="Attendance", ttl=0)
            if not df.empty:
                df['RollNo'] = df['RollNo'].astype(str)
                return df
        except Exception:
            pass
    
    if os.path.exists("attendance.csv"):
        df = pd.read_csv("attendance.csv")
        df['RollNo'] = df['RollNo'].astype(str)
        return df
    return pd.DataFrame(columns=["Date", "Time", "Subject", "RollNo", "Name", "Status"])

def append_attendance(new_row_df):
    """Appends attendance permanently to Google Sheets and local file"""
    new_row_df['RollNo'] = new_row_df['RollNo'].astype(str)
    
    if os.path.exists("attendance.csv"):
        new_row_df.to_csv("attendance.csv", mode='a', header=False, index=False)
    else:
        new_row_df.to_csv("attendance.csv", index=False)
        
    if conn:
        try:
            existing = load_attendance()
            updated_df = pd.concat([existing, new_row_df], ignore_index=True)
            conn.update(worksheet="Attendance", data=updated_df)
            st.cache_data.clear()
        except Exception as e:
            st.warning(f"Saved locally, but Google Sheets sync pending: {e}")

# --- HELPER FUNCTIONS ---
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

# --- BRANDING HEADER ---
st.title("🤖 V.G. Vaze (Kelkar) College")
st.caption("Department of Artificial Intelligence & Machine Learning — FYBSc Smart Attendance System")
st.write("---")

url_token = st.query_params.get("token", None)

# --- 1. LOGIN SCREEN ---
if not st.session_state["logged_in"]:
    st.subheader("🔑 Access Portal")
    role = st.radio("Select Login Type:", ["Student", "Teacher"], horizontal=True)

    if role == "Student":
        df_students = load_students()
        roll_list = df_students["RollNo"].unique().tolist()
        
        selected_roll = st.selectbox("Select Your Roll Number (FYBSc AI & ML):", roll_list)
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
        password = st.text_input("Enter Faculty Password:", type="password")
        if st.button("Log In as Faculty"):
            if password == TEACHER_PASSWORD:
                st.session_state["logged_in"] = True
                st.session_state["role"] = "Teacher"
                st.success("Authenticated!")
                st.rerun()
            else:
                st.error("Incorrect Password!")

# --- 2. LOGGED IN PORTAL ---
else:
    st.sidebar.title("🏫 Kelkar College Portal")
    st.sidebar.markdown("**Class:** FYBSc AI & ML")
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
                st.warning("This QR code has expired (valid for 5 minutes). Scan the active QR code projected on the classroom board.")
            else:
                st.success("✅ QR Session Verified (5-Min Window Active)!")
                
                with st.form("student_mark_form"):
                    selected_subject = st.selectbox("Select Subject:", SUBJECTS)
                    submit = st.form_submit_button("✅ Submit Attendance")

                if submit:
                    now_ist = datetime.now(IST)
                    today = now_ist.strftime("%Y-%m-%d")
                    current_time = now_ist.strftime("%H:%M:%S")

                    df_att = load_attendance()

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
                        append_attendance(new_entry)
                        st.success(f"🎉 Marked Present for {selected_subject} at {current_time} (IST)! (Saved Permanently)")
                        st.balloons()

        elif menu == "📊 My Monthly Attendance %":
            st.subheader(f"FYBSc AI & ML Report: {st.session_state['student_name']} (Roll: {st.session_state['student_roll']})")
            
            df_att = load_attendance()
            if not df_att.empty:
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
        try:
            sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        except Exception:
            sheet_url = "https://sheets.google.com"

        st.sidebar.markdown("---")
        st.sidebar.link_button("🟢 Open Live Google Sheet", sheet_url)

        t_menu = st.sidebar.radio("Faculty Menu", [
            "📺 Classroom Projector (Live QR)", 
            "📊 Full Class Reports & Defaulters",
            "📁 Upload Student Roster"
        ])

        if t_menu == "📺 Classroom Projector (Live QR)":
            st.subheader("📺 Classroom Projector Display")
            st.caption("Project this screen on the board. The QR code automatically expires every 5 minutes.")

            base_url = get_public_url()
            current_token = get_current_token()
            dynamic_url = f"{base_url}/?token={current_token}"

            seconds_remaining = TOKEN_EXPIRY_SECONDS - (int(time.time()) % TOKEN_EXPIRY_SECONDS)
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
                ### ⏱️ 5-Minute Timed Session (FYBSc AI & ML)
                * **Time Remaining for Current QR:** `{mins_left}m {secs_left}s`
                * **Active Link:** `{dynamic_url}`
                * **Anti-Proxy Rule:** Screenshots shared after 5 minutes will be rejected automatically.
                """)
                
                if st.button("🔄 Force Refresh / Generate New QR"):
                    st.rerun()

        elif t_menu == "📊 Full Class Reports & Defaulters":
            st.subheader("👨‍🏫 Faculty Analytics & Defaulters (<75%)")
            
            df_att = load_attendance()
            df_curr_students = load_students()

            if not df_att.empty:
                selected_subject = st.selectbox("Select Subject:", SUBJECTS)
                total_conducted = st.number_input(f"Total Conducted Lectures for '{selected_subject}':", min_value=1, value=10)

                subj_att = df_att[df_att['Subject'] == selected_subject]
                counts = subj_att.groupby('RollNo')['Date'].nunique().reset_index()
                counts.columns = ['RollNo', 'Attended']
                counts['RollNo'] = counts['RollNo'].astype(str)

                report = pd.merge(df_curr_students, counts, on='RollNo', how='left').fillna(0)
                report['Attendance %'] = round((report['Attended'] / total_conducted) * 100, 1)
                report['Status'] = report['Attendance %'].apply(lambda x: "🚨 DEFAULTER" if x < 75 else "✅ Regular")

                st.dataframe(report[['RollNo', 'Name', 'Attended', 'Attendance %', 'Status']], use_container_width=True)

                defaulters = report[report['Attendance %'] < 75]
                st.write("---")
                st.subheader("🚨 FYBSc AI & ML Defaulter List (<75%)")
                if not defaulters.empty:
                    st.error(f"Found {len(defaulters)} defaulter student(s):")
                    st.table(defaulters[['RollNo', 'Name', 'Attended', 'Attendance %']])
                else:
                    st.success("🎉 All students meet or exceed the 75% attendance criteria!")

                st.write("---")
                csv_data = df_att.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Full Attendance Excel/CSV Backup",
                    data=csv_data,
                    file_name=f"fybsc_aiml_attendance_{datetime.now(IST).strftime('%Y-%m-%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No attendance records logged yet.")

        elif t_menu == "📁 Upload Student Roster":
            st.subheader("📁 Upload FYBSc AI & ML Roster (CSV or Excel)")
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
            st.subheader("📋 Currently Active FYBSc AI & ML Student Roster")
            df_curr = load_students()
            st.dataframe(df_curr, use_container_width=True)