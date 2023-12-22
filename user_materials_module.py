import requests
import psycopg2


def connect_to_database():
    return psycopg2.connect(dbname="GW2 Item Crafter", user="postgres", password="pass", host="localhost")


def fetch_users(cursor):
    cursor.execute("SELECT user_id, api_key FROM users")
    return cursor.fetchall()


def fetch_user_materials(api_key):
    url = f"https://api.guildwars2.com/v2/account/materials?access_token={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(
            f"Error fetching user materials for API key {api_key}: {response.status_code}")
        return None


def fetch_item_details(item_id):
    url = f"https://api.guildwars2.com/v2/items/{item_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(
            f"Error fetching details for item {item_id}: {response.status_code}")
        return None


def insert_material_data(cursor, user_id, materials):
    for material in materials:
        cursor.execute(
            "SELECT item_id FROM items WHERE item_id = %s", (material['id'],))
        item_exists = cursor.fetchone()

        if not item_exists:
            item_details = fetch_item_details(material['id'])
            if item_details:
                cursor.execute("INSERT INTO items (item_id, item_name) VALUES (%s, %s)",
                               (item_details['id'], item_details['name']))

        cursor.execute(
            "INSERT INTO usermaterials (user_id, material_id, count) VALUES (%s, %s, %s) ON CONFLICT (user_id, material_id) DO UPDATE SET count = EXCLUDED.count",
            (user_id, material['id'], material['count'])
        )


def process_user_materials(user_id, api_key):
    conn = connect_to_database()
    cursor = conn.cursor()
    materials = fetch_user_materials(api_key)
    if materials:
        insert_material_data(cursor, user_id, materials)
    conn.commit()
    cursor.close()
    conn.close()
    print("Materials processing completed")
