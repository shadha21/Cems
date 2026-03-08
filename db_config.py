import mysql.connector
import os

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get('MYSQLHOST','mysql.railway.internal'),
        user=os.environ.get('MYSQLUSER','root'),
        password=os.environ.get('MYSQLPASSWORD','sFBhoPiXyjGqBWcnuwxMJdRwGJSAyvYM'),
        database=os.environ.get('MYSQLDATABASE','railway'),
        port=int(os.environ.get('MYSQLPORT','3306'))
    )
