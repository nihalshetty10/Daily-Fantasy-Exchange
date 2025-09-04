import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, UniqueConstraint, Date, Float, Text
from passlib.hash import bcrypt
from backend.db import Base


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        UniqueConstraint('username', name='uq_users_username'),
        UniqueConstraint('email', name='uq_users_email'),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(64), nullable=True)
    last_name = Column(String(64), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    phone_number = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(10), nullable=True)
    country = Column(String(50), default='US', nullable=False)
    
    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Trading info
    balance = Column(Float, default=10000.0, nullable=False)  # Starting balance
    total_deposits = Column(Float, default=0.0, nullable=False)
    total_withdrawals = Column(Float, default=0.0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)

    # Password helpers
    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hash(password)

    def check_password(self, password: str) -> bool:
        return bcrypt.verify(password, self.password_hash)
    
    # User info helpers
    def get_full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def get_age(self) -> int:
        if self.date_of_birth:
            today = datetime.date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None
    
    def is_adult(self) -> bool:
        age = self.get_age()
        return age is not None and age >= 18
    
    def update_last_login(self) -> None:
        self.last_login = datetime.datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.get_full_name(),
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'age': self.get_age(),
            'is_adult': self.is_adult(),
            'phone_number': self.phone_number,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'balance': self.balance,
            'total_deposits': self.total_deposits,
            'total_withdrawals': self.total_withdrawals,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        } 