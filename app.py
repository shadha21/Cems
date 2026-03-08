import os
import mysql.connector
import webbrowser
from threading import Timer

from flask import Flask, render_template, request, redirect, url_for, session, flash

from db_config import get_db_connection
from datetime import date
app = Flask(__name__)
app.secret_key = 'cems_secret_key'


@app.route('/test-db')
def test_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    cursor.close()
    conn.close()
    return str(tables)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM admin WHERE Email=%s AND Password=%s",
            (email, password)
        )
        admin = cursor.fetchone()

        cursor.close()
        conn.close()

        if admin:
            session['admin_id'] = admin['AdminID']
            session['admin_name'] = admin['User_name']
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid credentials")

    return render_template('admin_login.html')

@app.route('/events')
def events():
    conn = get_db_connection()       # get a connection from dbconfig.py
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
    SELECT e.EventID, e.Event_name, e.Date, e.Time, e.Type,
           v.Location_name AS Location_name,
           c.Club_name AS Club_name,
           GROUP_CONCAT(DISTINCT s.SponsorName SEPARATOR ', ') AS Sponsors
    FROM event e
    JOIN venue v ON e.VenueID = v.VenueID
    JOIN club c ON e.ClubID = c.ClubID
    LEFT JOIN event_sponsor s ON e.EventID = s.EventID
    GROUP BY e.EventID
""")

    events = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('events.html', events=events)
@app.route('/student-login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM student WHERE Email=%s AND Password=%s",
            (email, password)
        )
        student = cursor.fetchone()

        cursor.close()
        conn.close()

        if student:
            session['student_id'] = student['StudentID']
            session['student_name'] = student['User_name']
            return redirect(url_for('student_dashboard'))
        else:
            flash("Invalid student credentials")

    return render_template('student_login.html')

@app.route('/student-dashboard')
def student_dashboard():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Student details
    #cursor.execute(
    #    "SELECT * FROM student WHERE StudentID = %s",
    #    (session['student_id'],)
    #)
    cursor.execute("""
SELECT s.StudentID,
       s.User_name,
       s.Dept,
       s.Email,
       GROUP_CONCAT(sp.Phone_Number SEPARATOR ', ') AS Phone_Number
FROM student s
LEFT JOIN student_phone sp
ON s.StudentID = sp.StudentID
WHERE s.StudentID = %s
GROUP BY s.StudentID
""", (session['student_id'],))
    student = cursor.fetchone()

    # Registered events for this student
    cursor.execute("""
        SELECT e.EventID,
               e.Event_name,
               e.Date,
               e.Time,
               e.Type,
               v.Location_name AS Venue,
               c.Club_name AS Club,
               GROUP_CONCAT(DISTINCT s.SponsorName SEPARATOR ', ') AS Sponsors
        FROM event e
        JOIN venue v ON e.VenueID = v.VenueID
        JOIN club c ON e.ClubID = c.ClubID
        LEFT JOIN event_sponsor s ON e.EventID = s.EventID
        JOIN registration r ON e.EventID = r.EventID
        WHERE r.StudentID = %s
        GROUP BY e.EventID, e.Event_name, e.Date, e.Time, e.Type, v.Location_name, c.Club_name
    """, (session['student_id'],))
    registered_events = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'student_dashboard.html',
        student=student,
        registered_events=registered_events
    )





@app.route('/admin-dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM admin WHERE AdminID = %s",
        (session['admin_id'],)
    )
    admin = cursor.fetchone()
    
    cursor.execute("""
SELECT e.EventID,
       e.Event_name,
       e.Date,
       e.Time,
       e.Type,
       v.Location_name AS Venue,
       c.Club_name AS Club,
       COALESCE(s.Sponsors, '') AS Sponsors,
       COALESCE(f.Facilities, '') AS Facilities
