import os
from datetime import datetime, timedelta
import torch
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
import csv

# Initialize models (keep these global to avoid re-loading)
mtcnn = MTCNN(image_size=160, margin=0)
resnet = InceptionResnetV1(pretrained='vggface2').eval()

face_db = {}  # name -> embedding tensor

def load_database():
    """Load embeddings from images inside static/uploads/image_data/"""
    supported = ('.jpg', '.jpeg', '.png')
    base = 'static/uploads/image_data'
    os.makedirs(base, exist_ok=True)
    face_db.clear()
    for f in os.listdir(base):
        if f.lower().endswith(supported):
            path = os.path.join(base, f)
            emb = detect_and_vectorize(path)
            if emb is not None:
                name = os.path.splitext(f)[0]
                face_db[name] = emb

def detect_and_vectorize(image_path):
    """Return embedding tensor or None if no face detected."""
    try:
        img = Image.open(image_path).convert('RGB')
    except Exception:
        return None
    face_tensor = mtcnn(img)
    if face_tensor is None:
        return None
    with torch.no_grad():
        embedding = resnet(face_tensor.unsqueeze(0)).detach()
    return embedding

def cosine_similarity(a, b):
    """Compute cosine similarity between two 1xN tensors."""
    return torch.nn.functional.cosine_similarity(a, b).item()

def register_user(image_path):
    """Called after an image file is placed in image_data. Reload DB."""
    load_database()

