import psycopg2
import user_recipes_module
import user_materials_module
import user_characters_module
import requests


def connect_to_database():
    # change this to connect to your db
    return psycopg2.connect(dbname="", user="", password="", host="")


def fetch_market_price(item_id):
    url = f"https://api.guildwars2.com/v2/commerce/prices/{item_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None


def format_price(price):
    if price is None:
        return "Price not found"
    gold = price // 10000
    silver = (price % 10000) // 100
    copper = price % 100
    return f"{gold}g {silver}s {copper}c"


def create_user():
    username = input("Enter your username: ")
    api_key = input("Enter your API key: ")

    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))

    if cursor.fetchone():
        print("User already exists.")
    else:
        cursor.execute(
            "INSERT INTO users (api_key, username) VALUES (%s, %s)", (api_key, username))
        conn.commit()
        print("User created successfully.")

    cursor.close()
    conn.close()


def search_for_item(user_id):
    while True:
        item_name = input(
            "Enter the item name (or type 'exit' to go back): ").strip().lower()

        if item_name == 'exit':
            break

        conn = connect_to_database()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT item_id FROM items WHERE LOWER(item_name) = %s", (item_name,))
        item = cursor.fetchone()

        if item:
            item_id = item[0]
            display_recipe_tree(cursor, item_id, 0, user_id)
        else:
            print("Item not found.")

        cursor.close()
        conn.close()


def display_recipe_tree(cursor, item_id, level, user_id):
    cursor.execute(
        "SELECT item_name FROM items WHERE item_id = %s", (item_id,))
    item_name_result = cursor.fetchone()
    item_name = item_name_result[0] if item_name_result else f"Item ID {item_id}"

    cursor.execute(
        "SELECT recipe_id, min_rating FROM recipes WHERE output_item_id = %s", (item_id,))
    recipe_info = cursor.fetchone()

    if recipe_info:
        recipe_id, min_rating = recipe_info
        cursor.execute(
            "SELECT discipline FROM recipe_disciplines WHERE recipe_id = %s", (recipe_id,))
        disciplines = cursor.fetchall()
        cursor.execute(
            "SELECT recipe_id FROM userrecipes WHERE user_id = %s AND recipe_id = %s", (user_id, recipe_id))
        known_recipe = cursor.fetchone()
        print("   " * level + f"Recipe for '{item_name}':")
        print("   " * (level + 1) +
              f"{'Known' if known_recipe else 'Unknown'} recipe")

        for discipline_row in disciplines:
            discipline = discipline_row[0]
            characters_with_discipline = has_required_discipline_and_level(
                cursor, discipline, min_rating, user_id)

            if characters_with_discipline:
                character_names = ', '.join(
                    [character[0] for character in characters_with_discipline])
                print("   " * (level + 1) +
                      f"Can be crafted by characters: {character_names}")
                print("   " * (level + 1) +
                      f"Discipline Required: {discipline}, Minimum Level: {min_rating}")
            else:
                print("   " * (level + 1) +
                      f"No character can craft this. Required: {discipline}, Level: {min_rating}")

        cursor.execute(
            "SELECT ingredient_id, count FROM recipe_ingredients WHERE recipe_id = %s", (recipe_id,))
        ingredients = cursor.fetchall()

        for ingredient in ingredients:
            ingredient_id, count_required = ingredient
            market_price_data = fetch_market_price(ingredient_id)
            market_price = market_price_data['buys']['unit_price'] if market_price_data else None
            formatted_price = format_price(market_price)

            cursor.execute(
                "SELECT item_name FROM items WHERE item_id = %s", (ingredient_id,))
            ingredient_name = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count FROM usermaterials WHERE user_id = %s AND material_id = %s", (user_id, ingredient_id))
            user_material = cursor.fetchone()
            count_user_has = user_material[0] if user_material else 0

            still_needed = count_required - count_user_has
            if still_needed > 0:
                print("   " * (level + 1) +
                      f"> {ingredient_name}, Required Amount: {count_required}, Have: {count_user_has}, (Need: {still_needed}, Market Price: {formatted_price})")
            else:
                print("   " * (level + 1) +
                      f"> {ingredient_name}, Required Amount: {count_required}, Have: {count_user_has}, (Already have enough, Market Price: {formatted_price})")
            display_recipe_tree(cursor, ingredient_id, level + 2, user_id)


def has_required_discipline_and_level(cursor, discipline, min_rating, user_id):
    cursor.execute("SELECT character_name FROM character_crafting_disciplines WHERE discipline = %s AND rating >= %s AND character_name IN (SELECT name FROM characters WHERE user_id = %s)", (discipline, min_rating, user_id))
    return cursor.fetchall()


def get_api_key(username):
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT api_key FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None


def login_user():
    username = input("Enter your username: ")

    if username.lower() == 'admin':
        admin_functionality()
    else:
        user_id = get_user_id(username)
        if user_id:
            api_key = get_api_key(username)
            if api_key:
                print(
                    f"Welcome, {username}!\nUpdating data for your account, this may take a while...")
                user_characters_module.process_user_characters(
                    user_id, api_key)
                user_materials_module.process_user_materials(user_id, api_key)
                user_recipes_module.process_user_recipes(user_id, api_key)
                process_auto_learned_recipes(user_id)
                search_for_item(user_id)

            else:
                print("API key not found for the user.")
        else:
            print("User not found.")


def fetch_auto_learned_recipes(cursor):
    cursor.execute("""
        SELECT r.recipe_id, r.min_rating, array_agg(d.discipline)
        FROM recipes r
        JOIN recipe_disciplines d ON r.recipe_id = d.recipe_id
        WHERE r.auto_learned = True
        GROUP BY r.recipe_id, r.min_rating
    """)
    return cursor.fetchall()


def process_auto_learned_recipes(user_id):
    conn = connect_to_database()
    cursor = conn.cursor()

    auto_learned_recipes = fetch_auto_learned_recipes(cursor)
    user_characters = user_characters_module.fetch_user_characters(
        cursor, user_id)

    for recipe_id, min_rating, disciplines in auto_learned_recipes:
        for char_name, discipline, char_rating in user_characters:
            if discipline in disciplines and char_rating >= min_rating:
                cursor.execute(
                    "INSERT INTO userrecipes (user_id, recipe_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (user_id, recipe_id)
                )
                break

    conn.commit()
    cursor.close()
    conn.close()


def admin_functionality():
    print("Admin access granted.")
    input("Press any key to update game recipes...")
    import game_recipes_module
    game_recipes_module.process_game_recipes()


def get_user_id(username):
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None


def main_menu():
    choice = input("Choose an option: \n1. Login \n2. Create New User\n")
    if choice == '1':
        login_user()
    elif choice == '2':
        create_user()
    else:
        print("Invalid choice. Please try again.")
        main_menu()


if __name__ == "__main__":
    main_menu()