FROM event e
INNER JOIN venue v ON e.VenueID = v.VenueID
INNER JOIN club c ON e.ClubID = c.ClubID
LEFT JOIN (
    SELECT EventID,
           GROUP_CONCAT(DISTINCT SponsorName ORDER BY SponsorName SEPARATOR ', ') AS Sponsors
    FROM event_sponsor
    GROUP BY EventID
) s ON e.EventID = s.EventID
LEFT JOIN (
    SELECT VenueID,
           GROUP_CONCAT(DISTINCT FacilityName ORDER BY FacilityName SEPARATOR ', ') AS Facilities
    FROM venue_facility
    GROUP BY VenueID
) f ON v.VenueID = f.VenueID
WHERE e.AdminID = %s
""", (session['admin_id'],))
    admin_events = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        'admin_dashboard.html',
        admin=admin,
        admin_events=admin_events
    )

@app.route('/add-event', methods=['GET', 'POST'])
def add_event():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':

        event_name = request.form['event_name']
        event_date = request.form['date']
        time = request.form['time']
        type_ = request.form['type']
        venue_id = request.form['venue_id']
        club_id = request.form['club_id']
        sponsor = request.form.get('sponsor')

        # CHECK MAINTENANCE
        cursor.execute("""
        SELECT * FROM maintenance
        WHERE Venue_ID = %s
        AND %s BETWEEN Start_date AND End_date
        """, (venue_id, event_date))

        maintenance = cursor.fetchone()

        if event_date < str(date.today()):
           flash("⚠ Cannot create event in past date")
           return redirect(url_for('add_event'))

        # IF VENUE UNDER MAINTENANCE
        if maintenance:

            flash("⚠ Venue is under maintenance between "
                  + str(maintenance['Start_date']) +
                  " and "
                  + str(maintenance['End_date']))

            cursor.close()
            conn.close()

            # Redirect back to Add Event page
            return redirect(url_for('add_event'))

        # INSERT EVENT
        cursor.execute("""
        INSERT INTO event (Event_name, Date, Time, Type, VenueID, ClubID, AdminID)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (event_name, event_date, time, type_, venue_id, club_id, session['admin_id']))

        event_id = cursor.lastrowid

        if sponsor:
            cursor.execute("""
            INSERT INTO event_sponsor(EventID,SponsorName)
            VALUES(%s,%s)
            """, (event_id, sponsor))

        conn.commit()

        cursor.close()
        conn.close()

        flash("✅ Event created successfully!")

        return redirect(url_for('admin_dashboard'))

    # GET REQUEST
    cursor.execute("SELECT VenueID, Location_name, Capacity FROM venue")
    venues = cursor.fetchall()

    cursor.execute("SELECT ClubID, Club_name, Club_head FROM club")
    clubs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('add_event.html', venues=venues, clubs=clubs)
@app.route('/student-signup', methods=['GET', 'POST'])
def student_signup():
    if request.method == 'POST':
        username = request.form['username']
        dept = request.form['dept']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']

        conn = get_db_connection()
        cursor = conn.cursor()

        #cursor.execute("""
        #    INSERT INTO student (User_name, Dept, Email, Password, Phone_Number)
        #    VALUES (%s, %s, %s, %s, %s)
        #""", (username, dept, email, password, phone))
        cursor.execute("""
INSERT INTO student (User_name, Dept, Email, Password)
VALUES (%s, %s, %s, %s)
""", (username, dept, email, password))

        student_id = cursor.lastrowid

        cursor.execute("""
INSERT INTO student_phone (StudentID, Phone_Number)
VALUES (%s, %s)
""", (student_id, phone))
        conn.commit()
        cursor.close()
        conn.close()

        flash("Account created successfully. Please login.")
        return redirect(url_for('student_login'))

    return render_template('student_signup.html')
