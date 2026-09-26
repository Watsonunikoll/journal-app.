import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+psycopg://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    engine = create_engine("sqlite:///journal.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

teacher_subjects = Table(
    'teacher_subjects', Base.metadata,
    Column('teacher_id', Integer, ForeignKey('users.id', ondelete="CASCADE")),
    Column('subject_id', Integer, ForeignKey('subjects.id', ondelete="CASCADE"))
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, nullable=False) # 'admin', 'teacher'
    is_kursghek = Column(Integer, default=0)
    assigned_course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)

    subjects = relationship("Subject", secondary=teacher_subjects, back_populates="teachers")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    teachers = relationship("User", secondary=teacher_subjects, back_populates="subjects")

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lesson_number = Column(Integer, nullable=False)
    grade_value = Column(String, nullable=False)
    date = Column(String, nullable=False)
    is_locked = Column(Integer, default=1)

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Инициализация 30 курсов
    if db.query(Course).count() == 0:
        for i in range(1, 31):
            db.add(Course(id=i, name=f"Կուրս {i}"))
        db.commit()

    # Инициализация 30 студентов для каждого курса (всего 900)
    if db.query(Student).count() == 0:
        courses = db.query(Course).all()
        for c in courses:
            for s_num in range(1, 31):
                db.add(Student(full_name=f"Student {s_num}", course_id=c.id))
        db.commit()

    # Админ
    admin = db.query(User).filter_by(username="admin").first()
    if not admin:
        db.add(User(username="admin", password="admin123", role="admin", full_name="Admin"))
        db.commit()

    # 30 Учителей и у каждого свой предмет (учитель 1 -> предмет teacher 1)
    if db.query(User).filter(User.role == "teacher").count() == 0:
        for i in range(1, 31):
            subj_name = f"teacher {i}"
            subj = Subject(name=subj_name)
            db.add(subj)
            db.commit()

            u = User(
                username=f"teacher{i}",
                password="password123",
                full_name=f"Teacher {i}",
                role="teacher",
                is_kursghek=1,
                assigned_course_id=i
            )
            u.subjects.append(subj)
            db.add(u)
            db.commit()

    db.close()

if __name__ == "__main__":
    init_db()
