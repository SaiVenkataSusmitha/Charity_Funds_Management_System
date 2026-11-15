
from flask import Flask, render_template, request, redirect, flash, session
from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "charity-project-key"


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")


# USER REGISTRATION
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, hashed_password)
            )

            connection.commit()
            flash("Registration successful! Please login.")
            return redirect("/login")

        except Exception:
            connection.rollback()
            flash("Email already exists or registration failed.")

        finally:
            cursor.close()
            connection.close()

    return render_template("register.html")


# USER LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,)
            )

            user = cursor.fetchone()

            if user and check_password_hash(user[3], password):

                session["user_id"] = user[0]
                session["name"] = user[1]
                session["role"] = user[4]

                # Redirect according to user role
                if session["role"] == "admin":
                    return redirect("/admin-dashboard")
                else:
                    return redirect("/dashboard")

            else:
                flash("Invalid email or password.")

        finally:
            cursor.close()
            connection.close()

    return render_template("login.html")


# DONOR DASHBOARD
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM campaigns WHERE status = 'Active'"
        )

        campaigns = cursor.fetchall()

        return render_template(
            "dashboard.html",
            campaigns=campaigns
        )

    finally:
        cursor.close()
        connection.close()


# DONATION PAGE
@app.route("/donate", methods=["GET", "POST"])
def donate():

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == "POST":

            campaign_id = request.form["campaign_id"]

            try:
                amount = float(request.form["amount"])
            except ValueError:
                flash("Please enter a valid donation amount.")
                return redirect("/donate")

            if amount <= 0:
                flash("Please enter a valid donation amount.")
                return redirect("/donate")

            cursor.execute(
                "SELECT campaign_id FROM campaigns WHERE campaign_id = %s AND status = 'Active'",
                (campaign_id,)
            )

            campaign = cursor.fetchone()

            if not campaign:
                flash("Please select a valid campaign.")
                return redirect("/donate")

            cursor.execute(
                """INSERT INTO donations
                (user_id, campaign_id, amount)
                VALUES (%s, %s, %s)""",
                (session["user_id"], campaign_id, amount)
            )

            connection.commit()

            flash("Thank you! Your donation was recorded successfully.")
            return redirect("/donate")

        cursor.execute(
            "SELECT * FROM campaigns WHERE status = 'Active'"
        )

        campaigns = cursor.fetchall()

        return render_template(
            "donate.html",
            campaigns=campaigns
        )

    finally:
        cursor.close()
        connection.close()


# DONATION HISTORY
@app.route("/donation-history")
def donation_history():

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT donations.donation_id,
                   campaigns.campaign_name,
                   donations.amount,
                   donations.donation_date
            FROM donations
            JOIN campaigns
            ON donations.campaign_id = campaigns.campaign_id
            WHERE donations.user_id = %s
            ORDER BY donations.donation_date DESC
        """, (session["user_id"],))

        donations = cursor.fetchall()

        return render_template(
            "donation_history.html",
            donations=donations
        )

    finally:
        cursor.close()
        connection.close()


# ADMIN DASHBOARD
@app.route("/admin-dashboard")
def admin_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    # Only admins can access this page
    if session.get("role") != "admin":
        flash("Access denied. Admins only.")
        return redirect("/dashboard")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT COUNT(*) AS total_users FROM users"
        )
        total_users = cursor.fetchone()["total_users"]

        cursor.execute(
            "SELECT COUNT(*) AS total_campaigns FROM campaigns"
        )
        total_campaigns = cursor.fetchone()["total_campaigns"]

        cursor.execute(
            "SELECT COUNT(*) AS total_donations FROM donations"
        )
        total_donations = cursor.fetchone()["total_donations"]

        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total_amount FROM donations"
        )
        total_amount = cursor.fetchone()["total_amount"]

        cursor.execute("SELECT * FROM campaigns")
        campaigns = cursor.fetchall()

        return render_template(
            "admin_dashboard.html",
            total_users=total_users,
            total_campaigns=total_campaigns,
            total_donations=total_donations,
            total_amount=total_amount,
            campaigns=campaigns
        )

    finally:
        cursor.close()
        connection.close()


# ADD NEW CAMPAIGN
@app.route("/add-campaign", methods=["GET", "POST"])
def add_campaign():

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        flash("Access denied. Admins only.")
        return redirect("/dashboard")

    if request.method == "POST":
        campaign_name = request.form["campaign_name"].strip()
        description = request.form["description"].strip()

        try:
            target_amount = float(request.form["target_amount"])
        except ValueError:
            flash("Enter a valid target amount.")
            return redirect("/add-campaign")

        if not campaign_name or target_amount <= 0:
            flash("Enter valid campaign details.")
            return redirect("/add-campaign")

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """INSERT INTO campaigns
                (campaign_name, description, target_amount)
                VALUES (%s, %s, %s)""",
                (campaign_name, description, target_amount)
            )
            connection.commit()
            flash("New campaign added successfully!")
            return redirect("/admin-dashboard")

        finally:
            cursor.close()
            connection.close()

    return render_template("add_campaign.html")
# ADD CAMPAIGN EXPENSE
@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        flash("Access denied. Admins only.")
        return redirect("/dashboard")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        if request.method == "POST":
            campaign_id = request.form["campaign_id"]
            description = request.form["description"].strip()

            try:
                amount = float(request.form["amount"])
            except ValueError:
                flash("Enter a valid expense amount.")
                return redirect("/add-expense")

            if not description or amount <= 0:
                flash("Enter valid expense details.")
                return redirect("/add-expense")

            cursor.execute(
                """INSERT INTO expenses
                (campaign_id, description, amount)
                VALUES (%s, %s, %s)""",
                (campaign_id, description, amount)
            )

            connection.commit()
            flash("Expense recorded successfully!")
            return redirect("/admin-dashboard")

        cursor.execute(
            "SELECT campaign_id, campaign_name FROM campaigns"
        )
        campaigns = cursor.fetchall()

        return render_template(
            "add_expense.html",
            campaigns=campaigns
        )

    finally:
        cursor.close()
        connection.close()

# VIEW EXPENSE HISTORY
@app.route("/expense-history")
def expense_history():

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        flash("Access denied. Admins only.")
        return redirect("/dashboard")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT
                expenses.expense_id,
                campaigns.campaign_name,
                expenses.description,
                expenses.amount,
                expenses.expense_date
            FROM expenses
            JOIN campaigns
            ON expenses.campaign_id = campaigns.campaign_id
            ORDER BY expenses.expense_date DESC
        """)

        expenses = cursor.fetchall()

        return render_template(
            "expense_history.html",
            expenses=expenses
        )

    finally:
        cursor.close()
        connection.close()

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)