def is_logged_in_today(name, csv_file="user_verifications.csv"):
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(csv_file, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('Name') == name and row.get('Date') == today:
                    # determine state based on columns
                    if row.get('MLogin_Time','') == '':
                        return -1
                    elif row.get('MLogout_Time','') == '':
                        return 0
                    elif row.get('ALogin_Time','') == '':
                        return -1
                    elif row.get('ALogout_Time','') == '':
                        return 0
                    elif row.get('ELogin_Time','') == '':
                        return -1
                    elif row.get('ELogout_Time','') == '':
                        return 0
                    else:
                        return 1
    except FileNotFoundError:
        return -1
    return -1

def record_verification(name, csv_file="user_verifications.csv"):
    today = datetime.now().strftime("%Y-%m-%d")
    login_time = datetime.now().strftime("%H:%M:%S")
    
    rows = []
    found_today = False
    shift=None
    # Read existing CSV
    try:
        with open(csv_file, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                if row["Name"] == name and row["Date"] == today:
                    found_today = True
    except FileNotFoundError:
        pass  # File will be created

    # ---------- Case 1: User already has a record today ----------
    if found_today:
        for row in rows:
            if row["Name"] == name and row["Date"] == today:
                if row["ALogin_Time"] == "":
                    break_c=datetime.strptime(row["MLogout_Time"], "%H:%M:%S")-datetime.strptime(login_time, "%H:%M:%S")
                    if break_c>timedelta(hours=1) and break_c<=timedelta(hours=1,minutes=15):
                        login_time=(datetime.strptime(row["MLogout_Time"], "%H:%M:%S")+timedelta(hours=1)).time()
                    row["ALogin_Time"] = login_time
                elif row["ELogin_Time"] == "":
                    break_d=datetime.strptime(row["ALogout_Time"], "%H:%M:%S")-datetime.strptime(login_time, "%H:%M:%S")
                    if break_d>=timedelta(minutes=30) and break_d<=timedelta(minutes=45):
                        login_time=(datetime.strptime(row["ALogout_Time"], "%H:%M:%S")+timedelta(minutes=30)).time()
                    row["ELogin_Time"] = login_time
                break  # done

    # ---------- Case 2: First login of the day ----------
    else:
        # Insert blank row when date changes
        if rows and rows[-1]["Date"] != today:
            rows.append({})   # blank separator row
        morning_time=datetime.strptime("03:00:00","%H:%M:%S")
        day_time=(morning_time+timedelta(hours=8))
        night_time=day_time+timedelta(hours=8)
        
        time=datetime.strptime(login_time,"%H:%M:%S")
        
        if (time>=morning_time) and (time<=day_time):
            shift="Morning"
            
            if time-(morning_time)<=timedelta(minutes=15):
                login_time=morning_time.time()
        elif (time>=day_time) and (time<=night_time):
            shift="Day"
            print(time-morning_time)
            if time-day_time<=timedelta(minutes=15):
                login_time=day_time.time()
        elif (time>=night_time) or (time<=morning_time):
            shift="Night"
            if time-night_time<=timedelta(minutes=15):
                login_time=night_time.time()
       
        rows.append({
            "Name": name,
            "Date": today,
            "Shift":shift,
            "MLogin_Time": login_time,
            "MLogout_Time": "",
            "ALogin_Time": "",
            "ALogout_Time": "",
            "ELogin_Time": "",
            "ELogout_Time": "",
            "Worked_Hours": ""
        })

    # Write updated CSV
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["Name", "Date","Shift",
                      "MLogin_Time", "MLogout_Time",
                      "ALogin_Time", "ALogout_Time",
                      "ELogin_Time", "ELogout_Time",
                      "Worked_Hours"]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            # Write blank row
            if row == {}:
                f.write("\n")
                continue
            writer.writerow(row)

def add_logout_time(name,csv_file="user_verifications.csv", logout_time=None):
    if logout_time is None:
        logout_time = datetime.now().strftime('%H:%M:%S')
    rows = []
    updated = False
    work=None
    # Read the CSV content
    with open(csv_file, 'r', newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['Name'] == name:
                if row["MLogout_Time"] == "":
                    row["MLogout_Time"] = logout_time
                elif row["ALogout_Time"] == "":
                    row["ALogout_Time"] = logout_time
                elif row["ELogout_Time"] == "":
                    row["ELogout_Time"] = logout_time
            
                    total_delta = timedelta()
                    if row['MLogin_Time'] and row['MLogout_Time']:
                        m_delta = datetime.strptime(row['MLogout_Time'], '%H:%M:%S') - datetime.strptime(row['MLogin_Time'], '%H:%M:%S')
                        total_delta += m_delta
                    if row['ALogin_Time'] and row['ALogout_Time']:
                        a_delta = datetime.strptime(row['ALogout_Time'], '%H:%M:%S') - datetime.strptime(row['ALogin_Time'], '%H:%M:%S')
                        total_delta += a_delta
                    if row['ELogin_Time'] and row['ELogout_Time']:
                        e_delta = datetime.strptime(row['ELogout_Time'], '%H:%M:%S') - datetime.strptime(row['ELogin_Time'], '%H:%M:%S')
                        total_delta += e_delta
                    
                    total_seconds = int(total_delta.total_seconds())
                    # Convert timedelta to hours
                    
                    hours = (total_seconds // 3600)+1
                    minutes = ((total_seconds % 3600) // 60)+30

    # Format as "H:MM"
                    
                    worked_hours = f"{hours}:{minutes:02d}"
                    row['Worked_Hours'] = worked_hours
                # except Exception as e:
                #     print(f"Error calculating worked hours: {e}")
                #     row['Worked_Hours'] = ''
                updated = True
            rows.append(row)
    
    # If user not found, optionally add a new row (depends on your need)
    if not updated:
        rows.append({
            "Name": name,
            "Date": "",
            "Shift":"",
            "MLogin_Time": "",
            "MLogout_Time": "",
            "ALogin_Time": "",
            "ALogout_Time": "",
            "ELogin_Time": "",
            "ELogout_Time": "",
            "Worked_Hours": ""
        })
    
    # Write back the CSV with updated logout time
    with open(csv_file, 'w', newline='') as file:
        fieldnames = rows[0].keys() if rows else ["Name", "Date","Shift",
                      "MLogin_Time", "MLogout_Time",
                      "ALogin_Time", "ALogout_Time",
                      "ELogin_Time", "ELogout_Time",
                      "Worked_Hours"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def process_attendance(image_path):
    """Main entry used by Flask. Returns (result_message, name_or_None)."""
    load_database()
    target = detect_and_vectorize(image_path)
    if target is None:
        return ("No face detected", None)

    best_name = None
    best_sim = -1.0
    for name, vec in face_db.items():
        sim = cosine_similarity(target, vec)
        if sim > best_sim:
            best_sim = sim
            best_name = name

    # threshold can be tuned
    if best_sim < 0.70 or best_name is None:
        return ("Unknown face — please register", None)

    status = is_logged_in_today(best_name)
    if status == -1:
        record_verification(best_name)
        return ("Login recorded", best_name)
    elif status == 0:
        add_logout_time(best_name)
        return ("Logout recorded", best_name)
    else:
        return ("Already completed today", best_name)