@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO admin (User_name, Email, Password)
            VALUES (%s, %s, %s)
        """, (username, email, password))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Admin account created. Please login.")
        return redirect(url_for('admin_login'))

    return render_template('admin_signup.html')

@app.route('/student-events')
def student_events():

    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    #cursor.execute("""
    #SELECT e.EventID,
    #       e.Event_name,
    #       e.Date,
    #       e.Time,
    #       e.Type,
    #       v.Location_name AS Venue,
    #       c.Club_name AS Club,
    #       COALESCE(GROUP_CONCAT(DISTINCT s.SponsorName SEPARATOR ', '),'No Sponsor') AS Sponsors,
    #       v.Capacity,
    #       COUNT(r.RegID) AS registered_count,
    #       (v.Capacity - COUNT(r.RegID)) AS available_seats
    #FROM event e
    #JOIN venue v ON e.VenueID = v.VenueID
    #JOIN club c ON e.ClubID = c.ClubID
    #LEFT JOIN registration r ON e.EventID = r.EventID
    #LEFT JOIN event_sponsor s ON e.EventID = s.EventID
    #GROUP BY e.EventID
    #""")
    cursor.execute("""
SELECT e.EventID,
       e.Event_name,
       e.Date,
       e.Time,
       e.Type,
       v.Location_name AS Venue,
       c.Club_name AS Club,
       v.Capacity,
       COUNT(DISTINCT r.RegID) AS registered_count,
       (v.Capacity - COUNT(DISTINCT r.RegID)) AS available_seats
FROM event e
JOIN venue v ON e.VenueID = v.VenueID
JOIN club c ON e.ClubID = c.ClubID
LEFT JOIN registration r ON e.EventID = r.EventID
GROUP BY e.EventID, e.Event_name, e.Date, e.Time, e.Type, v.Location_name, c.Club_name, v.Capacity
""")
    events = cursor.fetchall()

    cursor.execute("""
    SELECT EventID FROM registration
    WHERE StudentID = %s
    """, (session['student_id'],))

    registered_event_ids = [row['EventID'] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return render_template(
        'student_events.html',
        events=events,
        registered_event_ids=registered_event_ids,
        current_date=date.today()
    )
@app.route('/register-event/<int:event_id>')
def register_event(event_id):

    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get capacity and registrations
    cursor.execute("""
        SELECT v.Capacity, COUNT(r.RegID) AS registered
        FROM event e
        JOIN venue v ON e.VenueID = v.VenueID
        LEFT JOIN registration r ON e.EventID = r.EventID
        WHERE e.EventID = %s
    """, (event_id,))

    seat_data = cursor.fetchone()
    # Check event date
    cursor.execute("SELECT Date FROM event WHERE EventID=%s", (event_id,))
    event_date = cursor.fetchone()

    if event_date['Date'] < date.today():
       flash("⚠ Registration closed. Event already finished.")
       return redirect(url_for('student_events'))

    available = seat_data['Capacity'] - seat_data['registered']

    if available <= 0:
        flash("❌ Sorry! No seats available for this event.")
        return redirect(url_for('student_events'))

    # Prevent duplicate registration
    cursor.execute("""
        SELECT 1 FROM registration
        WHERE StudentID = %s AND EventID = %s
    """, (session['student_id'], event_id))

    already_registered = cursor.fetchone()

    if already_registered:
        flash("⚠ You already registered for this event!")
        return redirect(url_for('student_events'))

    # Register student
    cursor.execute("""
        INSERT INTO registration (Reg_date, StudentID, EventID)
        VALUES (%s, %s, %s)
    """, (date.today(), session['student_id'], event_id))

    conn.commit()

    cursor.close()
    conn.close()

    flash("✅ Registration successful!")

    return redirect(url_for('student_events'))
@app.route('/give-feedback/<int:event_id>', methods=['GET','POST'])
def give_feedback(event_id):

    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':

        rating = request.form['rating']
        comments = request.form['comments']

        cursor.execute("""
        INSERT INTO feedback (Rating, Comments, StudentID, EventID)
        VALUES (%s,%s,%s,%s)
        """,(rating,comments,session['student_id'],event_id))

        conn.commit()

        cursor.close()
        conn.close()

        flash("✅ Feedback submitted successfully!")

        return redirect(url_for('student_dashboard'))

    # GET request → show feedback form

    cursor.execute("""
    SELECT Event_name
    FROM event
    WHERE EventID=%s
    """,(event_id,))

    event = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('give_feedback.html', event=event, event_id=event_id)
@app.route('/admin-feedback/<int:event_id>')
def admin_feedback(event_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get event details
    cursor.execute("""
        SELECT e.EventID, e.Event_name, v.Location_name, c.Club_name,
               GROUP_CONCAT(f.FacilityName SEPARATOR ', ') AS Facilities
        FROM event e
        JOIN venue v ON e.VenueID = v.VenueID
        JOIN club c ON e.ClubID = c.ClubID
        LEFT JOIN venue_facility f ON v.VenueID = f.VenueID
        WHERE e.EventID = %s AND e.AdminID = %s
        GROUP BY e.EventID
    """, (event_id, session['admin_id']))
    event = cursor.fetchone()

    if not event:
        cursor.close()
        conn.close()
        return "Unauthorized or event not found"

    # Get feedback list
    cursor.execute("""
        SELECT f.Rating, f.Comments, s.User_name
        FROM feedback f
        JOIN student s ON f.StudentID = s.StudentID
        WHERE f.EventID = %s
    """, (event_id,))
    feedbacks = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'admin_feedback.html',
        event=event,
        feedbacks=feedbacks
    )

@app.route('/add-facility', methods=['GET', 'POST'])
def add_facility():

    if request.method == 'POST':

        venue_id = request.form.get('venue_id')
        facility_name = request.form.get('facility_name')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
SELECT * FROM venue_facility
WHERE VenueID=%s AND FacilityName=%s
""",(venue_id, facility_name))

        existing = cursor.fetchone()

        if existing:
           flash("⚠ Facility already exists for this venue")
           return redirect(url_for('add_facility'))
        else:
          cursor.execute("""
        INSERT INTO venue_facility (VenueID, FacilityName)
        VALUES (%s,%s)
        """,(venue_id, facility_name))

        conn.commit()

        cursor.close()
        conn.close()

        flash("✅ Facility added successfully!")

        return redirect(url_for('add_facility'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT VenueID, Location_name FROM venue")
    venues = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('add_facility.html', venues=venues)
@app.route('/venue-maintenance', methods=['GET','POST'])
def venue_maintenance():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':

        venue_id = request.form['venue_id']
        start_date = request.form['start_date']
        end_date = request.form['end_date']

        # CHECK OVERLAPPING MAINTENANCE
        cursor.execute("""
        SELECT * FROM maintenance
        WHERE Venue_ID=%s
        AND (
            %s BETWEEN Start_date AND End_date
            OR
            %s BETWEEN Start_date AND End_date
        )
        """,(venue_id,start_date,end_date))

        existing = cursor.fetchone()

        if existing:
            flash("⚠ Venue is under maintenance on this date!", "error")
            return redirect(url_for('venue_maintenance'))

        # INSERT MAINTENANCE
        cursor.execute("""
        INSERT INTO maintenance(Venue_ID,Start_date,End_date)
        VALUES(%s,%s,%s)
        """,(venue_id,start_date,end_date))

        conn.commit()

        flash("🛠 Maintenance added successfully!")

        return redirect(url_for('venue_maintenance'))

    # GET REQUEST

    cursor.execute("SELECT VenueID, Location_name FROM venue")
    venues = cursor.fetchall()

    cursor.execute("""
    SELECT m.Maint_ID,v.Location_name,m.Start_date,m.End_date
    FROM maintenance m
    JOIN venue v ON m.Venue_ID=v.VenueID
    """)

    maintenance_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "venue_maintenance.html",
        venues=venues,
        maintenance_list=maintenance_list
    )

@app.route('/admin-logout')
def admin_logout():
    # Clear the admin session
    session.pop('admin_id', None)
    session.pop('admin_email', None)
    session.pop('admin_name', None)

    # Redirect back to the login page
    return redirect(url_for('admin_login'))

@app.route('/hello')
def hello():
    return "Hello route works"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))
if __name__ == '__main__':
    app.run(debug=True)


def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

