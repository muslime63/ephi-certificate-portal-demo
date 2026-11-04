def init_db():
    with app.app_context():
        db.create_all()
        
        # 1. Clean up any capital 'Admin' entries from past runs
        capital_admin = Admin.query.filter_by(username='Admin').first()
        if capital_admin:
            db.session.delete(capital_admin)
            db.session.commit()
            
        # 2. Find or create the standard lowercase 'admin' user
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            hashed_pw = generate_password_hash('admin123')
            default_admin = Admin(username='admin', password_hash=hashed_pw)
            db.session.add(default_admin)
        else:
            # Force update password hash to 'admin123'
            admin.password_hash = generate_password_hash('admin123')
            
        db.session.commit()
