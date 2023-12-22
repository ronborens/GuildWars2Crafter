import requests
import psycopg2


def connect_to_database():
    return psycopg2.connect(dbname="GW2 Item Crafter", user="postgres", password="pass", host="localhost")


def fetch_users(cursor):
    cursor.execute("SELECT user_id, api_key FROM users")
    return cursor.fetchall()


def fetch_user_recipes(api_key):
    url = f"https://api.guildwars2.com/v2/account/recipes?access_token={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(
            f"Error fetching recipes for API key {api_key}: {response.status_code}")
        return None


def insert_user_recipes(cursor, user_id, recipe_ids):
    for recipe_id in recipe_ids:
        cursor.execute(
            "INSERT INTO userrecipes (user_id, recipe_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, recipe_id)
        )



def process_user_recipes(user_id, api_key):
    conn = connect_to_database()
    cursor = conn.cursor()
    learned_recipes = fetch_user_recipes(api_key)
    if learned_recipes:
        insert_user_recipes(cursor, user_id, learned_recipes)
        
    conn.commit()
    cursor.close()
    conn.close()
    print("Recipes processing completed")
