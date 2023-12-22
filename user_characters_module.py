import requests
import psycopg2


def connect_to_database():
    return psycopg2.connect(dbname="GW2 Item Crafter", user="postgres", password="pass", host="localhost")


def fetch_users(cursor):
    cursor.execute("SELECT user_id, api_key FROM users")
    return cursor.fetchall()


def fetch_character_names(api_key):
    url = f"https://api.guildwars2.com/v2/characters?access_token={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(
            f"Error fetching character names for API key {api_key}: {response.status_code}")
        return None


def fetch_detailed_character_data(api_key, character_name):
    url = f"https://api.guildwars2.com/v2/characters/{character_name}?access_token={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(
            f"Error fetching data for character {character_name}: {response.status_code}")
        return None


def insert_character_data(cursor, user_id, character_names, api_key):
    for name in character_names:
        detailed_char_data = fetch_detailed_character_data(api_key, name)
        if detailed_char_data:
            cursor.execute(
                "INSERT INTO characters (user_id, name, profession) VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING",
                (user_id, detailed_char_data['name'],
                 detailed_char_data['profession'])
            )

            for craft in detailed_char_data.get('crafting', []):
                cursor.execute(
                    "INSERT INTO character_crafting_disciplines (character_name, discipline, rating, active) VALUES (%s, %s, %s, %s) ON CONFLICT (character_name, discipline) DO NOTHING",
                    (detailed_char_data['name'], craft['discipline'],
                     craft['rating'], craft['active'])
                )

def fetch_user_characters(cursor, user_id):
    cursor.execute("""
        SELECT c.name, cd.discipline, cd.rating
        FROM characters c
        JOIN character_crafting_disciplines cd ON c.name = cd.character_name
        WHERE c.user_id = %s
    """, (user_id,))
    return cursor.fetchall()


def process_user_characters(user_id, api_key):
    conn = connect_to_database()
    cursor = conn.cursor()
    character_names = fetch_character_names(api_key)
    if character_names:
        insert_character_data(cursor, user_id, character_names, api_key)
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Character data processing completed")
