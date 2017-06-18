import os
import re
from flask import Flask, jsonify, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_jsglue import JSGlue
import sqlalchemy
from sqlalchemy.sql import text, and_, or_, not_, select, insert

#from cs50 import SQL
from helpers import lookup



# configure application
app = Flask(__name__)
JSGlue(app)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response


#Use sqlalchemy to create database instance and connection
db = sqlalchemy.create_engine("sqlite:///mashup.db")
conn = db.connect()

#Import list of states and their codes from file
statesList = []
codesList = []
with open("americanStates.txt", "r") as file:
    for line in file.readlines():
        items = line.split(",")
        statesList.append(items[0].strip().lower())
        codesList.append(items[1].strip().lower())

@app.route("/")
def index():
    """Render map."""
    #print (codesList)
    apiKey = "AIzaSyCP7WxtRPdPxmdpyPjEpatPe7r5kZv0AxM"
    return render_template("index.html", key=apiKey)

@app.route("/articles")
def articles():
    """Look up articles for geo."""

    geo = request.args.get("geo")
    results = lookup(geo)
    return jsonify(results)

@app.route("/search")
def search():
    """Search for places that match query."""
    q = request.args.get("q")
    q = q.replace(" /  +/g"," ")
    
    if "," in q:
        print ("COMMA") #for debug
        tokens = [item.strip().lower() for item in q.split(",")]
    elif " " in q:
        print ("SPACE") #for debug
        tokens = [item.strip().lower() for item in q.split(" ")]
    else:
        isInteger = False
        try:
            postalCode = int(q)
            isInteger = True
        except ValueError:
            pass
        
        if isInteger:
            print ("NUMBER")
            query = text("""SELECT * FROM places WHERE postal_code LIKE :q
                            GROUP BY country_code, place_name, admin_code1
                            ORDER BY postal_code
                            LIMIT 10
                        """)
            results = conn.execute(query,q=q + "%")
        else:
            print ("NOT NUMBER")
            query = text("""SELECT * FROM places WHERE place_name LIKE :q OR admin_name1 LIKE :q OR admin_name2 LIKE :q
                            GROUP BY country_code, place_name, admin_code1
                            ORDER BY place_name
                            LIMIT 10
                            """)
            results = conn.execute(query,q=q + "%")
            
        rows = [dict(result) for result in results]
        return jsonify(rows)
        
    if "us" in tokens:
        tokens.remove("us")
        
    containsCode = False
    containsState = False
    
    for token in tokens:
        if token in codesList:
            containsCode = True
            code = token
            tokens.remove(token)
            value=code
        elif token in statesList:
            containsState=True
            state = token
            tokens.remove(token)
            value = state
            
    if containsCode or containsState:
        query = text("""SELECT * FROM places WHERE admin_code1 LIKE :value AND (place_name LIKE :value OR place_name LIKE :value2 OR admin_name2 LIKE :value2)
                    GROUP BY country_code, place_name, admin_code1
                    ORDER BY place_name
                    LIMIT 10
                """)
        updatedQuery = " ".join(tokens) + "%"
        results = conn.execute(query, value=value, value2=updatedQuery)
    if not containsCode and not containsState:
        query = text("""SELECT * FROM places WHERE place_name LIKE :q OR admin_name1 LIKE :q OR admin_name2 LIKE :q
                            GROUP BY country_code, place_name, admin_code1
                            ORDER BY place_name
                            LIMIT 10
                            """)
        results = conn.execute(query,q=q + "%")
        
    rows = [dict(result) for result in results]
    return jsonify(rows)
        
@app.route("/update")
def update():
    """Find up to 10 places within view."""

    # ensure parameters are present
    if not request.args.get("sw"):
        raise RuntimeError("missing sw")
    if not request.args.get("ne"):
        raise RuntimeError("missing ne")

    # ensure parameters are in lat,lng format
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("sw")):
        raise RuntimeError("invalid sw")
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("ne")):
        raise RuntimeError("invalid ne")

    # explode southwest corner into two variables
    (sw_lat, sw_lng) = [float(s) for s in request.args.get("sw").split(",")]

    # explode northeast corner into two variables
    (ne_lat, ne_lng) = [float(s) for s in request.args.get("ne").split(",")]

    # find 10 cities within view, pseudorandomly chosen if more within view
    query = text("")
    if (sw_lng <= ne_lng):
        # doesn't cross the antimeridian
        query = text(
        """SELECT * FROM places WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude AND longitude <= :ne_lng)
        GROUP BY country_code, place_name, admin_code1
        ORDER BY RANDOM()
        LIMIT 10""")

        
    else:
        query = text(
        """SELECT * FROM places WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude OR longitude <= :ne_lng)
        GROUP BY country_code, place_name, admin_code1
        ORDER BY RANDOM()
        LIMIT 10""")


    results = conn.execute(query, sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)
    rows = [dict(result) for result in results]
    # output places as JSON
    return jsonify(rows)