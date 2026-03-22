import os
from flask import Flask, flash, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_ # Add this to your imports at the top
from datetime import datetime, timedelta # Add this to your imports at the top
import random

app = Flask(__name__)
app.secret_key = 'harar_raffle_super_secret_key_2026' # Change this to any long string
# 2. Configure the Database path
# This tells SQLAlchemy where to save the 'harar.db' file
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///raffle.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# 3. Create the 'db' object <-- THIS FIXES YOUR ERROR
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20)) # Added this
    password = db.Column(db.String(200))     # Added this
    payment_company = db.Column(db.String(50))
    account_number = db.Column(db.String(50))
    sub_type = db.Column(db.String(20))
    receipt_image = db.Column(db.String(200))
    role = db.Column(db.String(20), default='poster')
    is_approved = db.Column(db.Boolean, default=False)

    # NEW FIELDS
    approval_date = db.Column(db.DateTime)   # When they were verified
    expiry_date = db.Column(db.DateTime)     # When they lose access

class Post(db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    raffle_name = db.Column(db.String(100), nullable=False)
    raffle_value = db.Column(db.Float, nullable=False)
    total_raffles = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(100), nullable=False)
    prize_1 = db.Column(db.Float, nullable=False)
    prize_2 = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    draw_start_time = db.Column(db.DateTime) # Time when the last ticket was sold

      #Use back_populates instead of backref
    tickets = db.relationship('Ticket', 
                               back_populates='parent_raffle', 
                               foreign_keys='Ticket.raffle_id')
    # 2. This is specifically for the ONE winning ticket
    winner_id = db.Column(db.Integer, db.ForeignKey('ticket.id'))
    winner_2_id = db.Column(db.Integer, db.ForeignKey('ticket.id')) # New field
    winner = db.relationship('Ticket', foreign_keys=[winner_id])
    winner_2 = db.relationship('Ticket', foreign_keys=[winner_2_id]) # New relationship

    winner_payment_proof = db.Column(db.String(255), nullable=True)   # For 1st place
    winner_2_payment_proof = db.Column(db.String(255), nullable=True) # For 2nd place
    # ... for chat box ...
    messages = db.relationship('Message', backref='raffle', lazy=True, cascade="all, delete-orphan")
    # Add this line inside your Post class
    organizer = db.relationship('User', backref='my_raffles_list')
    # 🚀 ADD THIS LINE TO FIX THE ERROR
    user = db.relationship('User', backref='my_raffles')

class Ticket(db.Model):
    __tablename__ = 'ticket'
    id = db.Column(db.Integer, primary_key=True)
    raffle_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    # Add this line to link Ticket back to the Post (Raffle)
   # Explicitly link back to Post.tickets
    parent_raffle = db.relationship('Post', 
                                     back_populates='tickets', 
                                     foreign_keys=[raffle_id])
    number_selected = db.Column(db.Integer)
    buyer_name = db.Column(db.String(100))
    buyer_phone = db.Column(db.String(20))
    payment_screenshot = db.Column(db.String(100))
    is_confirmed = db.Column(db.Boolean, default=False) # Poster clicks this
# 1. Add the Model
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    raffle_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    sender_name = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)




@app.route('/')
def home():
    # Get the search term from the URL (e.g., /?search=iphone)
    search_query = request.args.get('search', '')
    
    # 1. Start with the base query
    query = Post.query
    
    # 2. If user searched for something, filter the results
    if search_query:
        query = query.filter(Post.raffle_name.ilike(f"%{search_query}%"))
    
    # 3. Execute the query
    all_raffles = query.order_by(Post.created_at.desc()).all()
    
    now = datetime.utcnow()
    user_id = session.get('user_id')
    user = db.session.get(User, user_id) if user_id else None
    
    recent_winners = Post.query.filter(Post.winner_id != None)\
                               .order_by(Post.draw_start_time.desc())\
                               .limit(4).all()
    
    def is_raffle_full(raffle):
        confirmed_count = Ticket.query.filter_by(raffle_id=raffle.id, is_confirmed=True).count()
        return confirmed_count >= raffle.total_raffles
    
    return render_template('home.html', 
                           raffles=all_raffles, 
                           user=user, 
                           recent_winners=recent_winners, 
                           is_raffle_full=is_raffle_full, 
                           now=now, 
                           timedelta=timedelta,
                           search_query=search_query) # Pass it back to the template
