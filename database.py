import sqlite3
import hashlib

DB_NAME = "journal.db"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            subject TEXT,
            is_curator BOOLEAN DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            date TEXT NOT NULL,
            lesson_num INTEGER DEFAULT 1,
            value TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # Куратор
        cursor.execute('''
            INSERT INTO users (username, password, full_name, subject, is_curator)
            VALUES (?, ?, ?, ?, ?)
        ''', ("curator", hash_password("curator1234"), "Կուրատոր (Куратор)", "Համ. օպեր.", 1))

        # Преподаватели
        teachers_def = [
            ("math", "Բարձր. մաթեմ.", "math7492"),
            ("market", "Մարքեթինգ", "market3184"),
            ("armenian", "Հայոց լեզու", "armenian5920"),
            ("history", "Պատմություն", "history8314"),
            ("pe", "Ֆիզկուլտ", "pe4019"),
            ("biz", "Աշխ. գործ. ընդ.", "biz6723"),
            ("os", "Համ. օպեր.", "os1954"),
            ("english", "Օտար լեզու", "english9041"),
            ("russian", "Ռուսաց լեզու", "russian2835"),
            ("econ", "Կիրառ. տնտ.", "econ5162"),
        ]

        for username, subject_name, default_pwd in teachers_def:
            full_title = f"Ուսուցիչ ({subject_name})"
            cursor.execute('''
                INSERT INTO users (username, password, full_name, subject, is_curator)
                VALUES (?, ?, ?, ?, 0)
            ''', (username, hash_password(default_pwd), full_title, subject_name))

        # 19 учеников
        for i in range(1, 20):
            cursor.execute("INSERT INTO students (full_name) VALUES (?)", (f"Ուսանող {i}",))

    conn.commit()
    conn.close()

def authenticate_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, full_name, subject, is_curator FROM users WHERE username = ? AND password = ?",
        (username, hash_password(password))
    )
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_credentials(user_id, new_username, new_password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        if new_password.strip():
            hashed = hash_password(new_password)
            cursor.execute("UPDATE users SET username = ?, password = ? WHERE id = ?", (new_username, hashed, user_id))
        else:
            cursor.execute("UPDATE users SET username = ? WHERE id = ?", (new_username, user_id))
        conn.commit()
        conn.close()
        return True, "Տվյալները հաջողությամբ թարմացվել են:"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Այս մուտքանունն արդեն զբաղված է:"
    except Exception as e:
        conn.close()
        return False, str(e)

def get_all_students():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name FROM students")
    students = cursor.fetchall()
    conn.close()
    return students

# Новая функция: получение списка реальных предметов из базы
def get_all_subjects():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT subject FROM users WHERE is_curator = 0 AND subject IS NOT NULL")
    subjects = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subjects

def add_or_update_record(student_id, subject, date_str, lesson_num, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM records WHERE student_id = ? AND subject = ? AND date = ? AND lesson_num = ?
    ''', (student_id, subject, date_str, lesson_num))
    existing = cursor.fetchone()

    if existing:
        cursor.execute('UPDATE records SET value = ? WHERE id = ?', (value, existing[0]))
    else:
        cursor.execute('INSERT INTO records (student_id, subject, date, lesson_num, value) VALUES (?, ?, ?, ?, ?)', 
                       (student_id, subject, date_str, lesson_num, value))

    conn.commit()
    conn.close()

def get_teacher_records_for_date(subject, date_str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.full_name,
               MAX(CASE WHEN r.lesson_num = 1 THEN r.value END) as l1,
               MAX(CASE WHEN r.lesson_num = 2 THEN r.value END) as l2
        FROM students s
        LEFT JOIN records r ON s.id = r.student_id AND r.date = ? AND r.subject = ?
        GROUP BY s.id, s.full_name
    ''', (date_str, subject))
    data = cursor.fetchall()
    conn.close()
    return data

def get_records_by_date_and_subject(date_str, subject):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.full_name, 
               MAX(CASE WHEN r.lesson_num = 1 THEN r.value END) as lesson1,
               MAX(CASE WHEN r.lesson_num = 2 THEN r.value END) as lesson2
        FROM students s
        LEFT JOIN records r ON s.id = r.student_id AND r.date = ? AND r.subject = ?
        GROUP BY s.id, s.full_name
    ''', (date_str, subject))
    data = cursor.fetchall()
    conn.close()
    return data

# ИСПРАВЛЕНО: группировка 1 и 2 уроков по дате и предмету
def get_student_history(student_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT date, subject,
               MAX(CASE WHEN lesson_num = 1 THEN value END) as lesson1,
               MAX(CASE WHEN lesson_num = 2 THEN value END) as lesson2
        FROM records 
        WHERE student_id = ?
        GROUP BY date, subject
        ORDER BY date DESC, subject
    ''', (student_id,))
    data = cursor.fetchall()
    conn.close()
    return data

if __name__ == "__main__":
    init_db()
    print("[+] База данных инициализирована.")