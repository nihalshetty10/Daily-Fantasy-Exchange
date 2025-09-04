from flask import Blueprint, request, jsonify, session
from datetime import datetime, date
from backend.services.auth_service import AuthService
from backend.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate email format
        email = data['email']
        if '@' not in email or '.' not in email:
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate password strength
        password = data['password']
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        # Parse date of birth if provided
        date_of_birth = None
        if data.get('date_of_birth'):
            try:
                date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Create user
        user_data = AuthService.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            date_of_birth=date_of_birth,
            phone_number=data.get('phone_number'),
            address=data.get('address'),
            city=data.get('city'),
            state=data.get('state'),
            zip_code=data.get('zip_code'),
            country=data.get('country', 'US')
        )
        
        if user_data:
            # Set session
            session['user_id'] = user_data['id']
            session['username'] = user_data['username']
            
            return jsonify({
                'message': 'User created successfully',
                'user': user_data
            }), 201
        else:
            return jsonify({'error': 'Username or email already exists'}), 409
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login a user"""
    try:
        data = request.get_json()
        
        if not data.get('username') or not data.get('password'):
            return jsonify({'error': 'Username and password are required'}), 400
        
        user_data = AuthService.authenticate_user(data['username'], data['password'])
        
        if user_data:
            # Set session
            session['user_id'] = user_data['id']
            session['username'] = user_data['username']
            
            return jsonify({
                'message': 'Login successful',
                'user': user_data
            }), 200
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout a user"""
    try:
        session.clear()
        return jsonify({'message': 'Logout successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get current user profile"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = AuthService.get_user_by_id(user_id)
        if user:
            return jsonify({'user': user.to_dict()}), 200
        else:
            return jsonify({'error': 'User not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Update current user profile"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        
        # Parse date of birth if provided
        if data.get('date_of_birth'):
            try:
                data['date_of_birth'] = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Remove sensitive fields that shouldn't be updated via this endpoint
        data.pop('password', None)
        data.pop('password_hash', None)
        data.pop('id', None)
        data.pop('created_at', None)
        data.pop('updated_at', None)
        
        success = AuthService.update_user_info(user_id, **data)
        
        if success:
            user = AuthService.get_user_by_id(user_id)
            return jsonify({
                'message': 'Profile updated successfully',
                'user': user.to_dict()
            }), 200
        else:
            return jsonify({'error': 'Failed to update profile'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """Change user password"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Current password and new password are required'}), 400
        
        if len(new_password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters long'}), 400
        
        user = AuthService.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        user.set_password(new_password)
        
        # Save to database
        from backend.db import get_db_session
        with next(get_db_session()) as db:
            db.add(user)
            db.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/check-auth', methods=['GET'])
def check_auth():
    """Check if user is authenticated"""
    try:
        user_id = session.get('user_id')
        if user_id:
            user = AuthService.get_user_by_id(user_id)
            if user:
                return jsonify({
                    'authenticated': True,
                    'user': user.to_dict()
                }), 200
        
        return jsonify({'authenticated': False}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
