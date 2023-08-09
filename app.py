import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    id = session["user_id"]
    username = db.execute("SELECT username FROM users WHERE id = ?", id)
    username = username[0]["username"]
    cash = db.execute("SELECT cash FROM users WHERE id = ?", id)
    cash = cash[0]["cash"]
    everything = db.execute("SELECT * FROM owned WHERE username = ?", username)
    for i in everything:
        stck = lookup(i["stock"])
        stck = usd(stck["price"])
    for purchase in everything:
        quote = lookup(purchase["stock"])
        purchase["quote"] = quote
    return render_template("index.html", cash=usd(cash), everything=everything)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    id = session["user_id"]
    if request.method == "POST":
        symbol1 = request.form.get("symbol")
        shares = request.form.get("shares")
        try:
            shares = int(shares)
        except ValueError:
            return apology("Please input a number of shares")
        if not symbol1:
            return apology("Please enter a symbol")
        elif not shares or shares <= 0:
            return apology("Please enter the amount of shares you wish to purchase")
        o = lookup(symbol1)
        # print(o)
        if not o:
            return apology("The stock doesn't exist, please try again")
        stck = lookup(symbol1)
        p = stck["price"]
        old = p * shares
        a = db.execute("SELECT cash FROM users WHERE id = ?", id)
        username = db.execute("SELECT username FROM users WHERE id=?", id)
        username = username[0]["username"]
        a = a[0]["cash"]
        w = a - old
        if old > a:
            return apology(
                "You don't own enough money to complete the transaction", 403
            )

        else:
            buy = "BUY"
            new = a - old
            update = db.execute("UPDATE users SET cash=(?) WHERE id=(?)", w, id)
            current_date = datetime.datetime.now()
            formatted_date = current_date.strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "INSERT INTO purchases(stock, shares, price, username, time, type) VALUES (?, ?, ?, ?, ?, 'BUY')",
                symbol1,
                shares,
                old,
                username,
                formatted_date,
            )
            test = db.execute(
                "SELECT * FROM owned WHERE username = ? AND stock = ?",
                username,
                symbol1,
            )
            print(test)
            if len(test) > 0:
                if symbol1 in test[0]["stock"]:
                    db.execute(
                        "UPDATE owned SET shares = (shares + ?) WHERE stock = ? AND username = ?",
                        shares,
                        symbol1,
                        username,
                    )
            else:
                db.execute(
                    "INSERT INTO owned(shares, stock, username) VALUES (?, ?, ?)",
                    shares,
                    symbol1,
                    username,
                )
            flash(f"Bought {shares} for {usd(old)}")
            return redirect("/")
        return apology("Transaction failed")
    else:
        cash = db.execute("SELECT cash FROM users WHERE id = ?", id)
        cash = cash[0]["cash"]

        return render_template("buy.html", cash=usd(cash))


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    id = session["user_id"]
    username = db.execute("SELECT username FROM users WHERE id = (?)", id)
    username = username[0]["username"]
    cash = db.execute("SELECT cash FROM users WHERE id = (?)", id)
    cash = cash[0]["cash"]
    transactions = db.execute(
        "SELECT stock, shares, price, time, type FROM purchases WHERE username = ?",
        username,
    )
    print(transactions)

    return render_template("history.html", cash=usd(cash), transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        a = request.form.get("username")
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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please enter a symbol", 400)
        z = lookup(symbol)
        print(z)
        if z == None:
            return apology("Could not find the stock")
        z["price"] = usd(z["price"])
        print(z)
        if not z:
            return apology("The stock doesn't exist, please try again")
        id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id = ?", id)
        cash = cash[0]["cash"]
        return render_template("quoted.html", z=z, cash=usd(cash))
    else:
        id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id = ?", id)
        cash = cash[0]["cash"]
        return render_template("quote.html", cash=usd(cash))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        user = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        x = db.execute("SELECT * FROM users WHERE username = ?", user)
        if len(x) >= 1:
            return apology("Username already exists", 400)
        elif not user or not password or not confirmation:
            return apology("Please enter a username and/or a password", 400)
        elif password != confirmation:
            return apology("The passwords do not match, please try again", 400)
        else:
            db.execute(
                "INSERT INTO users(username, hash) VALUES(?, ?)",
                user,
                generate_password_hash(password),
            )
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        name = request.form.get("symbol")
        p = name
        shares = request.form.get("shares")
        if not name or not shares:
            return apology("What are you trying to do?", 403)
        shares = int(shares)
        id = session["user_id"]
        username = db.execute("SELECT username FROM users WHERE id = ?", id)
        username = username[0]["username"]
        list = {}
        list = db.execute("SELECT stock FROM owned WHERE username = ?", username)
        for name in list:
            if name["stock"] == name:
                return apology("Transaction failed, please try again", 403)
        x = db.execute(
            "SELECT shares FROM owned WHERE username = ? AND stock = ?", username, p
        )
        x = x[0]["shares"]
        if shares < 0 or shares > x:
            return apology("Please enter an actual number", 403)

        geo = lookup(p)
        geo = geo["price"]
        total = geo * shares
        db.execute(
            "UPDATE owned SET shares = shares - ? WHERE stock = ? AND username = ?",
            shares,
            p,
            username,
        )
        db.execute(
            "UPDATE users SET cash = cash + ? WHERE username = ?", total, username
        )
        type1 = "SELL"
        current_date = datetime.datetime.now()
        formatted_date = current_date.strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO purchases(shares, stock, price, username, time, type) VALUES(?, ?, ?, ?, ?, ?)",
            shares,
            p,
            total,
            username,
            formatted_date,
            type1,
        )
        flash(f"Sold {shares} stock(s) for {usd(total)}")
        return redirect("/")

        return apology("Success")
    else:
        id = session["user_id"]
        username = db.execute("SELECT username FROM users WHERE id = ?", id)
        username = username[0]["username"]
        owned = db.execute("SELECT stock FROM OWNED where USERNAME =?", username)
        cash = db.execute("SELECT cash FROM users WHERE id = ?", id)
        cash = cash[0]["cash"]
        list = []
        list = db.execute("SELECT stock FROM owned WHERE username = ?", username)
        for i in list:
            Z = i["stock"]

        return render_template("sell.html", cash=usd(cash), list=list)