# 2. Add the Route to post a message
@app.route('/send-message/<int:raffle_id>', methods=['POST'])
def send_message(raffle_id):
    name = request.form.get('name')
    text = request.form.get('text')
    
    if name and text:
        new_msg = Message(raffle_id=raffle_id, sender_name=name, text=text)
        db.session.add(new_msg)
        db.session.commit()
    
    return redirect(url_for('select_number', raffle_id=raffle_id))

@app.route('/delete-message/<int:message_id>')
def delete_message(message_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    message = db.session.get(Message, message_id)
    if not message:
        return redirect(url_for('home'))
        
    # Security: Only the organizer of the raffle can delete messages
    if session['user_id'] == message.raffle.user_id:
        db.session.delete(message)
        db.session.commit()
        flash("Message removed.", "info")
    
    return redirect(url_for('select_number', raffle_id=message.raffle_id))




@app.route('/upload-payment-proof/<int:raffle_id>/<int:winner_rank>', methods=['POST'])
def upload_payment_proof(raffle_id, winner_rank):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    # ✅ Modern 2.0 Syntax
    raffle = db.session.get(Post, raffle_id)
    
    file = request.files.get('screenshot')
    if file and raffle:
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"proof_{raffle_id}_{winner_rank}.{ext}")
        file.save(os.path.join('static/uploads', filename))
        
        if winner_rank == 1: raffle.winner_payment_proof = filename
        else: raffle.winner_2_payment_proof = filename
        
        db.session.commit()
        flash('Payment proof uploaded!', 'success')
    return redirect(url_for('poster_dashboard'))

@app.route('/remove-payment-proof/<int:raffle_id>/<int:winner_rank>')
def remove_payment_proof(raffle_id, winner_rank):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    # ✅ Modern 2.0 Syntax
    raffle = db.session.get(Post, raffle_id)
    
    if raffle:
        if winner_rank == 1: raffle.winner_payment_proof = None
        else: raffle.winner_2_payment_proof = None
        db.session.commit()
        flash('Payment proof removed.', 'info')
    return redirect(url_for('poster_dashboard'))


@app.route('/check-winner/<int:raffle_id>')
def check_winner(raffle_id):
    raffle = Post.query.get_or_404(raffle_id)
    
    if not raffle.winner_id:
        confirmed_tickets = Ticket.query.filter_by(raffle_id=raffle_id, is_confirmed=True).all()
        
        if confirmed_tickets:
            # 1. Pick the Grand Prize Winner
            winning_ticket_1 = random.choice(confirmed_tickets)
            raffle.winner_id = winning_ticket_1.id
            
            # 2. Check if there is a 2nd Prize and enough tickets to pick a different person
            if raffle.prize_2 and len(confirmed_tickets) > 1:
                # Remove the first winner from the list so they don't win twice!
                remaining_tickets = [t for t in confirmed_tickets if t.id != winning_ticket_1.id]
                winning_ticket_2 = random.choice(remaining_tickets)
                raffle.winner_2_id = winning_ticket_2.id
                
            db.session.commit()
            
    return redirect(url_for('select_number', raffle_id=raffle_id))


@app.route('/reject-ticket/<int:ticket_id>')
def reject_ticket(ticket_id):
    user_id = session.get('user_id')
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Use parent_raffle here!
    if user_id == ticket.parent_raffle.user_id:
        db.session.delete(ticket)
        db.session.commit()
        flash(f"Ticket #{ticket.number_selected} rejected.", "warning")
    return redirect(url_for('poster_dashboard'))


@app.route('/select-number/<int:raffle_id>')
def select_number(raffle_id):
    raffle = Post.query.get_or_404(raffle_id)
    
    # 1. Map tickets for the grid
    tickets = Ticket.query.filter_by(raffle_id=raffle_id).all()
    ticket_map = {t.number_selected: t for t in tickets}
    
    # 2. Show results only if the 30-second animation "window" has passed
    show_results = False
    if raffle.winner_id:
        if raffle.draw_start_time:
            now = datetime.utcnow()
            # If current time is 30+ seconds after the draw started, show results
            if now > (raffle.draw_start_time + timedelta(seconds=30)):
                show_results = True
        else:
            show_results = True

    return render_template('select_number.html', 
                           raffle=raffle, 
                           ticket_map=ticket_map,
                           show_results=show_results)



