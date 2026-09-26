import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

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

# Таблица связки Преподаватель <-> Предмет
teacher_subjects = Table(
    'teacher_subjects', Base.metadata,
    Column('teacher_id', Integer, ForeignKey('users.id')),
    Column('subject_id', Integer, ForeignKey('subjects.id'))
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, nullable=False) # 'admin', 'teacher'
    is_kursghek = Column(Integer, default=0) # 1 если Куратор
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
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)

class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    lesson_number = Column(Integer, nullable=False) # 1..9
    grade_value = Column(String, nullable=False) # 1..10, 'Բ', 'Հ', 'Ն'
    date = Column(String, nullable=False) # YYYY-MM-DD
    is_locked = Column(Integer, default=1) # 1 - заблокировано для учителя

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Инициализация 30 базовых курсов
    if db.query(Course).count() == 0:
        for i in range(1, 31):
            db.add(Course(id=i, name=f"Курс {i}"))
        db.commit()

    # Инициализация дефолтного предмета
    if db.query(Subject).count() == 0:
        db.add(Subject(id=1, name="Основной предмет"))
        db.commit()

    # Админ
    admin = db.query(User).filter_by(username="admin").first()
    if not admin:
        db.add(User(username="admin", password="admin123", role="admin", full_name="Администратор"))
        db.commit()

    # 30 Учителей
    if db.query(User).filter(User.role == "teacher").count() == 0:
        default_subj = db.query(Subject).first()
        for i in range(1, 31):
            u = User(
                username=f"teacher{i}",
                password="password123",
                full_name=f"Преподаватель {i}",
                role="teacher",
                is_kursghek=1,
                assigned_course_id=i
            )
            if default_subj:
                u.subjects.append(default_subj)
            db.add(u)
        db.commit()

    db.close()

if __name__ == "__main__":
    init_db()
