import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.models.user import User
from backend.db import get_db_session


class AuthService:
    """Service for user authentication and management"""
    
    @staticmethod
    def create_user(
        username: str,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        date_of_birth: Optional[datetime.date] = None,
        phone_number: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        zip_code: Optional[str] = None,
        country: str = 'US'
    ) -> Optional[dict]:
        """Create a new user"""
        try:
            from sqlalchemy import text
            from passlib.hash import bcrypt
            
            with next(get_db_session()) as db:
                # Check if user already exists using raw SQL
                existing = db.execute(
                    text("SELECT id FROM users WHERE username = :username OR email = :email"),
                    {"username": username, "email": email}
                ).fetchone()
                
                if existing:
                    return None
                
                # Hash password
                password_hash = bcrypt.hash(password)
                
                # Create user using raw SQL
                result = db.execute(
                    text("""
                        INSERT INTO users (username, email, password_hash, first_name, last_name, 
                                         date_of_birth, phone_number, address, city, state, zip_code, 
                                         country, is_active, is_admin, is_verified, balance, total_deposits, 
                                         total_withdrawals, created_at, updated_at)
                        VALUES (:username, :email, :password_hash, :first_name, :last_name,
                                :date_of_birth, :phone_number, :address, :city, :state, :zip_code,
                                :country, 1, 0, 0, 10000.0, 0.0, 0.0, :now, :now)
                    """),
                    {
                        "username": username,
                        "email": email,
                        "password_hash": password_hash,
                        "first_name": first_name,
                        "last_name": last_name,
                        "date_of_birth": date_of_birth,
                        "phone_number": phone_number,
                        "address": address,
                        "city": city,
                        "state": state,
                        "zip_code": zip_code,
                        "country": country,
                        "now": datetime.datetime.utcnow()
                    }
                )
                
                db.commit()
                user_id = result.lastrowid
                
                # Get the created user data
                user_result = db.execute(
                    text("SELECT * FROM users WHERE id = :user_id"),
                    {"user_id": user_id}
                ).fetchone()
                
                if user_result:
                    # Build user data
                    user_data = {
                        'id': user_result.id,
                        'username': user_result.username,
                        'email': user_result.email,
                        'first_name': user_result.first_name,
                        'last_name': user_result.last_name,
                        'phone_number': user_result.phone_number,
                        'city': user_result.city,
                        'state': user_result.state,
                        'country': user_result.country,
                        'is_active': user_result.is_active,
                        'is_verified': user_result.is_verified,
                        'balance': user_result.balance,
                        'total_deposits': user_result.total_deposits,
                        'total_withdrawals': user_result.total_withdrawals,
                        'created_at': str(user_result.created_at) if user_result.created_at else None,
                        'last_login': str(user_result.last_login) if user_result.last_login else None
                    }
                    
                    # Calculate derived fields
                    full_name = f"{user_result.first_name} {user_result.last_name}" if user_result.first_name and user_result.last_name else user_result.username
                    user_data['full_name'] = full_name
                    
                    age = None
                    if user_result.date_of_birth and str(user_result.date_of_birth).strip():
                        # Handle date conversion
                        if hasattr(user_result.date_of_birth, 'isoformat'):
                            user_data['date_of_birth'] = user_result.date_of_birth.isoformat()
                            dob = user_result.date_of_birth
                        else:
                            user_data['date_of_birth'] = str(user_result.date_of_birth)
                            # Try to parse the date string
                            try:
                                dob = datetime.datetime.strptime(str(user_result.date_of_birth), '%Y-%m-%d').date()
                            except:
                                dob = None
                        
                        if dob:
                            today = datetime.date.today()
                            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                    else:
                        user_data['date_of_birth'] = None
                    
                    user_data['age'] = age
                    user_data['is_adult'] = age is not None and age >= 18
                    
                    return user_data
                
                return None
                
        except Exception as e:
            print(f"Error creating user: {e}")
            return None
    
    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[dict]:
        """Authenticate a user by username/email and password"""
        try:
            # Use raw SQL to avoid session issues completely
            from sqlalchemy import text
            from passlib.hash import bcrypt
            
            with next(get_db_session()) as db:
                # Get user data using raw SQL
                result = db.execute(
                    text("SELECT * FROM users WHERE (username = :username OR email = :username) AND is_active = 1"),
                    {"username": username}
                ).fetchone()
                
                if result:
                    # Check password
                    password_valid = bcrypt.verify(password, result.password_hash)
                    
                    if not password_valid:
                        return None
                    
                    # Update last login
                    db.execute(
                        text("UPDATE users SET last_login = :now WHERE id = :user_id"),
                        {"now": datetime.datetime.utcnow(), "user_id": result.id}
                    )
                    db.commit()
                    
                    # Build user data from result
                    user_data = {
                        'id': result.id,
                        'username': result.username,
                        'email': result.email,
                        'first_name': result.first_name,
                        'last_name': result.last_name,
                        'phone_number': result.phone_number,
                        'city': result.city,
                        'state': result.state,
                        'country': result.country,
                        'is_active': result.is_active,
                        'is_verified': result.is_verified,
                        'balance': result.balance,
                        'total_deposits': result.total_deposits,
                        'total_withdrawals': result.total_withdrawals,
                        'created_at': str(result.created_at) if result.created_at else None,
                        'last_login': str(result.last_login) if result.last_login else None
                    }
                    
                    # Calculate derived fields
                    full_name = f"{result.first_name} {result.last_name}" if result.first_name and result.last_name else result.username
                    user_data['full_name'] = full_name
                    
                    age = None
                    if result.date_of_birth and str(result.date_of_birth).strip():
                        # Handle date conversion
                        if hasattr(result.date_of_birth, 'isoformat'):
                            user_data['date_of_birth'] = result.date_of_birth.isoformat()
                            dob = result.date_of_birth
                        else:
                            user_data['date_of_birth'] = str(result.date_of_birth)
                            # Try to parse the date string
                            try:
                                dob = datetime.datetime.strptime(str(result.date_of_birth), '%Y-%m-%d').date()
                            except:
                                dob = None
                        
                        if dob:
                            today = datetime.date.today()
                            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                    else:
                        user_data['date_of_birth'] = None
                    
                    user_data['age'] = age
                    user_data['is_adult'] = age is not None and age >= 18
                    
                    return user_data
                
                return None
                
        except Exception as e:
            print(f"Error authenticating user: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[User]:
        """Get user by ID"""
        try:
            with next(get_db_session()) as db:
                return db.query(User).filter(User.id == user_id).first()
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None
    
    @staticmethod
    def get_user_by_username(username: str) -> Optional[User]:
        """Get user by username"""
        try:
            with next(get_db_session()) as db:
                return db.query(User).filter(User.username == username).first()
        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[User]:
        """Get user by email"""
        try:
            with next(get_db_session()) as db:
                return db.query(User).filter(User.email == email).first()
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None
    
    @staticmethod
    def update_user_balance(user_id: int, new_balance: float) -> bool:
        """Update user's balance"""
        try:
            with next(get_db_session()) as db:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.balance = new_balance
                    db.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error updating user balance: {e}")
            return False
    
    @staticmethod
    def update_user_info(user_id: int, **kwargs) -> bool:
        """Update user information"""
        try:
            with next(get_db_session()) as db:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    for key, value in kwargs.items():
                        if hasattr(user, key) and value is not None:
                            setattr(user, key, value)
                    db.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error updating user info: {e}")
            return False
    
    @staticmethod
    def deactivate_user(user_id: int) -> bool:
        """Deactivate a user account"""
        try:
            with next(get_db_session()) as db:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.is_active = False
                    db.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error deactivating user: {e}")
            return False
    
    @staticmethod
    def get_all_users(limit: int = 100, offset: int = 0) -> list[User]:
        """Get all users with pagination"""
        try:
            with next(get_db_session()) as db:
                return db.query(User).offset(offset).limit(limit).all()
        except Exception as e:
            print(f"Error getting all users: {e}")
            return []