@app.route('/buy-ticket/<int:raffle_id>', methods=['POST'])
def buy_ticket(raffle_id):
    # Get form data
    number = request.form.get('number')
    name = request.form.get('name')
    phone = request.form.get('phone')
    file = request.files.get('screenshot')

    if file:
        filename = secure_filename(f"ticket_{raffle_id}_{number}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # Create the ticket in database
        new_ticket = Ticket(
            raffle_id=raffle_id,
            number_selected=int(number),
            buyer_name=name,
            buyer_phone=phone,
            payment_screenshot=filename,
            is_confirmed=False  # Poster must approve this later
        )
        db.session.add(new_ticket)
        db.session.commit()
        # 🚀 THE SUCCESS MESSAGE
        flash(f"Success! Number {number} is reserved. Please wait for the poster to verify your payment.", "success")
        return redirect(url_for('home'))
    
    flash("Error: Please upload a valid payment screenshot.", "danger")
    return redirect(url_for('select_number', raffle_id=raffle_id))


@app.route('/poster-dashboard')
def poster_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # ✅ Modern 2.0 Syntax
    user = db.session.get(User, user_id)
    
    # Update your tickets query to avoid the AmbiguousForeignKey error too
    tickets = Ticket.query.join(Post, Ticket.raffle_id == Post.id).filter(
        Post.user_id == user_id, 
        Ticket.is_confirmed == False
    ).all()
    
    my_raffles = Post.query.filter_by(user_id=user_id).all()
    
    return render_template('poster_dash.html', user=user, tickets=tickets, my_raffles=my_raffles)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone_input = request.form.get('phone_number') # Matches HTML name
        password_input = request.form.get('password')
        
        # 🚀 Query the database using the phone_number column
        user = User.query.filter_by(phone_number=phone_input).first()
        
        if user and user.password == password_input:
            session['user_id'] = user.id
            flash('Welcome back!', 'success')
            return redirect(url_for('poster_dashboard'))
        else:
            flash('Invalid phone number or password.', 'danger')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/confirm-ticket/<int:ticket_id>')
def confirm_ticket(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    raffle = ticket.parent_raffle
    ticket.is_confirmed = True
    
    # Check if this was the last ticket needed
    confirmed_count = Ticket.query.filter_by(raffle_id=raffle.id, is_confirmed=True).count()
    
    if confirmed_count >= raffle.total_raffles:
        # 🚀 PRE-PICK THE WINNERS NOW
        confirmed_tickets = Ticket.query.filter_by(raffle_id=raffle.id, is_confirmed=True).all()
        
        if not raffle.winner_id:
            # Pick 1st Place
            win1 = random.choice(confirmed_tickets)
            raffle.winner_id = win1.id
            
            # Pick 2nd Place (if applicable)
            if raffle.prize_2 and len(confirmed_tickets) > 1:
                remaining = [t for t in confirmed_tickets if t.id != win1.id]
                win2 = random.choice(remaining)
                raffle.winner_2_id = win2.id
            
            # Set the draw time to 5 minutes from now
            raffle.draw_start_time = datetime.utcnow() + timedelta(seconds=25)
            
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/posting', methods=['GET', 'POST'])
def posting_tab():
    user = None  # <--- FIX: Initialize user to None so it always exists
    
    if request.method == 'POST':
        phone = request.form.get('phone')
        pwd = request.form.get('password')
        
        found_user = User.query.filter_by(phone_number=phone, password=pwd).first()
        
        if found_user:
            if not found_user.is_approved:
                return "<h3>Wait for Admin approval.</h3>"
            
            # Check if expired
            if datetime.utcnow() > found_user.expiry_date:
                return "<h3>Your subscription has expired. Please renew.</h3>"
            
            session['user_id'] = found_user.id
            user = found_user  # Assign the found user
            return render_template('posting.html', verified=True, user=user)
        else:
            return "<h3>Invalid credentials.</h3><a href='/posting'>Try again</a>"

    # If it's a GET request, 'user' is None, but the variable still exists!
    return render_template('posting.html', verified=False, user=user)



@app.route('/submit-post', methods=['POST'])
def submit_post():
    # 1. Get user_id from hidden input or session
    user_id = request.form.get('user_id')
    
    # 2. Get and Convert values (using 0 as fallback to avoid crashes)
    try:
        val = float(request.form.get('raffle_value', 0))
        total = int(request.form.get('total_raffles', 0))
        p1 = float(request.form.get('prize_1', 0))
       # Capture prize_2 but default to 0 if it's empty
        p2_raw = request.form.get('prize_2')
        p2 = float(p2_raw) if p2_raw and p2_raw.strip() else 0.0
        # 3. Perform the Mathematical Guardrail
        total_revenue = val * total
        prize_sum = p1 + p2
        
        # Validation bounds
        min_allowed = total_revenue * 0.80
        max_allowed = total_revenue * 0.95
        
        # 4. Strict Enforcement
        if total_revenue <= 0:
            return "Error: Revenue must be greater than 0.", 400
            
        if prize_sum < min_allowed or prize_sum > max_allowed:
            return f"Security Alert: Mathematical violation! Prizes must be between {min_allowed} and {max_allowed} ETB.", 400

        # 5. Save to Database if all checks pass
        new_post = Post(
            raffle_name=request.form.get('raffle_name'),
            raffle_value=val,
            total_raffles=total,
            payment_method=request.form.get('payment_method'),
            prize_1=p1,
            prize_2=p2,
            user_id=user_id
        )
        db.session.add(new_post)
        db.session.commit()
        
        return redirect(url_for('home'))

    except ValueError:
        return "Error: Invalid numeric input.", 400

@app.route('/register')
def register():
    return render_template('registration.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    # 1. Handle the Admin Login Form Submission
    if request.method == 'POST':
        phone = request.form.get('phone')
        pwd = request.form.get('password')
        
        # Check if this is the Admin account
        admin_user = User.query.filter_by(phone_number=phone, password=pwd, role='admin').first()
        
        if admin_user:
            session['admin_id'] = admin_user.id
            return redirect(url_for('admin_dashboard'))
        else:
            return "<h3>Invalid Admin Credentials</h3><a href='/admin'>Try Again</a>"

    # 2. Check if Admin is already logged in
    if 'admin_id' in session:
        # --- YOUR QUERY GOES HERE ---
        # It only grabs posters waiting for your "OK"
        pending_users = User.query.filter_by(role='poster', is_approved=False).all()
        
        return render_template('admin.html', pending=pending_users, is_admin=True)

    # 3. If not logged in and no POST data, show Login Page
    return render_template('admin.html', is_admin=False)

# Logic to approve a user
@app.route('/approve/<int:user_id>')
def approve_user(user_id):
    # Only allow if an admin is logged in
    if 'admin_id' not in session:
        return redirect(url_for('admin_dashboard'))

    user_to_approve = User.query.get(user_id)
    if user_to_approve:
        user_to_approve.is_approved = True
        
        # Calculate expiry date based on their chosen plan
        now = datetime.utcnow()
        if user_to_approve.sub_type == '1 Month':
            user_to_approve.expiry_date = now + timedelta(days=30)
        else:
            user_to_approve.expiry_date = now + timedelta(days=365)
            
        db.session.commit()
        
    return redirect(url_for('admin_dashboard'))
@app.route('/logout')
def logout():
    session.clear() # This "clears the room" and logs everyone out
    return redirect(url_for('home'))

@app.route('/submit-registration', methods=['POST'])
def submit_registration():
    # Get password data
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    # 1. Check if passwords match
    if password != confirm_password:
        return "<h1>Error: Passwords do not match!</h1><a href='/register'>Try Again</a>"
    # 1. Capture the form text data
    full_name = request.form.get('full_name')
    phone = request.form.get('phone_number')
    company = request.form.get('payment_company')
    acc_num = request.form.get('account_number')
    sub = request.form.get('sub_type')

    # 2. Handle the screenshot upload
    file = request.files.get('receipt')
    filename = None
    
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        # Ensure the path exists: static/uploads/
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)
    
    # 3. Create the database record
    new_user = User(
        full_name=full_name, # or a unique ID logic
        phone_number=phone,
        password=password, # In the future, we will hash this!
        payment_company=company,
        account_number=acc_num,
        sub_type=sub,
        receipt_image=filename,
        role='poster',
        is_approved=False
    )
    
    try:
        db.session.add(new_user)
        db.session.commit()
        # Redirect to a success page or home
        return "<h1>Success!</h1><p>Your receipt is being reviewed.</p><a href='/'>Back Home</a>"
    except Exception as e:
        return f"There was an error saving to the database: {e}"

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Check if Admin already exists, if not, create one
        admin_exists = User.query.filter_by(role='admin').first()
        if not admin_exists:
            # You can set your own secret password here
            admin = User(full_name="Raffle Admin", 
                         phone_number="0900000000", 
                         password="adminsecret", 
                         role="admin", 
                         is_approved=True)
            db.session.add(admin)
            db.session.commit()
            print("Admin account created!")
    app.run(debug=True)

