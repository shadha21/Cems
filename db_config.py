
#import mysql.connector

#def get_db_connection():
#    return mysql.connector.connect(
#        host="localhost",
#        user="root",
#        password="Shadha@123",
#  )

import mysql.connector
import os

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("mysql.railway.internal"),
        user=os.getenv("root"),
        password=os.getenv("fwhOsncSkLuKMyxkQzaYuzkYaHlWsjZm"),
        database=os.getenv("railway"),
        port=os.getenv("3306")
#import mysql.connector

#def get_db_connection():
#    return mysql.connector.connect(
#        host="localhost",
#        user="root",
#        password="Shadha@123",
#  )
