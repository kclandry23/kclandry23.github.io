import os

from pyxirr import xirr
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, hlookup

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET"])
@login_required
def index():
    uses = db.execute("SELECT COUNT(quantity) AS duses FROM transactions WHERE user_id = ?", session["user_id"])

    if uses[0]["duses"] <= 0:
        user = db.execute("SELECT username AS user FROM users WHERE id = ?", session["user_id"])
        return render_template("newindex.html", user = user[0]["user"])

    else:
        # Display performance stats:
        # Get transactions
        transactions = db.execute("SELECT quantity, price, date FROM transactions WHERE user_id = ?", session["user_id"])
        # Define variables for calls and dists for MOIC calculation
        calls = 0
        dists = 0
        # Define variables for future value of calls and distributions for PME
        fvcalls = 0
        fvdists = 0
        # Define list for XIRR and direct alpha calculation
        irrdates = []
        irrcf = []
        dacf = []
        # Get present value of S&P500
        spy = lookup("SPY")
        spyp = spy["price"]
        # Calculate FV of each transaciton if it was instead used to buy S&P500 shares
        for transaction in transactions:
            # Make date compatible with API
            date = datetime.strptime(transaction["date"], "%Y-%m-%d")
            cdate = datetime.strftime(date, '%Y%m%d')
            # Get value of S&P500 transaction date
            spyh = hlookup(cdate)
            # Get value change of S&P500 over period since transaction
            spychange = spyp / spyh
            # Calculate cost of transaction
            cost = transaction["price"] * transaction["quantity"]
            # Seperate into calls and dists for MOIC
            if cost > 0:
                calls += cost
            if cost < 0:
                dists -= cost
            # Calculate FV if invested into S&P
            fvt = spychange * cost
            # Add dates and future value cash flows/cash flows to lists of dates/cashflows for IRR/DA
            irrdates.append(date)
            irrcf.append(-cost)
            dacf.append(-fvt)
            # Seperate into fvcalls and fvdistributions and add them to totals for PME
            if fvt > 0:
                fvcalls += fvt
            if fvt < 0:
                fvdists -= fvt

        # Display Portfolio:
        s_value = 0
        # sum transactions
        stocks = db.execute("SELECT symbol, SUM(quantity) AS quantity_o FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(quantity) > 0 ", session["user_id"])
        # get prices and values
        for holding in stocks:
            if holding.get("stocks") != 0:
                quoted = lookup(holding.get("symbol"))
                holding["price"] = quoted["price"]
                holding["value"] = holding.get("quantity_o") * holding["price"] 
                s_value += holding["value"]

        # Add value of current holdings to FVdists and dists to calculate MOIC and PME with unrealized value
        fvdists += s_value
        dists += s_value
        # Add value of current holdings to lists of dates and cashflows for IRR/DA
        irrdates.append(datetime.strptime(datetime.today().strftime("%Y-%m-%d"), "%Y-%m-%d"))
        irrcf.append(s_value)
        dacf.append(s_value)
        # Calculate PME, remove decimals and add x
        dpme = fvdists / fvcalls
        pme = f"{dpme:,.2f} x"
        #calculate MOIC, remove decimals and add x
        dmoic = dists / calls
        moic = f"{dmoic:,.2f} x"
        #calculate value generated
        tvalue = dists - calls
        # Allow for IRR errors
        eirr = 0
        try:
            dirr = (xirr(irrdates, irrcf) * 100)
            dda = xirr(irrdates, dacf) * 100
        except (KeyError, TypeError, ValueError):
            eirr = 1
        #calculate IRR and direct alpha and clean values and remove non menaingful xirr
        if eirr == 1:
            irr = "Error"
            da = "Error"
        else:
            if 1000 < dirr:
                irr = "Not meaningful"
            elif -1000 > dirr:
                irr = "Not meaningful"
            else: 
                irr = f"{dirr:,.2f} %"
            if 1000 < dda:
                da = "Not meaningful"
            elif -1000 > dda:
                da = "Not meaningful"
            else:
                da = f"{dda:,.2f} %"

        # output page/variables
        return render_template("index.html", stocks=stocks, s_value = s_value, pme = pme, moic = moic, tvalue = tvalue, irr = irr, da = da)


@app.route("/transactions", methods=["GET", "POST"])
@login_required
def buy():
    """Record Buy Transaction"""

    if request.method == "POST":
        # check valid form
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        
        if not request.form.get("shares"):
            return apology("must provide quantity", 400)

        if not request.form.get("date"):
            return apology("must provide date", 400)
        
        # Check weekday
        date = datetime.strptime(request.form.get("date"), "%Y-%m-%d")
        day = date.weekday()
        if day > 4:
            return apology("must provide date when market is open", 400)

        while True:
            try:
                x = int(request.form.get("shares"))
                break
            except ValueError:
                return apology("invalid quantity", 400)

        if int(request.form.get("shares")) < 1:
            return apology("must provide positive integer quantity", 400)

        # lookup quote and record variables
        quoted = lookup(request.form.get("symbol"))
        price = (request.form.get("price"))
        quantity = int(request.form.get("shares"))
        date = (request.form.get("date"))

        if quoted == None:
            return apology("invalid symbol", 400)

        # save transaction 
        db.execute("INSERT INTO transactions (symbol, quantity, price, user_id, date) VALUES(?, ?, ?, ?, ?)", quoted["symbol"], quantity, price, session["user_id"], date)
        
        # Output todays date for input error prevention
        today = datetime.today().strftime("%Y-%m-%d")

        flash("Transaction Recorded")
        # return to same page
        return render_template("transactions.html", today = today)

    else: 
        # Output todays date for input error prevention
        today = datetime.today().strftime("%Y-%m-%d")
        return render_template("transactions.html", today = today)


@app.route("/stransactions", methods=["POST"])
@login_required
def sell():
    """Record Sell Transaction"""
    # check valid form
    if not request.form.get("symbol"):
        return apology("must provide symbol", 400)
    
    if not request.form.get("shares"):
        return apology("must provide quantity", 400)

    if not request.form.get("date"):
        return apology("must provide date", 400)
    
    while True:
        try:
            x = int(request.form.get("shares"))
            break
        except ValueError:
            return apology("invalid quantity", 400)

    if int(request.form.get("shares")) < 1:
        return apology("must provide positive integer quantity", 400)

    # lookup quote and record variables
    quoted = lookup(request.form.get("symbol"))
    price = (request.form.get("price"))
    quantity = - int(request.form.get("shares"))
    date = (request.form.get("date"))

    if quoted == None:
        return apology("invalid symbol", 400)

    # save transaction 
    db.execute("INSERT INTO transactions (symbol, quantity, price, user_id, date) VALUES(?, ?, ?, ?, ?)", quoted["symbol"], quantity, price, session["user_id"], date)
    
    flash("Transaction Recorded")
    # return to same page
    return render_template("transactions.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    historys = db.execute("SELECT symbol, quantity, price, date FROM transactions WHERE user_id = ?", session["user_id"])

    return render_template("history.html", historys=historys)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Cornfirm password match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 400)
        
        # check username availible
        if db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username")):
            return apology("username taken", 400)
        
        username = request.form.get("username")
        password = request.form.get("password")
        hash = generate_password_hash(password)

        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

    return apology("TODO")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
