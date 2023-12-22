import requests
import psycopg2


def connect_to_database():
    # change to connect your db
    return psycopg2.connect(dbname="", user="", password="", host="")


def fetch_recipe_ids():
    url = "https://api.guildwars2.com/v2/recipes"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    print(f"Error fetching recipe IDs: {response.status_code}")
    return []


def fetch_recipes_details(recipe_ids):
    url = "https://api.guildwars2.com/v2/recipes"
    params = {'ids': ','.join(map(str, recipe_ids))}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    print(f"Error fetching recipes details: {response.status_code}")
    return []


def fetch_item_details(item_id):
    url = f"https://api.guildwars2.com/v2/items/{item_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None


def ensure_item_exists(cursor, conn, item_id):
    cursor.execute("SELECT item_id FROM items WHERE item_id = %s", (item_id,))
    if cursor.fetchone() is None:
        item_details = fetch_item_details(item_id)
        if item_details:
            cursor.execute(
                "INSERT INTO items (item_id, item_name) VALUES (%s, %s)",
                (item_id, item_details['name'])
            )
            conn.commit()
            print(f"Inserted item {item_id} into items table.")
            return True, item_details['name']
        else:
            print(f"Item details not found for item_id {item_id}")
            return False, None
    return True, None


def insert_recipe_data(cursor, conn, recipes):
    for recipe in recipes:
        # Check if output item exists
        output_item_exists, _ = ensure_item_exists(
            cursor, conn, recipe['output_item_id'])
        if not output_item_exists:
            continue

        # Check if all ingredients exist
        all_ingredients_exist = True
        for ingredient in recipe.get('ingredients', []):
            ingredient_exists, _ = ensure_item_exists(
                cursor, conn, ingredient['item_id'])
            if not ingredient_exists:
                all_ingredients_exist = False
                break

        if not all_ingredients_exist:
            continue

        # Check if the recipe is auto-learned
        auto_learned = 'AutoLearned' in recipe.get('flags', [])

        # Insert recipe data into the database
        cursor.execute("""
            INSERT INTO recipes (recipe_id, output_item_id, output_item_count, min_rating, auto_learned) 
            VALUES (%s, %s, %s, %s, %s) 
            ON CONFLICT (recipe_id) DO UPDATE SET 
                output_item_id = EXCLUDED.output_item_id, 
                output_item_count = EXCLUDED.output_item_count, 
                min_rating = EXCLUDED.min_rating,
                auto_learned = EXCLUDED.auto_learned
            """,
                       (recipe['id'], recipe['output_item_id'],
                        recipe['output_item_count'], recipe['min_rating'], auto_learned)
                       )

        # Insert disciplines associated with the recipe
        for discipline in recipe['disciplines']:
            cursor.execute("""
                INSERT INTO recipe_disciplines (recipe_id, discipline) 
                VALUES (%s, %s) 
                ON CONFLICT (recipe_id, discipline) DO NOTHING
                """,
                           (recipe['id'], discipline)
                           )

        # Insert ingredients required for the recipe
        for ingredient in recipe.get('ingredients', []):
            cursor.execute("""
                INSERT INTO recipe_ingredients (recipe_id, ingredient_id, count) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (recipe_id, ingredient_id) DO UPDATE SET 
                    count = EXCLUDED.count
                """,
                           (recipe['id'], ingredient['item_id'],
                            ingredient['count'])
                           )

        print(f"Inserted/Updated recipe {recipe['id']}")


def process_game_recipes():
    conn = connect_to_database()
    cursor = conn.cursor()

    print("Fetching recipe IDs...")
    recipe_ids = fetch_recipe_ids()
    print(
        f"Fetched {len(recipe_ids)} recipe IDs. Fetching and inserting recipe details...")

    batch_size = 200
    for i in range(0, len(recipe_ids), batch_size):
        batch = recipe_ids[i:i + batch_size]
        recipes = fetch_recipes_details(batch)
        if recipes:
            insert_recipe_data(cursor, conn, recipes)

    conn.commit()
    cursor.close()
    conn.close()
    print("Game recipes processing completed.")
