
try:
    import mysql.connector
except ImportError:
    mysql = None
import pandas as pd

from decimal import Decimal
from datetime import date, datetime, time
from .security import decrypt_password


# --------------------------------------------------
# 1. CONNECT TO EXTERNAL MYSQL
# --------------------------------------------------

def connect_mysql(config):

    return mysql.connector.connect(
        host=config["host"],
        port=int(config["port"]),
        user=config["username"],
        password=config["password"],
        database=config["database_name"],
        connection_timeout=5
    )


# --------------------------------------------------
# 2. GET SAVED CONNECTION CONFIGURATION
# --------------------------------------------------

def get_connection_config(saved_connection):

    return {
        "host": saved_connection.host,
        "port": saved_connection.port,
        "username": saved_connection.username,

        "password": decrypt_password(
            saved_connection.encrypted_password
        ),

        "database_name": saved_connection.database_name
    }


# --------------------------------------------------
# 3. DISCOVER AVAILABLE TABLES
# --------------------------------------------------

def get_tables(connection):

    cursor = connection.cursor()

    try:

        cursor.execute("SHOW TABLES")

        return [
            row[0]
            for row in cursor.fetchall()
        ]

    finally:

        cursor.close()


# --------------------------------------------------
# 4. CONVERT MYSQL DATA TYPES
# --------------------------------------------------

def convert_dataframe_types(df):

    for column in df.columns:

        # Convert MySQL DECIMAL values to numeric
        if df[column].map(
            lambda value: isinstance(value, Decimal)
        ).any():

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        # Convert boolean values to numeric
        elif df[column].map(
            lambda value: isinstance(value, bool)
        ).any():

            df[column] = df[column].astype("boolean")

    return df


# --------------------------------------------------
# 5. LOAD MYSQL TABLE INTO PANDAS DATAFRAME
# --------------------------------------------------

def load_table_dataframe(connection, table_name):

    available_tables = get_tables(connection)

    # Validate table name
    if table_name not in available_tables:

        raise ValueError("Table not found.")

    # Escape SQL identifier safely
    safe_table = table_name.replace("`", "``")

    cursor = connection.cursor()

    try:

        cursor.execute(
            f"SELECT * FROM `{safe_table}` LIMIT 100000"
        )

        columns = [
            description[0]
            for description in cursor.description
        ]

        rows = cursor.fetchall()

        df = pd.DataFrame(
            rows,
            columns=columns
        )

        # Convert MySQL values into appropriate Pandas types
        df = convert_dataframe_types(df)

        return df

    finally:

        cursor.close()


# --------------------------------------------------
# 6. CONVERT VALUES INTO JSON-SAFE FORMAT
# --------------------------------------------------

def convert_json_value(value):

    # Handle NULL / NaN / NaT
    if pd.isna(value):

        return None

    # Handle dates and timestamps
    if isinstance(
        value,
        (datetime, date, time, pd.Timestamp)
    ):

        return value.isoformat()

    # Handle Decimal
    if isinstance(value, Decimal):

        return float(value)

    # Handle bytes
    if isinstance(value, (bytes, bytearray)):

        return value.decode(
            "utf-8",
            errors="replace"
        )

    # Handle NumPy scalar values
    if hasattr(value, "item"):

        return value.item()

    return value


# --------------------------------------------------
# 7. CONVERT DATAFRAME INTO JSON RESPONSE
# --------------------------------------------------

def dataframe_to_json(df, limit=10):

    preview = df.head(limit).copy()

    rows = []

    for record in preview.to_dict(
        orient="records"
    ):

        converted_record = {

            str(key): convert_json_value(value)

            for key, value in record.items()

        }

        rows.append(converted_record)

    return {

        "columns": [
            str(column)
            for column in preview.columns
        ],

        "rows": rows

    }
